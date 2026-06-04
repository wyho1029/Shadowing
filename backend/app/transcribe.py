from app.config import WHISPER_MODEL

_model = None


def _get_model():
    """Lazy load：第一次叫先載 model（避免 import 即慢/即佔記憶體）。"""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    return _model


def transcribe_segments(audio_path: str) -> list[dict]:
    """轉成 [{text, start, end}, ...] 餵 segmenter。"""
    model = _get_model()
    segments, _info = model.transcribe(audio_path, language="en")
    return [
        {"text": s.text.strip(), "start": float(s.start), "end": float(s.end)}
        for s in segments
    ]


def transcribe_text(audio_path: str) -> str:
    """轉成一串純文字，餵 compare。"""
    segs = transcribe_segments(audio_path)
    return " ".join(s["text"] for s in segs).strip()
