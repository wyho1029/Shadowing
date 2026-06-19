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
