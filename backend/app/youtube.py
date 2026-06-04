from pathlib import Path

import yt_dlp

from app.config import AUDIO_DIR

MIN_DURATION = 30      # 秒
MAX_DURATION = 600     # 秒（10 分鐘）


def _has_english_subs(entry: dict) -> bool:
    subs = entry.get("subtitles") or {}
    auto = entry.get("automatic_captions") or {}
    return any(k.startswith("en") for k in subs) or \
           any(k.startswith("en") for k in auto)


def pick_candidate(entries: list[dict]) -> dict | None:
    """喺搜尋結果揀第一個：有英文字幕、長度合理嘅。"""
    for e in entries:
        dur = e.get("duration") or 0
        if MIN_DURATION <= dur <= MAX_DURATION and _has_english_subs(e):
            return e
    return None


def search(query: str, limit: int = 10) -> list[dict]:
    """ytsearch 攞 metadata（唔下載）。"""
    opts = {"quiet": True, "skip_download": True, "extract_flat": False}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    return info.get("entries", []) if info else []


def download_audio(youtube_id: str) -> Path:
    """抽單一影片嘅音檔（m4a），回傳本機路徑。"""
    out_tmpl = str(AUDIO_DIR / "%(id)s.%(ext)s")
    opts = {
        "quiet": True,
        "format": "bestaudio[ext=m4a]/bestaudio",
        "outtmpl": out_tmpl,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(
            f"https://www.youtube.com/watch?v={youtube_id}", download=True
        )
    return Path(ydl.prepare_filename(info))


def find_clip(query: str) -> dict | None:
    """搜尋 → 揀 candidate → 下載音檔。回傳 dict 或 None。

    包住錯誤：個別 entry 抽唔到就 skip。
    """
    entries = search(query)
    candidate = pick_candidate(entries)
    if candidate is None:
        return None
    try:
        audio_path = download_audio(candidate["id"])
    except Exception:
        return None
    return {
        "youtube_id": candidate["id"],
        "title": candidate.get("title", candidate["id"]),
        "audio_path": str(audio_path),
    }
