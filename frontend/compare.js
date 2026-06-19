// compare.py 的 JS port：normalize + difflib.SequenceMatcher（autojunk=False）等價對齊。
// UMD-lite：瀏覽器掛 global Compare；node 用 module.exports。
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Compare = api;
})(typeof self !== "undefined" ? self : this, function () {
  function normalize(text) {
    text = text.toLowerCase();
    text = text.replace(/[^\w\s']/g, " "); // 去標點；連字號等變空格
    text = text.replace(/'/g, "");          // 縮寫去 apostrophe：im / dont
    return text.split(/\s+/).filter(Boolean);
  }

  // difflib find_longest_match（無 junk）
  function findLongestMatch(a, b, b2j, alo, ahi, blo, bhi) {
    let besti = alo, bestj = blo, bestsize = 0;
    let j2len = {};
    for (let i = alo; i < ahi; i++) {
      const newj2len = {};
      const indices = b2j[a[i]] || [];
      for (const j of indices) {
        if (j < blo) continue;
        if (j >= bhi) break;
        const k = (j2len[j - 1] || 0) + 1;
        newj2len[j] = k;
        if (k > bestsize) { besti = i - k + 1; bestj = j - k + 1; bestsize = k; }
      }
      j2len = newj2len;
    }
    return [besti, bestj, bestsize];
  }

  function getMatchingBlocks(a, b) {
    const la = a.length, lb = b.length;
    const b2j = {};
    for (let j = 0; j < lb; j++) { (b2j[b[j]] = b2j[b[j]] || []).push(j); }
    const queue = [[0, la, 0, lb]];
    const matching = [];
    while (queue.length) {
      const [alo, ahi, blo, bhi] = queue.pop();
      const [i, j, k] = findLongestMatch(a, b, b2j, alo, ahi, blo, bhi);
      if (k) {
        matching.push([i, j, k]);
        if (alo < i && blo < j) queue.push([alo, i, blo, j]);
        if (i + k < ahi && j + k < bhi) queue.push([i + k, ahi, j + k, bhi]);
      }
    }
    matching.sort((x, y) => x[0] - y[0] || x[1] - y[1] || x[2] - y[2]);
    // 合併相鄰 block
    let i1 = 0, j1 = 0, k1 = 0;
    const nonAdjacent = [];
    for (const [i2, j2, k2] of matching) {
      if (i1 + k1 === i2 && j1 + k1 === j2) { k1 += k2; }
      else { if (k1) nonAdjacent.push([i1, j1, k1]); i1 = i2; j1 = j2; k1 = k2; }
    }
    if (k1) nonAdjacent.push([i1, j1, k1]);
    nonAdjacent.push([la, lb, 0]);
    return nonAdjacent;
  }

  function getOpcodes(a, b) {
    let i = 0, j = 0;
    const ops = [];
    for (const [ai, bj, size] of getMatchingBlocks(a, b)) {
      let tag = "";
      if (i < ai && j < bj) tag = "replace";
      else if (i < ai) tag = "delete";
      else if (j < bj) tag = "insert";
      if (tag) ops.push([tag, i, ai, j, bj]);
      i = ai + size; j = bj + size;
      if (size) ops.push(["equal", ai, i, bj, j]);
    }
    return ops;
  }

  function compareSentence(reference, spoken) {
    const ref = normalize(reference), hyp = normalize(spoken);
    const tokens = [];
    let correct = 0;
    for (const [tag, i1, i2, j1, j2] of getOpcodes(ref, hyp)) {
      if (tag === "equal") {
        for (let k = i1; k < i2; k++) { tokens.push({ ref: ref[k], status: "ok" }); correct++; }
      } else if (tag === "replace") {
        for (let k = i1; k < i2; k++) tokens.push({ ref: ref[k], status: "wrong" });
        for (let k = j1; k < j2; k++) tokens.push({ ref: hyp[k], status: "extra" });
      } else if (tag === "delete") {
        for (let k = i1; k < i2; k++) tokens.push({ ref: ref[k], status: "missing" });
      } else if (tag === "insert") {
        for (let k = j1; k < j2; k++) tokens.push({ ref: hyp[k], status: "extra" });
      }
    }
    const score = ref.length ? correct / ref.length : 0.0;
    return { tokens, score };
  }

  return { normalize, compareSentence };
});
