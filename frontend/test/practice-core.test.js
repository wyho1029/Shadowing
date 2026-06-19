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
