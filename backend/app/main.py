import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import compare, segmenter, shows, transcribe, youtube
from app.config import AUDIO_DIR, DB_PATH
from app.db import Database

app = FastAPI(title="Shadowing")
db = Database(DB_PATH)

# 一句達到呢個比例先算「過咗」，否則叫使用者再練
PASS_THRESHOLD = 0.8


@app.get("/api/shows")
def api_shows():
    return shows.list_shows()


@app.post("/api/materials")
def api_create_material(show_id: str):
    try:
        query = shows.get_search_query(show_id)
    except KeyError:
        raise HTTPException(404, f"unknown show: {show_id}")

    clip = youtube.find_clip(query)
    if clip is None:
        raise HTTPException(404, "呢套劇暫時搵唔到啱嘅片，試下另一套")

    raw = transcribe.transcribe_segments(clip["audio_path"])
    sentences = segmenter.segment_transcript(raw)
    if not sentences:
        raise HTTPException(422, "呢條片切唔到句子，試下另一套")

    mid = db.add_material(show_id, clip["title"],
                          clip["youtube_id"], clip["audio_path"])
    db.add_sentences(mid, sentences)
    return {
        "material_id": mid,
        "youtube_id": clip["youtube_id"],
        "title": clip["title"],
        "sentences": db.get_sentences(mid),
    }


@app.post("/api/attempts")
async def api_attempt(sentence_id: int = Form(...), audio: UploadFile = File(...)):
    suffix = Path(audio.filename or "rec.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(audio.file, tmp)
        tmp_path = tmp.name

    try:
        spoken = transcribe.transcribe_text(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    ref_text = db.get_sentence_text(sentence_id)
    if ref_text is None:
        raise HTTPException(404, "sentence not found")

    result = compare.compare_sentence(ref_text, spoken)
    status = "pass" if result["score"] >= PASS_THRESHOLD else "retry"
    db.record_attempt(sentence_id, result["score"], status)
    return {"spoken": spoken, "tokens": result["tokens"],
            "score": result["score"], "status": status}


@app.get("/api/audio/{youtube_id}")
def api_audio(youtube_id: str):
    for f in AUDIO_DIR.glob(f"{youtube_id}.*"):
        return FileResponse(str(f))
    raise HTTPException(404, "audio not found")


# 前端靜態檔（最後 mount，唔好食咗 /api）
_frontend = Path(__file__).resolve().parent.parent.parent / "frontend"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")
