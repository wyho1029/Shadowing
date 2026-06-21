const API = window.API_BASE;
let manifest = null;
let progress = { version: 1, done_clips: [], attempts: [] };
let current = null;   // {show, clip}
let idx = 0;
let mediaRecorder = null, recordedChunks = [], myAudioUrl = null;
let recognition = null, lastSpoken = "", listening = false;

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
  const savedIdx = loadSentProgress()[current.clip.clip_id] || 0;
  idx = Math.min(savedIdx, current.clip.sentences.length - 1);   // resume 到上次嗰句
  $("show-picker").hidden = true;
  $("practice").hidden = false;
  $("material-title").textContent = current.clip.title;
  $("orig-audio").src = "./audio/" + current.clip.audio_file;  // 同源（GitHub Pages），Drive link 喺瀏覽器播唔到
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
  if (!SR) {
    $("status").textContent = "呢個瀏覽器唔支援語音辨識，請用 Chrome。";
    return;
  }
  if (listening) {                 // 第二下撳 = 停止辨識
    try { recognition.stop(); } catch (_) {}
    return;
  }

  // 評分淨用 Web Speech（唔同時開 MediaRecorder，避免 Android 上爭麥克風 → 收唔到聲 → 0%）
  lastSpoken = "";
  recognition = new SR();
  recognition.lang = "en-US";
  recognition.interimResults = true;   // 即時顯示，亦方便睇到有冇收到聲
  recognition.continuous = true;
  recognition.onresult = (e) => {
    lastSpoken = Array.from(e.results).map((r) => r[0].transcript).join(" ").trim();
    $("status").textContent = "聽到：" + lastSpoken;
  };
  recognition.onerror = (e) => { $("status").textContent = "辨識出錯：" + e.error; };
  recognition.onend = () => {
    listening = false;
    $("record").textContent = "● 錄跟讀";
    $("record").classList.remove("recording");
    score();
  };
  recognition.start();
  listening = true;
  $("record").textContent = "■ 停止";
  $("record").classList.add("recording");
  $("status").textContent = "聽緊…請讀出嗰句";
};

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
  const clipId = current.clip.clip_id;
  if (idx + 1 < current.clip.sentences.length) {
    idx++;
    saveSentProgress(clipId, idx);            // 記返 resume 點（同機 localStorage）
    loadSentence();
    return;
  }
  // clip 練完：標 done（Drive）+ 記晒
  PracticeCore.markDone(progress, clipId);
  saveSentProgress(clipId, current.clip.sentences.length);
  postProgress(clipId);
  $("ref-text").textContent = "🎉 呢條片練完！返去揀過。";
  $("result").hidden = true;
  setTimeout(goHome, 1200);
}

function postProgress(clipId) {
  fetch(API, {
    method: "POST",
    headers: { "Content-Type": "text/plain;charset=utf-8" },  // 避開 CORS preflight
    body: JSON.stringify({ clip_id: clipId }),
  }).catch(() => {});   // 失敗唔阻練習；下次 boot 會重攞 progress
}

// ── 句子進度（localStorage，同機 resume）+ 返主頁 ───────────────────────────
const SENT_KEY = "shadowing_sentence_progress";
function loadSentProgress() {
  try { return JSON.parse(localStorage.getItem(SENT_KEY)) || {}; } catch (_) { return {}; }
}
function saveSentProgress(clipId, nextIdx) {
  const p = loadSentProgress();
  p[clipId] = nextIdx;
  try { localStorage.setItem(SENT_KEY, JSON.stringify(p)); } catch (_) {}
}

function goHome() {
  try { $("orig-audio").pause(); } catch (_) {}
  $("practice").hidden = true;
  $("show-picker").hidden = false;
  renderShows();
}
$("home-btn").onclick = goHome;

boot();
