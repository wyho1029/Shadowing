# Shadowing

英文跟讀（shadowing）練習 PWA：揀套成人動畫 → 自動搵 YouTube clip → 逐句播原音、
錄跟讀、Whisper 轉文字後同原句逐字對比畀 feedback。本機跑，唔使收費 API。

## 架構

- **後端**：Python FastAPI，用 `yt-dlp` 自動搜尋/抽片、`faster-whisper` 轉文字、
  `difflib` 逐字對比、SQLite 存資料。
- **前端**：原生 HTML/JS/CSS PWA（可加到手機主畫面）。

## 安裝

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 起 server

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- 電腦開：http://localhost:8000
- 手機（同一 WiFi）開：`http://<電腦區網IP>:8000` → 瀏覽器選單「加到主畫面」當 app 用。

## 點用

1. 揀一套劇
2. 撳「搵片開始練」（**第一次會載 Whisper model，耐少少**）
3. 逐句：▶ 播原句（可慢放/loop）→ ● 錄跟讀 → 睇綠/紅逐字對比 → ▶ 聽返自己
4. 撳「過咗，下一句」或「再練」

## 行 test

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

真網絡搜尋測試（會落 YouTube，預設 skip）：

```powershell
cd backend
$env:RUN_NETWORK_TESTS=1; .\.venv\Scripts\python.exe -m pytest tests/test_youtube.py -q
```

## 法律 / 使用範圍

自動下載 YouTube 片段僅供**個人學習、離線練習**用，唔作公開再分享。
Netflix / Disney+ 完整集數有 DRM，本 app 唔處理。

## 之後計劃（v2）

- 上載自己音檔（自有片段）
- 進度 dashboard / 練習統計
- 生字卡（OCR 生字）
