from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = BASE_DIR / "data"
AUDIO_DIR = DATA_DIR / "audio"
DB_PATH = DATA_DIR / "shadowing.sqlite3"

# Whisper model：small 喺普通電腦平衡速度同準度；要快可改 "base"
WHISPER_MODEL = "small"

# ── yt-dlp cookies ──────────────────────────────────────────────────────────
# 有啲站會擋未認證嘅 yt-dlp：YouTube 偶爾 "Sign in to confirm you're not a bot"，
# Bilibili 更會直接 HTTP 412。兩個解法（cookie 檔優先）：
#
# 1) COOKIE 檔（推薦，最穩）：用 Chrome 擴充「Get cookies.txt LOCALLY」匯出
#    bilibili.com / youtube.com 嘅 cookies 做 Netscape 格式檔，放喺 backend/ 度。
#    Chrome 開唔開都唔阻，又唔受 App-Bound 加密影響。設下面個路徑就會用。
# 2) 直接借瀏覽器 cookies：設 YTDLP_COOKIES_FROM_BROWSER = "chrome"/"firefox"。
#    用 Chrome 嗰陣要先完全閂咗 Chrome，cookie DB 先解到鎖。
#
# 兩個都係 None 就唔用 cookies（YouTube 多數仍 work，Bilibili 會 412）。
YTDLP_COOKIE_FILE = BASE_DIR / "cookies.txt"   # 唔存在就自動當冇設
YTDLP_COOKIES_FROM_BROWSER = None

DATA_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)
