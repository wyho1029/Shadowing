from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = BASE_DIR / "data"
AUDIO_DIR = DATA_DIR / "audio"
DB_PATH = DATA_DIR / "shadowing.sqlite3"

# Whisper model：small 喺普通電腦平衡速度同準度；要快可改 "base"
WHISPER_MODEL = "small"

# YouTube 而家會擋未認證嘅 yt-dlp（"Sign in to confirm you're not a bot"）。
# 設成瀏覽器名（"chrome" / "edge" / "firefox"）就會借用該瀏覽器嘅登入 cookies
# 過反機械人檢查。None = 唔用 cookies（多數情況會被擋）。
# 注意：用 Chrome/Edge 嗰陣，最好先完全閂咗個瀏覽器，cookie DB 先解到鎖。
YTDLP_COOKIES_FROM_BROWSER = None

DATA_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)
