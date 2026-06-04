"""Bilibili 片源：每套劇綁一條「多 P 合集」BV URL（例如 curated 嘅 shadowing 系列）。

同 YouTube 唔同，Bilibili 一條 BV 入面有好多分 P（集）。我哋隨機抽一集、抽佢音檔，
畀 Whisper 轉文字切句。要 cookies（見 config.YTDLP_COOKIE_FILE）先過到 Bilibili 412。
抽唔到（冇 cookies / 412 / 網絡）就回 None，等上層 fallback 去 YouTube。
"""
import random

import yt_dlp

from app.config import AUDIO_DIR
from app.youtube import _base_opts


def part_count(collection_url: str) -> int:
    """數合集入面有幾多集（分 P）。失敗回 0。"""
    opts = {**_base_opts(), "extract_flat": "in_playlist"}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(collection_url, download=False)
    except yt_dlp.utils.DownloadError:
        return 0
    if not info:
        return 0
    return len([e for e in (info.get("entries") or []) if e])


def find_clip(collection_url: str) -> dict | None:
    """喺合集隨機抽一集，下載音檔。回傳 {youtube_id, title, audio_path} 或 None。

    （沿用 youtube.find_clip 嘅 dict 形狀，畀上層 / DB 一視同仁。）
    """
    n = part_count(collection_url)
    if n == 0:
        return None

    part = random.randint(1, n)
    opts = {
        **_base_opts(),
        "format": "bestaudio[ext=m4a]/bestaudio",
        "outtmpl": str(AUDIO_DIR / "%(id)s.%(ext)s"),
        "playlist_items": str(part),
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(collection_url, download=True)
            entry = (info.get("entries") or [None])[0] if info else None
            if not entry:
                return None
            audio_path = ydl.prepare_filename(entry)
    except Exception:
        return None

    return {
        "youtube_id": entry.get("id"),          # 例如 BV1sH4y1c7dR_p1
        "title": entry.get("title") or entry.get("id"),
        "audio_path": str(audio_path),
    }
