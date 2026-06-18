# 設計文件：Shadowing 重構為「本機磨片廠 + Google 練習亭」

- 日期：2026-06-18
- 狀態：已通過 brainstorming，待寫實作計劃
- 取代：現行本機 FastAPI + SQLite + 即場 yt-dlp/Whisper 架構

## 1. 背景與問題

現行 app 每次「搵片」都喺本機即場做三件重嘢：yt-dlp 下載、載入 Whisper model、CPU 行 Whisper 轉錄。`small` model 喺普通電腦轉一條幾分鐘嘅片要等 30 秒到幾分鐘；而且要部電腦開住 `uvicorn` 先用到，做唔到「手機隨時隨地、撳掣即練」。使用者因為太慢已經唔想用。

### 目標

1. 手機 / 電腦隨時開個網址，**即時**(零等待)就有句子可以跟讀。
2. **完全免費**，用使用者現有嘅 Google 資源(`script.google.com` Apps Script + Google Drive)。
3. 重嘅運算(下載 + 轉錄)同練習時刻**完全脫鈎**，並且**自動補貨**，使用者唔使手動搵片或下載。
4. 保留逐字對比回饋(ok / wrong / missing / extra)。

### 非目標(YAGNI，明確唔做)

- 多劇進度 dashboard、詞彙卡(原 v2 構想，繼續延後)。
- 即場攞全新片(本質上同「免費 + 即時 + 純 Google」衝突)。
- 雲端 GPU 轉錄、付費服務。
- 精準「剛好 50% 即時觸發」補片(用「每日保持緩衝量」代替，見 §5)。

## 2. 硬限制(影響設計嘅事實)

- **Apps Script / Drive 唔可以跑 yt-dlp 或 Whisper**：冇 Python、唔准行 binary、有執行時間上限、冇 ML。所以下載 + 轉錄一定要喺本機 prep，唔可以喺 Google 即場做。
- 專案本身已經喺 `G:\我的雲端硬碟\AI\Shadowing`，即 **Google Drive 同步資料夾**。寫入呢度嘅檔案會由 Drive 桌面版自動 sync 上雲，**唔使搞 Drive API 認證**。
- Apps Script web app 串流 binary 音檔冇 HTTP range request → seek 唔到。故音檔唔經 Apps Script，改由 manifest 內嘅 Drive 直connect link 畀 `<audio>` 直接載。

## 3. 架構總覽：兩半獨立系統

```
┌─────────────────────────────┐        Google Drive (已同步資料夾)        ┌──────────────────────────────┐
│  🏭 本機磨片廠 (Replenisher)  │        ┌──────────────────────────┐       │  📱 Google 練習亭 (Apps Script)│
│  你部電腦 · Task Scheduler   │  寫入  │  library/                │  讀取 │  web app /exec URL            │
│                             │ ─────► │   manifest.json          │ ◄──── │                               │
│  shows→youtube/bilibili     │        │   audio/<id>.m4a ...     │       │  doGet:                       │
│   →transcribe→segmenter     │        │  progress.json           │ ◄────►│   · 派 PWA shell              │
│  每日 cron，保持緩衝量        │  讀取  └──────────────────────────┘  讀寫 │   · ?action=manifest          │
│                             │ ◄──────────────────────────────────────► │   · ?action=progress (讀/寫)  │
└─────────────────────────────┘                                          └──────────────────────────────┘
                                                                                      │ 派 PWA
                                                                                      ▼
                                                                          手機 / 電腦瀏覽器
                                                                          · <audio> 直載 Drive link + seek
                                                                          · Web Speech API 做 STT
                                                                          · JS port 嘅 compare 邏輯
                                                                          · service worker cache → 即開 / 離線
```

兩半透過 Drive 上嘅檔案溝通，冇即時耦合：磨片廠淨係生產，練習亭淨係消費 + 記進度。

## 4. 元件

### 4.1 磨片廠 Replenisher(本機腳本，重用現有 pipeline)

- 重用 `shows`、`youtube`、`bilibili`、`transcribe`、`segmenter` 幾乎原封不動。
- 新增一個 entry-point 腳本(例如 `backend/replenish.py`)：
  1. 讀 Drive 上現有 `manifest.json` + `progress.json`。
  2. 對每套劇，計「未練片數 / 未練總時長」。低過 target(例如每套劇保持 ≥ 2–3 條未練片，或 ≥ N 分鐘)就補：跑現有 `find_clip` → `transcribe_segments` → `segment_transcript`。
  3. 將音檔寫入 `library/audio/`，更新 `manifest.json`。
  4. 全部寫喺 Drive 同步資料夾，靠 Drive 桌面版 sync。
- 由 Windows Task Scheduler 每日觸發一次(背景、無人值守)。
- 重嘅嘢全部喺呢度，同練習時刻脫鈎。

### 4.2 練習亭 Apps Script web app(`Code.gs`)

- `doGet(e)`：
  - 冇 `action` → 用 `HtmlService` 派 PWA(HTML/JS/CSS inline 或從 Drive 讀)。
  - `action=manifest` → 讀 Drive `manifest.json`，用 `ContentService` 返 JSON。
  - `action=progress` → 返 `progress.json`。
- `doPost(e)`：`action=progress` → 將練完嘅 sentence/clip 標記寫入 `progress.json`(令手機 + 電腦共用進度)。
- 以使用者自己身份跑，讀寫自己 Drive，免費。

### 4.3 練習亭 PWA(client)

- 由 Apps Script 派發；service worker cache shell + 近期音檔 → 第二次開即秒開、離線可練。
- 開機流程：fetch `?action=manifest` → 揀一條「未練」片 → 顯示第一句。
- 播放：沿用單一 `<audio>` + seek 到 `sentence.start` + `timeupdate` 停喺 `sentence.end`；`<audio>.src` = manifest 內 Drive 直connect link；首次 seek 前等 `loadedmetadata`。
- 評分：撳錄音 → **Web Speech API**(`SpeechRecognition`)即時轉文字 → JS port 嘅 compare 邏輯逐字比對 → 渲染 `tokens[].ref` + `tokens[].status`。
- 練完一句 → POST `?action=progress` 標記 → 下一句 / 下一條片。

### 4.4 compare 邏輯 port 落 JS

把 `compare.py` 嘅行為 1:1 搬去 JS：
- `normalize`：轉細階、`[^\w\s']` 變空格(連字號拆兩 token)、去 apostrophe(`I'm`→`im`)、split。
- 對齊：`difflib.SequenceMatcher` JS 無內建，用等價 LCS / opcode 演算法產生 `equal/replace/delete/insert`，對應 `ok/wrong/missing/extra`。
- `score` = (#ok) / (參考 token 數)。
- 用原 `compare.py` 嘅單元測試作為 oracle，確保 JS 版同 Python 版同結果。

## 5. 「練到一半自動補」嘅實現

唔做長駐監察嘅精準 50% 觸發器(要掛住部機)。改為：

- 練習亭每練完一條片就更新 `progress.json`(經 Apps Script 寫返 Drive)。
- 磨片廠每日跑時讀 `progress.json` + `manifest.json`，per show 計「未練緩衝量」，低過門檻先補。
- 效果等同「永遠唔會練到冇片」，但唔使長駐進程、唔使精準即時觸發。門檻(target buffer)可調。

## 6. 資料形狀(契約，end-to-end 對齊)

### manifest.json
```jsonc
{
  "version": 1,
  "updated_at": "2026-06-18T03:00:00Z",
  "shows": [
    {
      "id": "bojack",
      "name": "BoJack Horseman",
      "clips": [
        {
          "clip_id": "BV1sH4y1c7dR_p3",      // 或 YouTube id
          "source": "bilibili",               // "bilibili" | "youtube"
          "title": "...",
          "audio_url": "https://drive.../uc?id=...&export=download",
          "sentences": [
            { "idx": 0, "text": "...", "start": 1.2, "end": 4.8 }
          ]
        }
      ]
    }
  ]
}
```
> sentence 形狀沿用現行 `{idx, text, start, end}`(去咗 DB 自動產生嘅 `id`，client 用 `clip_id + idx` 作 key)。

### progress.json
```jsonc
{
  "version": 1,
  "done_clips": ["BV1sH4y1c7dR_p3", "dQw4w9WgXcQ"],   // 已練完嘅片
  "attempts": [                                          // 可選：保留評分紀錄
    { "clip_id": "...", "idx": 0, "score": 0.92, "at": "..." }
  ]
}
```

## 7. 錯誤處理

- **磨片廠**：個別片下載/轉錄失敗 → skip 嗰條，繼續其他(沿用現有 `ignoreerrors` / try-except 回 None)；寫 manifest 用「先寫 temp 再 rename」避免 Drive sync 到半截檔。
- **Apps Script**：manifest / progress 唔存在 → 返合理預設(空 manifest → 練習亭顯示「未有素材，等磨片廠跑」)。
- **PWA**：
  - Web Speech API 唔支援(iOS Safari) → 退化做「自我比對」模式(播原聲、錄、播返自己聽，唔自動評分)，並提示。
  - Drive 音檔載入失敗 → 跳去下一條可用片並提示。
  - 離線 → service worker 派 cache 嘅 shell + 已 cache 片。

## 8. 技術風險與前置驗證(spike)

**最大不確定性：Drive 直connect link 畀 `<audio>` seek(range request)實際可唔可靠。**

- 落實作之前先做 5 分鐘 spike：放一個音檔上 Drive、設 share link、喺手機 Chrome 試 `<audio>` seek 到中段。
- 若不可靠，後備方案：磨片廠順手用 ffmpeg 將每條片切成**逐句細音檔**(每句一個檔，毋須 seek)；manifest 改為每句一個 `audio_url`。此為已知可行嘅 fallback，但增加 prep 工序同檔案數。

次要風險：iOS Safari 嘅 Web Speech API 支援(已有 §7 退化方案)。

## 9. 測試策略

- **磨片廠**：沿用現行 TDD。新增 `replenish` 嘅緩衝量計算(純邏輯：給定 manifest + progress + target → 該補邊套劇)做單元測試；manifest 寫入用 monkeypatch 假 Drive 路徑。pipeline 各模組測試不變。
- **JS compare**：以 `compare.py` 現有測試 case 作 oracle，逐個喂入 JS 版斷言同結果(可用 node 跑一個細 test harness)。
- **Apps Script**：邏輯薄(讀寫 Drive JSON)，以手動 / clasp 本地測試為主；JSON 形狀以上述契約為準。
- 外部 IO(YouTube / Bilibili / Whisper)仍然唔入預設測試,沿用現有 monkeypatch 策略。

## 10. 重用 vs 新寫

| 現有 | 命運 |
|------|------|
| `shows` / `youtube` / `bilibili` / `transcribe` / `segmenter` | 幾乎照用，包成 replenisher |
| `compare.py` 邏輯 | port 落 JS（client 端） |
| `db.py`（SQLite） | 退役 → Drive `manifest.json` + `progress.json` |
| `main.py`（FastAPI） | 退役 → Apps Script `Code.gs` |
| `frontend/app.js` | 進化：加 Web Speech API + JS compare + fetch Apps Script |
| service worker / manifest.webmanifest | 保留並強化(cache shell + 近期片) |

## 11. 待落實作時決定（非阻塞）

- target buffer 具體數值（每套劇留幾多條 / 幾多分鐘）。
- progress.json 是否保留 attempts 評分歷史（影響檔案大小）。
- service worker 預 cache 幾多條片。

以上為非阻塞細節，於 writing-plans 階段定案。
