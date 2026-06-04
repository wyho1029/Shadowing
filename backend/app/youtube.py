from pathlib import Path

import yt_dlp

from app.config import AUDIO_DIR, YTDLP_COOKIES_FROM_BROWSER

MIN_DURATION = 30      # 秒
MAX_DURATION = 600     # 秒（10 分鐘）


def _base_opts() -> dict:
    """所有 yt-dlp 呼叫共用嘅 options：靜音、忽略個別片錯誤、按需借用瀏覽器 cookies。"""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,   # 個別片抽唔到就 skip，唔好成個 crash
    }
    if YTDLP_COOKIES_FROM_BROWSER:
        opts["cookiesfrombrowser"] = (YTDLP_COOKIES_FROM_BROWSER,)
    return opts


def pick_candidate(entries: list[dict]) -> dict | None:
    """喺搜尋結果揀第一個長度合理嘅片。

    唔再硬性要求 YouTube 英文字幕——我哋係用 Whisper 轉音檔做 transcript，
    根本唔靠 YouTube 字幕；而且劇集清單本身全部係英文劇，任何 clip 都係英文對白。
    淨係用長度（30 秒到 10 分鐘）篩走太短/太長嘅。
    """
    for e in entries:
        dur = e.get("duration") or 0
        if MIN_DURATION <= dur <= MAX_DURATION:
            return e
    return None


def search(query: str, limit: int = 10) -> list[dict]:
    """ytsearch 攞 metadata。用 flat 抽取（快、唔逐條深抽，唔易觸發反機械人），
    只攞到 id/title/duration——足夠揀片。抽取失敗時回 []，唔好 raise。"""
    opts = {**_base_opts(), "extract_flat": "in_playlist"}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    except yt_dlp.utils.DownloadError:
        return []
    if not info:
        return []
    # ignoreerrors 會令抽唔到嘅 entry 變 None，要隔走
    return [e for e in info.get("entries", []) if e]


def download_audio(youtube_id: str) -> Path:
    """抽單一影片嘅音檔（m4a），回傳本機路徑。"""
    out_tmpl = str(AUDIO_DIR / "%(id)s.%(ext)s")
    opts = {
        **_base_opts(),
        "format": "bestaudio[ext=m4a]/bestaudio",
        "outtmpl": out_tmpl,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(
            f"https://www.youtube.com/watch?v={youtube_id}", download=True
        )
        if info is None:
            raise RuntimeError(f"download failed for {youtube_id}")
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
