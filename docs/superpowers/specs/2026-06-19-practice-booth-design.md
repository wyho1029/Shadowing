# 設計文件：Plan 2 — 練習亭（Practice Booth）

- 日期：2026-06-19
- 狀態：已通過 brainstorming，待寫實作計劃
- 關聯：[2026-06-18 整體 rebuild spec](2026-06-18-shadowing-google-rebuild-design.md)。本文**修正**該 spec 兩個假設（見 §2）。
- 前置：Plan 1（Replenisher）已交付到 master，會持續產生 `manifest.json` + 音檔入 Drive library 資料夾。

## 1. 背景與目標

Plan 1（磨片廠）已將「下載 + Whisper 轉錄」變成本機背景工序，產出片庫。Plan 2 是**消費端**：一個手機/電腦隨時開、即時可跟讀練習的 PWA。

### 目標
1. 手機開個網址即時練習：揀片庫一條未練 clip → 逐句播原聲 → 錄自己跟讀 → 逐字評分回饋。
2. 完全免費，用使用者現有 Google（Drive）+ GitHub 資源。
3. 跨裝置共用進度，並回寫 `progress.json` 令 Plan 1 的補片閉環成立。

### 非目標（YAGNI）
- 多劇進度 dashboard、詞彙卡。
- iOS 第二條 STT 方案（只 feature-detect 退化）。
- 花巧 UI（沿用現有簡樸介面）。
- 即場攞新片（屬 Plan 1）。

## 2. 修正原 spec 的兩個假設

1. **網頁寄存：Apps Script → GitHub Pages。** 原 spec 說用 Apps Script HtmlService 寄存整個 PWA。但 Apps Script 的網頁在一個 `googleusercontent` 的 sandbox iframe 內執行，**麥克風（getUserMedia）、Web Speech API、service worker（離線/PWA 安裝）在該 sandbox 多數被擋** → 核心「錄音+評分+離線」會失效。改為：**PWA 寄存於 GitHub Pages**（真 origin、HTTPS，全部功能可用），Apps Script 只做 JSON API。
2. **音檔送達：遠端逐句 seek → 整條下載再本地 seek。** 改為 `<audio>` 載入整條 clip（preload，clip 細，幾 MB），buffer 好後**本地 seek 逐句播**，消除「遠端 range/seek」可靠性風險，並順帶離線可播。

## 3. 架構（三件，各自獨立）

```
┌───────────────────────────┐     fetch JSON (CORS)      ┌──────────────────────────┐
│  PWA @ GitHub Pages        │ ─────────────────────────► │  Apps Script JSON API     │
│  username.github.io/...    │ ◄───────────────────────── │  doGet/doPost             │
│  · 真 origin：mic / Web     │     manifest / progress    │  · ?action=manifest       │
│    Speech / SW / install    │                            │  · ?action=progress (GET) │
│  · <audio src=Drive link>   │                            │  · doPost progress (POST) │
│    preload→buffer→本地 seek │                            │  讀寫 Drive library 資料夾 │
│  · compare.js 逐字評分      │                            └──────────────┬───────────┘
└──────────────┬─────────────┘                                           │ 讀寫
               │ <audio> 直載（playback 免 CORS）                          ▼
               └──────────────────────────────────────────►  Google Drive library/
                                                              manifest.json · progress.json
                                                              audio/<id>.m4a（Plan 1 寫入）
```

- **PWA（GitHub Pages）**：static HTML/JS/CSS。真 origin → 麥克風 / Web Speech API / service worker / 加到主畫面全部可用。
- **Apps Script JSON API**：以使用者身份讀寫自己的 Drive library 資料夾。serve manifest 時，將每個 `audio_file` 對應的 Drive 檔設為「擁有連結即可檢視」並填入直connect link（`audio_url`），解析 Plan 1 留下的 `audio_file` 契約。
- **Drive**：音檔（Plan 1 replenisher 寫入）+ `manifest.json` + `progress.json`。

## 4. Client 模組（PWA）

由現有 [frontend/](../../../frontend/) 進化（app.js / style.css / sw.js / manifest.webmanifest）。

- **主邏輯**：開機 fetch `?action=manifest` → 讀本地 `progress.json`（經 API）→ 揀一條未練 clip → `<audio src=audio_url>` `preload="auto"` → 等 buffer 足夠 → 逐句 seek 到 `sentence.start`、`timeupdate` 停在 `sentence.end`（沿用現有單一 `<audio>` 機制）→ 慢速 0.75x / loop。
- **錄音 + 評分**：MediaRecorder 錄 → **Web Speech API（`SpeechRecognition`）** 本地轉文字 → **`compare.js`** 對齊 → 渲染 `tokens[].ref` + `tokens[].status`。練完一條 POST `?action=progress` mark done。
- **`compare.js`**：1:1 port 自 [compare.py](../../../backend/app/compare.py)（normalize：lower、`[^\w\s']`→空格、去 apostrophe；difflib `SequenceMatcher` 等價對齊 → ok/wrong/missing/extra；score = #ok / #ref）。以 compare.py 既有測試 case 作 oracle。
- **service worker**：cache app shell + 近期 clip 音檔 → 第二次即開、離線可練。
- **iOS 退化**：feature-detect `SpeechRecognition`；缺則收起評分，保留「播原聲 + 錄 + 播返自己聽」。

## 5. 資料契約（end-to-end）

- **manifest**（Plan 1 產生，Apps Script 增補）：clip 的 `audio_file`（檔名）→ Apps Script serve 時解析成 `audio_url`（Drive 直connect link）。其餘 `{clip_id, source, title, sentences:[{idx,text,start,end}]}` 不變。
- **progress.json**（`{version, done_clips:[], attempts:[]}`）：booth POST mark done（加 `clip_id` 入 `done_clips`，可選記 attempt 評分）→ Apps Script 原子寫回 Drive。Plan 1 replenisher 下次 cron 讀 `done_clips` 計「未練緩衝」補片 → 閉環。
- sentence 用 `clip_id + idx` 作 key（manifest 無 DB 自增 id）。

## 6. 🔬 SPIKE（實作計劃的第一個 task，使用者在 Android Chrome 跑，~10 分鐘）

落實作前必須驗證三項，全綠才繼續：
1. **Drive 音檔 link** 在手機 Chrome **載到 + seek 到**（放一個 m4a 上 Drive、設「有連結可看」、`<audio>` preload 後 seek 到中段）。
2. **GitHub Pages 頁 fetch Apps Script JSON 過到 CORS**（部署一個最小 Apps Script `doGet` 回 JSON，從 github.io 頁 `fetch()` 成功讀到）。
3. **GitHub Pages 上麥克風 + Web Speech API 行到**（HTTPS origin 取得 mic、`SpeechRecognition` 出到文字）。

各項 fallback（若該項紅）：
- (1) 紅 → 音檔改由 Apps Script proxy（細檔可行），或 replenisher 順手 ffmpeg/av 切 per-sentence 小檔。
- (2) 紅 → 改 JSONP，或調 Apps Script 回應/部署設定。
- (3) 紅 → 評分退化為自我比對（與 iOS 退化同路）。

## 7. 錯誤處理

- **PWA**：manifest fetch 失敗 → 提示重試 / 用 cache。無未練 clip → 顯示「等磨片廠補片」。音檔載入失敗 → 跳下一條可用 clip。Web Speech API 不支援/拒權 → 退化自我比對。離線 → service worker 派 cache。
- **Apps Script**：manifest/progress 不存在 → 回合理預設（空）。寫 progress 用「先寫 temp 再 rename」原子操作（與 Plan 1 library 一致）。
- **CORS / 權限**：spike 先行驗證，避免實作到一半先發現。

## 8. 測試策略

- **compare.js**：以 compare.py 既有測試 case 作 oracle，node test harness 逐個斷言同結果（ok/wrong/missing/extra、score）。這是最重邏輯，必須嚴測。
- **純函式**：揀「下一條未練 clip」、progress mark/merge 抽成可測 function。
- **Apps Script / PWA glue**：邏輯薄，以 spike + 手動驗證為主（GAS 難自動化單元測試）。
- 外部（Drive / 麥克風 / Web Speech）不入自動套件。

## 9. 元件 / 檔案結構（初步，writing-plans 細化）

| 區域 | 檔案 | 責任 |
|------|------|------|
| Apps Script | `appscript/Code.gs` | doGet（manifest/progress）、doPost（progress）、Drive 讀寫 + audio link 解析 |
| PWA | `frontend/index.html` / `style.css` | 介面（沿用、微調） |
| PWA | `frontend/app.js` | 主邏輯（改 fetch API、整條下載+seek、Web Speech、POST progress） |
| PWA | `frontend/compare.js` | compare.py 的 JS port（可測） |
| PWA | `frontend/sw.js` / `manifest.webmanifest` | 離線 cache + 安裝 |
| 測試 | `frontend/compare.test.*`（node） | compare.js 對 oracle |

> 部署：GitHub Pages 由 `frontend/`（或 `/docs`）發佈；Apps Script 由 clasp 或網頁編輯器部署成 web app。實作計劃定案。

## 10. 待落實作時決定（非阻塞）

- Apps Script 端點 CORS 的具體做法（依 spike 結果）。
- service worker 預 cache clip 數。
- progress 是否保留 attempts 評分歷史。
- GitHub Pages 發佈來源（`frontend/` vs `/docs` vs `gh-pages` 分支）。
