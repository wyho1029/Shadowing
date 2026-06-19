# Practice Booth（練習亭）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一個寄存於 GitHub Pages 的 PWA，讀取 Plan 1 在 Drive 產生的 `manifest.json`，讓使用者在手機逐句跟讀練習、用 Web Speech API + 一個 compare.py 的 JS port 做逐字評分，並把進度寫回 `progress.json` 形成補片閉環。

**Architecture:** 三件式 —— PWA（GitHub Pages，靜態 HTML/JS/CSS）、Apps Script JSON API（讀寫使用者 Drive 的 library 資料夾、解析音檔直connect link）、Drive（音檔 + manifest + progress）。評分全部 client-side。音檔以 `<audio preload>` 整條載入後本地逐句 seek。

**Tech Stack:** 純前端（無 build step）、Google Apps Script（`Code.gs`）、Node 內建測試（`node --test`，已驗機器有 node v24）。

**Spec:** [docs/superpowers/specs/2026-06-19-practice-booth-design.md](../specs/2026-06-19-practice-booth-design.md)

## Global Constraints

每個 task 的要求都隱含包含本節。

- **相對路徑**：PWA 寄存於 GitHub Pages **project site**（`https://wyho1029.github.io/Shadowing/`，子路徑）。所有資源用相對路徑（`./app.js`，**不可** `/app.js`）；service worker 用 `navigator.serviceWorker.register("./sw.js")`；manifest `start_url` 設 `"."`。
- **Apps Script 是唯一後端，且與 PWA 跨 origin**：GET 是 simple request（可直接 `fetch`）；**POST progress 必須用 `Content-Type: text/plain`** 以避開 CORS preflight（Apps Script 無 OPTIONS handler），server 端照 `JSON.parse`。
- **音檔**：`<audio>` 用 manifest 的 `audio_url`（Drive 直connect link）整條 `preload="auto"` 載入，本地 seek 逐句；不依賴遠端 range。
- **compare.js 必須與 [backend/app/compare.py](../../../backend/app/compare.py) 輸出完全一致**（oracle：其測試 case）。normalize：lowercase、`[^\w\s']`→空格、去 `'`、split。score = #ok / #ref。
- **manifest clip 形狀**（Plan 1 產生）：`{clip_id, source, title, audio_file, sentences:[{idx,text,start,end}]}`；Apps Script serve 時為每條 clip 增補 `audio_url`。
- **progress.json 形狀**：`{version:1, done_clips:[], attempts:[]}`。
- **目標平台**：Android Chrome 為主；Web Speech API 做 STT；iOS 缺 `SpeechRecognition` 時 feature-detect 退化為「播+錄+自聽」。
- **無 build step**；JS 測試用 `node --test`（從 `frontend/` 跑 `node --test test/`）。
- Git commit 訊息結尾加 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。

## File Structure

| 檔案 | 責任 | 動作 |
|------|------|------|
| `frontend/compare.js` | compare.py 的 JS port（normalize + SequenceMatcher 等價 + compareSentence）。UMD-lite：瀏覽器 global `Compare` + node CommonJS | Create |
| `frontend/practice-core.js` | 純邏輯：`pickNextClip(manifest, doneClips, showId)`、`markDone(progress, clipId)`。UMD-lite | Create |
| `frontend/test/compare.test.js` | node --test，對 compare.py 8 個 oracle case | Create |
| `frontend/test/practice-core.test.js` | node --test | Create |
| `frontend/config.js` | `window.API_BASE`（Apps Script /exec URL，部署時填） | Create |
| `frontend/app.js` | 主邏輯重寫：fetch manifest、揀 clip、音檔載入+seek、錄音+Web Speech+評分、POST progress | Modify（整檔重寫） |
| `frontend/index.html` | 相對路徑、UI 微調（用 manifest 的 shows、移除舊 server 搵片） | Modify |
| `frontend/sw.js` | 相對路徑、cache shell + 音檔 | Modify |
| `appscript/Code.gs` | Apps Script web app：doGet（manifest/progress）、doPost（progress）、Drive 讀寫 + audio link | Create |
| `appscript/appsscript.json` | Apps Script manifest（時區 + webapp 設定） | Create |

---

## Task 1: SPIKE — 瀏覽器三項可行性驗證（手動，gate）

**這不是 TDD 任務，是落實作前的硬 gate。** 使用者在 Android Chrome 跑，驗證 spec §6 三項；任一項紅就走對應 fallback 再繼續。

**Files:**
- Create: `appscript/spike.gs`（臨時，驗 CORS 用，spike 後可刪）
- Create: `frontend/spike.html`（臨時，spike 後可刪）

- [ ] **Step 1: 部署一個最小 Apps Script 回 JSON**

`appscript/spike.gs`：

```javascript
function doGet(e) {
  return ContentService
    .createTextOutput(JSON.stringify({ ok: true, when: new Date().toISOString() }))
    .setMimeType(ContentService.MimeType.JSON);
}
```

在 script.google.com 新建專案貼上，Deploy → New deployment → Web app → Execute as **Me**、Who has access **Anyone** → 複製 `/exec` URL。

- [ ] **Step 2: 放一個音檔上 Drive 並設分享**

把任何一個 `.m4a`（可從 `backend/data/library/audio/` 拿一個，或臨時跑一次 replenisher 產生）上傳到 Drive，右鍵 → 共用 → 「知道連結的任何人」→「檢視者」。記下檔案 ID，組成 `https://drive.google.com/uc?export=download&id=<ID>`。

- [ ] **Step 3: 建 spike 頁，驗三項**

`frontend/spike.html`（把 `APPS_SCRIPT_EXEC_URL` 與 `DRIVE_AUDIO_URL` 換成上面兩個）：

```html
<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>spike</title></head>
<body>
<h3>1. Drive audio load + seek</h3>
<audio id="a" src="DRIVE_AUDIO_URL" preload="auto" controls></audio>
<button onclick="document.getElementById('a').currentTime=20;document.getElementById('a').play()">seek to 20s + play</button>
<h3>2. Apps Script CORS fetch</h3>
<button onclick="fetch('APPS_SCRIPT_EXEC_URL?action=ping').then(r=>r.json()).then(j=>out('cors OK '+JSON.stringify(j))).catch(e=>out('cors FAIL '+e))">GET test</button>
<button onclick="fetch('APPS_SCRIPT_EXEC_URL',{method:'POST',headers:{'Content-Type':'text/plain'},body:'{"hi":1}'}).then(r=>r.json()).then(j=>out('post OK '+JSON.stringify(j))).catch(e=>out('post FAIL '+e))">POST test</button>
<h3>3. Mic + Web Speech</h3>
<button onclick="startSR()">start speech recognition</button>
<pre id="o"></pre>
<script>
function out(m){document.getElementById('o').textContent += m + "\n";}
function startSR(){
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if(!SR){ out('SpeechRecognition NOT supported'); return; }
  const r = new SR(); r.lang='en-US';
  r.onresult = (e)=> out('heard: ' + e.results[0][0].transcript);
  r.onerror = (e)=> out('SR error: ' + e.error);
  r.start(); out('listening… say something');
}
</script>
</body></html>
```

把 `frontend/spike.html` 推上 GitHub Pages（或本機用 `python -m http.server` 在 https 工具測；但 mic/SW 需 HTTPS，故最準是 push 到 GitHub Pages 一個臨時路徑）。在 **Android Chrome** 打開，逐項按掣。

- [ ] **Step 4: 記錄結果，決定走向**

驗收（三項全綠才進 Task 2）：
- (1) 撳「seek to 20s」後音檔由 20 秒播起 → ✅；若 link 開唔到 / 撳完冇反應 → 紅。
- (2) GET 印 `cors OK …`、POST 印 `post OK …` → ✅；任一 FAIL → 紅。
- (3) 講嘢後印 `heard: …` → ✅；印 `NOT supported` → 紅（屬 iOS 行為，Android 應綠）。

紅的 fallback（在報告寫明採用哪個，後續 task 依此調整）：
- (1)紅 → 音檔改由 Apps Script proxy（`doGet?action=audio&file=` 回 base64／blob），或 replenisher 切 per-sentence 小檔（需回 Plan 1 補一個 task）。
- (2)POST紅 → 確認用了 `text/plain`；仍紅則改 GET-with-query 寫 progress。
- (3)紅 → 評分退化自我比對（Task 6 的 iOS 分支）。

- [ ] **Step 5: 清理 spike 檔**

```bash
cd "g:/我的雲端硬碟/AI/Shadowing" && git rm -f --ignore-unmatch frontend/spike.html appscript/spike.gs 2>/dev/null; rm -f frontend/spike.html appscript/spike.gs
```
（spike 檔不入正式 commit；若曾 add 才需 git rm。）本 task 無 code commit；把三項結果記入執行報告。

---

## Task 2: `compare.js` — compare.py 的 JS port（TDD）

**Files:**
- Create: `frontend/compare.js`
- Test: `frontend/test/compare.test.js`

**Interfaces:**
- Produces: `Compare.normalize(text) -> string[]`、`Compare.compareSentence(reference, spoken) -> {tokens:[{ref,status}], score}`，status ∈ `ok|wrong|missing|extra`。瀏覽器全域 `Compare`，node `require("../compare.js")`。

- [ ] **Step 1: 寫失敗測試（鏡像 compare.py 的 oracle case）**

`frontend/test/compare.test.js`：

```javascript
const test = require("node:test");
const assert = require("node:assert");
const { compareSentence, normalize } = require("../compare.js");

test("perfect match all ok", () => {
  const r = compareSentence("I'm a horse.", "im a horse");
  assert.deepStrictEqual(r.tokens.map(t => t.status), ["ok", "ok", "ok"]);
  assert.strictEqual(r.score, 1.0);
});

test("tokens carry reference words", () => {
  const r = compareSentence("I'm a horse.", "im a horse");
  assert.deepStrictEqual(r.tokens.map(t => t.ref), ["im", "a", "horse"]);
});

test("missing word marked", () => {
  const r = compareSentence("I am a horse", "I am horse");
  const byRef = {};
  r.tokens.forEach(t => { byRef[t.ref] = t.status; });
  assert.strictEqual(byRef["a"], "missing");
  assert.strictEqual(r.score, 0.75);
});

test("wrong word marked", () => {
  const r = compareSentence("I am a horse", "I am a house");
  const wrong = r.tokens.filter(t => t.status === "wrong");
  const extra = r.tokens.filter(t => t.status === "extra");
  assert.ok(wrong.length && wrong[0].ref === "horse");
  assert.ok(extra.length && extra[0].ref === "house");
});

test("empty spoken all missing", () => {
  const r = compareSentence("hello world", "");
  assert.deepStrictEqual(r.tokens.map(t => t.status), ["missing", "missing"]);
  assert.strictEqual(r.score, 0.0);
});

test("hyphenated word treated as two tokens", () => {
  assert.deepStrictEqual(normalize("well-known fact"), ["well", "known", "fact"]);
});

test("empty reference spoken all extra", () => {
  const r = compareSentence("", "anything said");
  assert.deepStrictEqual(r.tokens.map(t => t.status), ["extra", "extra"]);
  assert.strictEqual(r.score, 0.0);
});

test("both empty returns empty tokens zero score", () => {
  const r = compareSentence("", "");
  assert.deepStrictEqual(r.tokens, []);
  assert.strictEqual(r.score, 0.0);
});
```

- [ ] **Step 2: 跑測試確認 fail**

Run（從 `frontend/`）：`node --test test/compare.test.js`
Expected: FAIL（`Cannot find module '../compare.js'`）。

- [ ] **Step 3: 寫實作**

`frontend/compare.js`：

```javascript
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
```

- [ ] **Step 4: 跑測試確認 pass**

Run（從 `frontend/`）：`node --test test/compare.test.js`
Expected: 8 tests PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/compare.js frontend/test/compare.test.js
git commit -m "feat(booth): compare.js port of compare.py with node tests"
```

---

## Task 3: `practice-core.js` — 揀片 / 進度純邏輯（TDD）

**Files:**
- Create: `frontend/practice-core.js`
- Test: `frontend/test/practice-core.test.js`

**Interfaces:**
- Produces: `PracticeCore.pickNextClip(manifest, doneClips, showId?) -> {show, clip} | null`、`PracticeCore.markDone(progress, clipId) -> progress`。

- [ ] **Step 1: 寫失敗測試**

`frontend/test/practice-core.test.js`：

```javascript
const test = require("node:test");
const assert = require("node:assert");
const { pickNextClip, markDone } = require("../practice-core.js");

const manifest = {
  shows: [
    { id: "bojack", name: "BoJack", clips: [{ clip_id: "a" }, { clip_id: "b" }] },
    { id: "simpsons", name: "Simpsons", clips: [{ clip_id: "c" }] },
  ],
};

test("pick first unplayed across shows", () => {
  const r = pickNextClip(manifest, ["a"]);
  assert.strictEqual(r.clip.clip_id, "b");
  assert.strictEqual(r.show.id, "bojack");
});

test("pick respects showId filter", () => {
  const r = pickNextClip(manifest, ["a", "b"], "simpsons");
  assert.strictEqual(r.clip.clip_id, "c");
});

test("pick returns null when all done", () => {
  assert.strictEqual(pickNextClip(manifest, ["a", "b", "c"]), null);
});

test("markDone adds clip id once", () => {
  const p = { version: 1, done_clips: [], attempts: [] };
  markDone(p, "a");
  markDone(p, "a");
  assert.deepStrictEqual(p.done_clips, ["a"]);
});
```

- [ ] **Step 2: 跑測試確認 fail**

Run（從 `frontend/`）：`node --test test/practice-core.test.js`
Expected: FAIL（module not found）。

- [ ] **Step 3: 寫實作**

`frontend/practice-core.js`：

```javascript
// 純邏輯：揀下一條未練 clip、標記練完。UMD-lite。
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PracticeCore = api;
})(typeof self !== "undefined" ? self : this, function () {
  function pickNextClip(manifest, doneClips, showId) {
    const done = new Set(doneClips || []);
    for (const show of manifest.shows || []) {
      if (showId && show.id !== showId) continue;
      for (const clip of show.clips || []) {
        if (!done.has(clip.clip_id)) return { show, clip };
      }
    }
    return null;
  }

  function markDone(progress, clipId) {
    if (!progress.done_clips) progress.done_clips = [];
    if (progress.done_clips.indexOf(clipId) === -1) progress.done_clips.push(clipId);
    return progress;
  }

  return { pickNextClip, markDone };
});
```

- [ ] **Step 4: 跑測試確認 pass**

Run（從 `frontend/`）：`node --test test/practice-core.test.js`
Expected: 4 tests PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/practice-core.js frontend/test/practice-core.test.js
git commit -m "feat(booth): practice-core pick-next-clip and mark-done helpers"
```

---

## Task 4: Apps Script `Code.gs` — manifest / progress API（實作 + 手動驗證）

**Files:**
- Create: `appscript/Code.gs`
- Create: `appscript/appsscript.json`

**Interfaces:**
- Produces（HTTP）：`GET ?action=manifest` → manifest（每 clip 增補 `audio_url`）；`GET ?action=progress` → progress；`POST`（body=JSON, Content-Type text/plain）`{clip_id, attempt?}` → 更新 progress，回 `{ok:true, done_clips:N}`。

> GAS 無本機單元測試環境；本 task 以「部署後對端點手動 fetch」驗證。

- [ ] **Step 1: 寫 `appscript/appsscript.json`**

```json
{
  "timeZone": "Asia/Hong_Kong",
  "exceptionLogging": "STACKDRIVER",
  "runtimeVersion": "V8",
  "webapp": { "executeAs": "USER_DEPLOYING", "access": "ANYONE_ANONYMOUS" }
}
```

- [ ] **Step 2: 寫 `appscript/Code.gs`**

```javascript
// Apps Script web app：以「你」的身份讀寫你 Drive 的 library 資料夾。
// 部署：Deploy > New deployment > Web app；Execute as Me；Who has access Anyone。
// 把 LIBRARY_FOLDER_ID 換成 Drive 上 library 資料夾（含 manifest.json / progress.json / audio/）的 ID。
var LIBRARY_FOLDER_ID = "PASTE_DRIVE_LIBRARY_FOLDER_ID";

function _folder() { return DriveApp.getFolderById(LIBRARY_FOLDER_ID); }

function _fileByName(folder, name) {
  var it = folder.getFilesByName(name);
  return it.hasNext() ? it.next() : null;
}

function _readJson(folder, name, fallback) {
  var f = _fileByName(folder, name);
  if (!f) return fallback;
  return JSON.parse(f.getBlob().getDataAsString());
}

function _writeJson(folder, name, obj) {
  var f = _fileByName(folder, name);
  var content = JSON.stringify(obj);
  if (f) f.setContent(content);
  else folder.createFile(name, content, "application/json");
}

function _audioFolder(folder) {
  var it = folder.getFoldersByName("audio");
  return it.hasNext() ? it.next() : null;
}

function _audioUrl(audioFolder, audioFile) {
  if (!audioFolder || !audioFile) return null;
  var it = audioFolder.getFilesByName(audioFile);
  if (!it.hasNext()) return null;
  var f = it.next();
  f.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
  return "https://drive.google.com/uc?export=download&id=" + f.getId();
}

function _json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  var action = (e && e.parameter && e.parameter.action) || "manifest";
  var folder = _folder();
  if (action === "progress") {
    return _json(_readJson(folder, "progress.json",
      { version: 1, done_clips: [], attempts: [] }));
  }
  var manifest = _readJson(folder, "manifest.json",
    { version: 1, updated_at: null, shows: [] });
  var audio = _audioFolder(folder);
  (manifest.shows || []).forEach(function (show) {
    (show.clips || []).forEach(function (clip) {
      clip.audio_url = _audioUrl(audio, clip.audio_file);
    });
  });
  return _json(manifest);
}

function doPost(e) {
  var folder = _folder();
  var body = JSON.parse(e.postData.contents);   // {clip_id, attempt?}
  var progress = _readJson(folder, "progress.json",
    { version: 1, done_clips: [], attempts: [] });
  if (body.clip_id && progress.done_clips.indexOf(body.clip_id) === -1) {
    progress.done_clips.push(body.clip_id);
  }
  if (body.attempt) progress.attempts.push(body.attempt);
  _writeJson(folder, "progress.json", progress);
  return _json({ ok: true, done_clips: progress.done_clips.length });
}
```

- [ ] **Step 3: 部署並取得 library 資料夾 ID**

1. 確認 Drive 上 `backend/data/library` 已同步（含 `manifest.json` 與 `audio/`）。若 manifest 空，先在本機跑一次 `python -m app.replenish`（見 Plan 1）讓它有內容。
2. 在 Drive 找到該 `library` 資料夾，URL 中 `folders/` 後的字串就是 ID。貼進 `Code.gs` 的 `LIBRARY_FOLDER_ID`。
3. script.google.com 新建專案 → 貼上 `Code.gs` 與專案設定 → Deploy → New deployment → Web app（Execute as Me、Anyone）→ 授權 Drive 權限 → 複製 `/exec` URL。

- [ ] **Step 4: 手動驗證端點**

在電腦瀏覽器：
- 開 `<EXEC_URL>?action=manifest` → 應見 JSON，且每條 clip 有非 null 的 `audio_url`。把該 `audio_url` 貼到新分頁，應能下載/播到音檔。
- 開 `<EXEC_URL>?action=progress` → 應見 `{version:1, done_clips:[], attempts:[]}`（或現有進度）。
- POST 測試（瀏覽器 console）：
```js
fetch("<EXEC_URL>", {method:"POST", headers:{"Content-Type":"text/plain"}, body: JSON.stringify({clip_id:"__test__"})}).then(r=>r.json()).then(console.log)
```
應回 `{ok:true, done_clips:N}`；再開 `?action=progress` 應見 `__test__` 已在 `done_clips`。**驗證後把 `__test__` 從 Drive 的 progress.json 移除**（或忽略，replenisher 不受影響）。

- [ ] **Step 5: Commit**

```bash
git add appscript/Code.gs appscript/appsscript.json
git commit -m "feat(booth): apps script JSON API for manifest/progress over drive"
```

記下 `EXEC_URL`，Task 5 的 `config.js` 要用。

---

## Task 5: PWA — index.html + config.js + app.js 整合（實作 + 手動驗證）

**Files:**
- Create: `frontend/config.js`
- Modify: `frontend/index.html`（整檔重寫）
- Modify: `frontend/app.js`（整檔重寫）

**Interfaces:**
- Consumes: `Compare.compareSentence`（Task 2）、`PracticeCore.pickNextClip` / `markDone`（Task 3）、`window.API_BASE`（config.js）。
- Apps Script 端點：`GET ?action=manifest|progress`、`POST`（text/plain）。

- [ ] **Step 1: 寫 `frontend/config.js`**

```javascript
// 部署時把 API_BASE 換成 Task 4 的 Apps Script /exec URL。
window.API_BASE = "PASTE_APPS_SCRIPT_EXEC_URL";
```

- [ ] **Step 2: 重寫 `frontend/index.html`（相對路徑 + 新 script）**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Shadowing</title>
  <link rel="manifest" href="./manifest.webmanifest" />
  <link rel="stylesheet" href="./style.css" />
</head>
<body>
  <header><h1>Shadowing</h1></header>

  <section id="show-picker">
    <h2>揀一套劇</h2>
    <div id="shows" class="shows"></div>
    <p id="status" class="status"></p>
  </section>

  <section id="practice" hidden>
    <p id="material-title" class="title"></p>
    <p id="progress" class="progress"></p>

    <blockquote id="ref-text" class="ref"></blockquote>

    <div class="controls">
      <button id="play-orig">▶ 播原句</button>
      <label><input type="checkbox" id="slow" /> 0.75x 慢放</label>
      <label><input type="checkbox" id="loop" /> Loop</label>
    </div>

    <div class="controls">
      <button id="record">● 錄跟讀</button>
      <button id="play-mine" disabled>▶ 聽返自己</button>
    </div>

    <div id="result" class="result" hidden>
      <p class="score">分數：<span id="score"></span></p>
      <p id="tokens" class="tokens"></p>
    </div>

    <div class="controls">
      <button id="mark-pass">✓ 過咗，下一句</button>
      <button id="mark-retry">↻ 再練</button>
    </div>
  </section>

  <audio id="orig-audio" preload="auto"></audio>
  <script src="./config.js"></script>
  <script src="./compare.js"></script>
  <script src="./practice-core.js"></script>
  <script src="./app.js"></script>
  <script>
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("./sw.js");
  </script>
</body>
</html>
```

- [ ] **Step 3: 重寫 `frontend/app.js`**

```javascript
const API = window.API_BASE;
let manifest = null;
let progress = { version: 1, done_clips: [], attempts: [] };
let current = null;   // {show, clip}
let idx = 0;
let mediaRecorder = null, recordedChunks = [], myAudioUrl = null;
let recognition = null, lastSpoken = "";

const $ = (id) => document.getElementById(id);

async function boot() {
  $("status").textContent = "載入緊片庫…";
  try {
    const [m, p] = await Promise.all([
      fetch(`${API}?action=manifest`).then((r) => r.json()),
      fetch(`${API}?action=progress`).then((r) => r.json()),
    ]);
    manifest = m;
    progress = p && p.done_clips ? p : progress;
  } catch (e) {
    $("status").textContent = "✗ 載入失敗，請檢查網絡或稍後再試。";
    return;
  }
  renderShows();
}

function renderShows() {
  const wrap = $("shows");
  wrap.innerHTML = "";
  (manifest.shows || []).forEach((s) => {
    const unplayed = s.clips.filter(
      (c) => progress.done_clips.indexOf(c.clip_id) === -1).length;
    const b = document.createElement("button");
    b.textContent = `${s.name}（未練 ${unplayed}）`;
    b.disabled = unplayed === 0;
    b.onclick = () => startShow(s.id);
    wrap.appendChild(b);
  });
  if (!(manifest.shows || []).some((s) =>
      s.clips.some((c) => progress.done_clips.indexOf(c.clip_id) === -1))) {
    $("status").textContent = "片庫暫時冇未練嘅片，等磨片廠補片。";
  }
}

function startShow(showId) {
  current = PracticeCore.pickNextClip(manifest, progress.done_clips, showId);
  if (!current) { renderShows(); return; }
  idx = 0;
  $("show-picker").hidden = true;
  $("practice").hidden = false;
  $("material-title").textContent = current.clip.title;
  $("orig-audio").src = current.clip.audio_url;
  loadSentence();
}

function loadSentence() {
  const s = current.clip.sentences[idx];
  $("ref-text").textContent = s.text;
  $("progress").textContent = `第 ${idx + 1} / ${current.clip.sentences.length} 句`;
  $("result").hidden = true;
  $("play-mine").disabled = true;
}

// 單一 timeupdate listener，永遠讀「當前句」的 end
function bindSegmentStop() {
  const a = $("orig-audio");
  if (a._stopBound) return;
  a.addEventListener("timeupdate", () => {
    const cur = current && current.clip.sentences[idx];
    if (!cur) return;
    if (a.currentTime >= cur.end) {
      if ($("loop").checked) a.currentTime = cur.start;
      else a.pause();
    }
  });
  a._stopBound = true;
}

$("play-orig").onclick = () => {
  const s = current.clip.sentences[idx];
  const a = $("orig-audio");
  a.playbackRate = $("slow").checked ? 0.75 : 1.0;
  bindSegmentStop();
  const seek = () => { try { a.currentTime = s.start; } catch (_) {} };
  if (a.readyState >= 1) seek();
  else a.addEventListener("loadedmetadata", seek, { once: true });
  const p = a.play();
  if (p && p.catch) p.catch((err) => {
    $("status").textContent = "▶ 播放被擋，請再撳一次：" + err.message;
  });
};

// 錄跟讀：Web Speech API 即時 STT（評分）+ MediaRecorder（聽返自己）
$("record").onclick = async () => {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (mediaRecorder && mediaRecorder.state === "recording") { stopRecording(); return; }

  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch { alert("冇咪權限：請喺瀏覽器允許麥克風。"); return; }

  recordedChunks = [];
  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.ondataavailable = (e) => recordedChunks.push(e.data);
  mediaRecorder.onstop = () => {
    stream.getTracks().forEach((t) => t.stop());
    $("record").textContent = "● 錄跟讀";
    const blob = new Blob(recordedChunks, { type: "audio/webm" });
    if (myAudioUrl) URL.revokeObjectURL(myAudioUrl);
    myAudioUrl = URL.createObjectURL(blob);
    $("play-mine").disabled = false;
  };
  mediaRecorder.start();
  $("record").textContent = "■ 停止";

  lastSpoken = "";
  if (SR) {
    recognition = new SR();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.onresult = (e) => {
      lastSpoken = Array.from(e.results).map((r) => r[0].transcript).join(" ");
    };
    recognition.onerror = () => {};
    recognition.start();
  }
};

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") mediaRecorder.stop();
  if (recognition) { try { recognition.stop(); } catch (_) {} }
  setTimeout(score, 300);   // 等 onresult 收尾
}

function score() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    $("status").textContent = "（此瀏覽器唔支援語音辨識，淨係可以聽返自己對比。）";
    return;
  }
  const ref = current.clip.sentences[idx].text;
  const result = Compare.compareSentence(ref, lastSpoken);
  renderResult(result);
}

function renderResult(body) {
  $("score").textContent = Math.round(body.score * 100) + "%";
  const tEl = $("tokens");
  tEl.innerHTML = "";
  body.tokens.forEach((t) => {
    const span = document.createElement("span");
    span.textContent = t.ref + " ";
    span.className = "tok-" + t.status;
    tEl.appendChild(span);
  });
  $("result").hidden = false;
}

$("play-mine").onclick = () => { if (myAudioUrl) new Audio(myAudioUrl).play(); };

$("mark-pass").onclick = nextSentence;
$("mark-retry").onclick = () => { $("result").hidden = true; $("play-mine").disabled = true; };

function nextSentence() {
  if (idx + 1 < current.clip.sentences.length) { idx++; loadSentence(); return; }
  // clip 練完：標 done + 回寫 progress
  PracticeCore.markDone(progress, current.clip.clip_id);
  postProgress(current.clip.clip_id);
  $("ref-text").textContent = "🎉 呢條片練完！返去揀過。";
  $("result").hidden = true;
  setTimeout(() => {
    $("practice").hidden = true;
    $("show-picker").hidden = false;
    renderShows();
  }, 1200);
}

function postProgress(clipId) {
  fetch(API, {
    method: "POST",
    headers: { "Content-Type": "text/plain;charset=utf-8" },  // 避開 CORS preflight
    body: JSON.stringify({ clip_id: clipId }),
  }).catch(() => {});   // 失敗唔阻練習；下次 boot 會重攞 progress
}

boot();
```

> 註：`record` 掣是 toggle —— `$("record").onclick` 開頭 `if (mediaRecorder && mediaRecorder.state === "recording") { stopRecording(); return; }` 處理「停止」分支（停錄音、停辨識、`score()`）；否則行「開始」分支（錄音 + 開 SpeechRecognition）。

- [ ] **Step 4: 手動驗證（本機 + 部署）**

先把 `config.js` 的 `API_BASE` 設為 Task 4 的 EXEC_URL。因 mic/SW 需 HTTPS，最準是 push 上 GitHub Pages（見 Task 7）後在 Android 測；本機可先用桌面 Chrome 對 `http://localhost` 測非 mic 部分：
1. 載入頁面 → 應見每套劇按鈕帶「未練 N」。
2. 撳一套劇 → 入練習頁、顯示第一句、`<audio>` src 指向 Drive `audio_url`。
3. 撳「▶ 播原句」→ 由該句 `start` 播到 `end` 停（慢放/loop 可用）。
（mic/評分/Web Speech 在 Task 7 的 Android 端到端驗。）

- [ ] **Step 5: Commit**

```bash
git add frontend/config.js frontend/index.html frontend/app.js
git commit -m "feat(booth): PWA shell + manifest-driven practice + web speech scoring"
```

---

## Task 6: service worker + manifest（離線 + 安裝，實作 + 手動驗證）

**Files:**
- Modify: `frontend/sw.js`
- Modify: `frontend/manifest.webmanifest`

- [ ] **Step 1: 重寫 `frontend/sw.js`（相對路徑 + cache 音檔）**

```javascript
// 相對路徑 shell（GitHub Pages 子路徑）；network-first 取最新，離線用 cache。
// 音檔（Drive 跨 origin）以 cache-first 存起，令離線可重播近期 clip。
const CACHE = "shadowing-v3";
const SHELL = ["./", "./index.html", "./app.js", "./compare.js",
               "./practice-core.js", "./config.js", "./style.css",
               "./manifest.webmanifest"];

self.addEventListener("install", (e) => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // Drive 音檔：cache-first（離線可重播）
  if (url.hostname.indexOf("drive.google.com") !== -1 ||
      url.hostname.indexOf("googleusercontent.com") !== -1) {
    e.respondWith(
      caches.match(e.request).then((hit) => hit || fetch(e.request).then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
        return resp;
      }))
    );
    return;
  }
  // Apps Script API：一律走網絡（要最新 manifest/progress）
  if (url.href.indexOf("script.google.com") !== -1) return;
  // 其餘（shell）：network-first，離線用 cache
  e.respondWith(
    fetch(e.request).then((resp) => {
      const copy = resp.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
      return resp;
    }).catch(() => caches.match(e.request))
  );
});
```

- [ ] **Step 2: 改 `frontend/manifest.webmanifest` 的 start_url 為相對**

把 `"start_url": "/"` 改為 `"start_url": "."`（其餘不變）。

- [ ] **Step 3: 手動驗證（Task 7 部署後在 Android）**

1. 首次載入後，離線（飛行模式）重開 → app shell 仍開到、已 cache 的 clip 仍播到。
2. Chrome 選單見「安裝應用程式 / 加到主畫面」。

- [ ] **Step 4: Commit**

```bash
git add frontend/sw.js frontend/manifest.webmanifest
git commit -m "feat(booth): service worker caches shell + drive audio, relative paths"
```

---

## Task 7: 部署 + Android 端到端 smoke（手動）

**Files:** 無（部署設定）

- [ ] **Step 1: 設定 config 並開 GitHub Pages**

1. 確認 `frontend/config.js` 的 `API_BASE` = Task 4 的 EXEC_URL，已 commit。
2. GitHub repo `wyho1029/Shadowing` → Settings → Pages → Source 選 `Deploy from a branch`，branch 選含本前端的分支、資料夾選 `/frontend`（若 Pages 只接受 `/` 或 `/docs`，則把 `frontend/` 內容複製到 `/docs` 或用 `gh-pages` 分支發佈；實作時擇一，記錄於報告）。
3. 等 Pages 發佈，得到 `https://wyho1029.github.io/Shadowing/`。

- [ ] **Step 2: Android Chrome 端到端**

開 `https://wyho1029.github.io/Shadowing/`：
1. 見劇列表（帶未練數）→ 撳一套 → 顯示第一句。
2. 撳「▶ 播原句」→ 由 Drive 音檔該句播到停（慢放/loop 可用）。
3. 撳「● 錄跟讀」→ 允許麥克風 → 讀出該句 → 撳「■ 停止」→ 見分數 + 逐字 token 着色；撳「▶ 聽返自己」可重播自己。
4. 撳「✓ 過咗，下一句」到最後一句 → clip 標 done。
5. 回 Drive 開 `library/progress.json`（或 `<EXEC_URL>?action=progress`）→ 確認該 `clip_id` 已入 `done_clips`。
6. 下次 Plan 1 cron 跑（或手動 `python -m app.replenish`）→ 確認該劇因少了一條未練而補片。

- [ ] **Step 3: 驗收 + 記錄**

把上述每步結果（特別是評分是否合理、progress 是否回寫、閉環是否成立）記入執行報告。若有 spike fallback 被採用，一併記下。

---

## Self-Review（已對 spec 核對）

- **Spec §3 三件式架構**：PWA（Task 5/6/7）、Apps Script API（Task 4）、Drive 音檔 link（Task 4 `_audioUrl`）。
- **Spec §4 client 模組**：主邏輯（Task 5）、compare.js（Task 2）、practice-core（Task 3）、service worker（Task 6）、iOS 退化（Task 5 `score()` 的 `!SR` 分支）。
- **Spec §5 資料契約**：`audio_file`→`audio_url`（Task 4）；progress mark done + 回寫（Task 5 `postProgress` + Task 4 doPost）。
- **Spec §6 spike**：Task 1 三項 + fallback。
- **Spec §7 錯誤處理**：manifest fetch 失敗（Task 5 boot catch）、無未練（renderShows 提示）、音檔載入失敗（沿用 play catch）、無 Web Speech 退化（score `!SR`）、離線（Task 6 SW）、progress 原子寫（Task 4 `_writeJson` 以 setContent；GAS 單檔寫入本身原子）。
- **Spec §8 測試**：compare.js（Task 2，oracle）、純函式（Task 3）、GAS/PWA 手動（Task 4/5/6/7）。
- **Global Constraints**：相對路徑（Task 5/6）、POST text/plain（Task 5 `postProgress` + Task 4）、`<audio>` 整條載入+seek（Task 5 play-orig）、compare 一致（Task 2）。
- **Placeholder scan**：所有 code step 有完整 code；`PASTE_*` 是部署時必填的真實值（config.js API_BASE、Code.gs LIBRARY_FOLDER_ID），已在對應 step 指明來源，非 TBD。
- **型別一致**：`pickNextClip`/`markDone`/`compareSentence`/`normalize` 簽名跨 Task 2/3/5 一致；manifest/clip/progress 形狀跨 Task 4/5 與 Plan 1 一致。
