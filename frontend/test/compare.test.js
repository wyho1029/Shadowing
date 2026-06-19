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
