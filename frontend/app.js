const API = "";  // 同源
let selectedShow = null;
let material = null;       // {material_id, youtube_id, title, sentences}
let idx = 0;
let mediaRecorder = null;
let recordedChunks = [];
let myAudioUrl = null;

const $ = (id) => document.getElementById(id);

async function loadShows() {
  const res = await fetch(`${API}/api/shows`);
  const shows = await res.json();
  const wrap = $("shows");
  wrap.innerHTML = "";
  shows.forEach((s) => {
    const b = document.createElement("button");
    b.textContent = s.name;
    b.onclick = () => {
      selectedShow = s.id;
      [...wrap.children].forEach((c) => c.classList.remove("selected"));
      b.classList.add("selected");
      $("find-btn").disabled = false;
    };
    wrap.appendChild(b);
  });
}

$("find-btn").onclick = async () => {
  $("status").textContent = "搵緊片同處理緊…（第一次載 Whisper model 會耐少少）";
  $("find-btn").disabled = true;
  try {
    const res = await fetch(`${API}/api/materials?show_id=${selectedShow}`,
                            { method: "POST" });
    if (!res.ok) {
      const err = await res.json();
      $("status").textContent = "✗ " + (err.detail || "出錯，試下另一套");
      $("find-btn").disabled = false;
      return;
    }
    material = await res.json();
    idx = 0;
    $("show-picker").hidden = true;
    $("practice").hidden = false;
    $("material-title").textContent = material.title;
    $("orig-audio").src = `${API}/api/audio/${material.youtube_id}`;
    loadSentence();
  } catch (e) {
    $("status").textContent = "✗ 網絡或伺服器出錯：" + e.message;
    $("find-btn").disabled = false;
  }
};

function loadSentence() {
  const s = material.sentences[idx];
  $("ref-text").textContent = s.text;
  $("progress").textContent = `第 ${idx + 1} / ${material.sentences.length} 句`;
  $("result").hidden = true;
  $("play-mine").disabled = true;
}

$("play-orig").onclick = () => {
  const s = material.sentences[idx];
  const a = $("orig-audio");
  const stopAt = () => {
    if (a.currentTime >= s.end) {
      if ($("loop").checked) { a.currentTime = s.start; }
      else { a.pause(); a.removeEventListener("timeupdate", stopAt); }
    }
  };
  const start = () => {
    a.playbackRate = $("slow").checked ? 0.75 : 1.0;
    a.currentTime = s.start;   // 一定要 metadata 載好先 seek，否則會被夾到 0
    a.addEventListener("timeupdate", stopAt);
    a.play();
  };
  // readyState < 1 代表 metadata 未載好，seek 會失效 → 等 loadedmetadata 先播
  if (a.readyState < 1) {
    a.addEventListener("loadedmetadata", start, { once: true });
    a.load();
  } else {
    start();
  }
};

$("record").onclick = async () => {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    alert("冇咪權限：請喺瀏覽器允許麥克風使用。");
    return;
  }
  recordedChunks = [];
  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.ondataavailable = (e) => recordedChunks.push(e.data);
  mediaRecorder.onstop = () => {
    stream.getTracks().forEach((t) => t.stop());
    $("record").classList.remove("recording");
    $("record").textContent = "● 錄跟讀";
    const blob = new Blob(recordedChunks, { type: "audio/webm" });
    if (myAudioUrl) URL.revokeObjectURL(myAudioUrl);
    myAudioUrl = URL.createObjectURL(blob);
    $("play-mine").disabled = false;
    submitAttempt(blob);
  };
  mediaRecorder.start();
  $("record").classList.add("recording");
  $("record").textContent = "■ 停止";
};

$("play-mine").onclick = () => {
  if (myAudioUrl) new Audio(myAudioUrl).play();
};

async function submitAttempt(blob) {
  const s = material.sentences[idx];
  const fd = new FormData();
  fd.append("sentence_id", String(s.id));
  fd.append("audio", blob, "rec.webm");
  $("status").textContent = "對比緊…";
  const res = await fetch(`${API}/api/attempts`, { method: "POST", body: fd });
  $("status").textContent = "";
  const body = await res.json();
  renderResult(body);
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

function nextSentence() {
  if (idx + 1 < material.sentences.length) { idx++; loadSentence(); }
  else { $("ref-text").textContent = "🎉 呢條片練完！返去揀過套劇。";
         $("result").hidden = true; }
}

$("mark-pass").onclick = nextSentence;
$("mark-retry").onclick = () => { $("result").hidden = true;
                                  $("play-mine").disabled = true; };

loadShows();
