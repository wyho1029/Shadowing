# Shadowing App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 砌一個英文跟讀（shadowing）練習 PWA：自動搜尋成人動畫 YouTube clip 做素材，逐句播原音、錄使用者跟讀、Whisper 轉文字後同原句逐字對比畀 feedback。

**Architecture:** PWA 前端（原生 HTML/JS/CSS）+ Python FastAPI 後端。後端用 yt-dlp 自動搜尋/抽片、faster-whisper 轉文字、difflib 做逐字對比、SQLite 存資料。重活全部喺後端。

**Tech Stack:** Python 3.11+、FastAPI、uvicorn、yt-dlp、faster-whisper、pytest、SQLite（內建 `sqlite3`）、原生前端 + PWA（manifest + service worker）。

**全部本機跑，唔使任何收費 API。**

---

## File Structure

```
G:\我的雲端硬碟\AI\Shadowing\
├─ backend/
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ main.py          # FastAPI app + routes
│  │  ├─ config.py        # 路徑/常數（DB 位置、音檔資料夾）
│  │  ├─ shows.py         # 內建劇集清單 + 搜尋字串
│  │  ├─ compare.py       # 逐字對比引擎（difflib）— 核心
│  │  ├─ segmenter.py     # 字幕/transcript 切句 + 時間碼
│  │  ├─ youtube.py       # yt-dlp 搜尋 + 抽音 + 字幕
│  │  ├─ transcribe.py    # faster-whisper wrapper
│  │  └─ db.py            # SQLite：materials / sentences / attempts
│  ├─ tests/
│  │  ├─ __init__.py
│  │  ├─ test_compare.py
│  │  ├─ test_segmenter.py
│  │  ├─ test_shows.py
│  │  ├─ test_db.py
│  │  ├─ test_youtube.py
│  │  └─ test_api.py
│  ├─ data/               # runtime：sqlite db + 下載音檔（gitignore）
│  └─ requirements.txt
├─ frontend/
│  ├─ index.html
│  ├─ app.js
│  ├─ style.css
│  ├─ manifest.webmanifest
│  └─ sw.js
├─ .gitignore
└─ docs/...
```

**責任分工**：`compare.py` 同 `segmenter.py` 係純函數、最易測、係 app 心臟 → 行足 TDD。`youtube.py`/`transcribe.py` 係外部 IO wrapper → mock + 一條真樣本 smoke test。`db.py` 用臨時 db 測。`main.py` 用 FastAPI `TestClient` + monkeypatch 測 route 接駁。

---

## Task 0: Project scaffold

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`、`backend/tests/__init__.py`
- Create: `backend/app/config.py`
- Create: `.gitignore`

- [ ] **Step 1: 寫 `.gitignore`**

Create `.gitignore`:
```gitignore
# Python
__pycache__/
*.pyc
.venv/
venv/

# runtime data
backend/data/
*.sqlite3
*.db

# whisper model cache
*.bin
```

- [ ] **Step 2: 寫 `backend/requirements.txt`**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
yt-dlp==2025.1.15
faster-whisper==1.1.1
pytest==8.3.4
httpx==0.28.1
```
（`httpx` 係 FastAPI `TestClient` 需要。）

- [ ] **Step 3: 建 venv + 裝套件**

Run（PowerShell，喺 `backend/`）:
```powershell
cd "G:\我的雲端硬碟\AI\Shadowing\backend"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
Expected: 全部裝完，無 error。（faster-whisper 第一次會較大，耐少少。）

- [ ] **Step 4: 建空 package 檔**

Create `backend/app/__init__.py`（空檔）。
Create `backend/tests/__init__.py`（空檔）。

- [ ] **Step 5: 寫 `backend/app/config.py`**

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = BASE_DIR / "data"
AUDIO_DIR = DATA_DIR / "audio"
DB_PATH = DATA_DIR / "shadowing.sqlite3"

# Whisper model：small 喺普通電腦平衡速度同準度；要快可改 "base"
WHISPER_MODEL = "small"

DATA_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)
```

- [ ] **Step 6: 確認 pytest 行到（空跑）**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
Expected: `no tests ran`（或 collected 0），無 import error。

- [ ] **Step 7: Commit**

```powershell
git add -A
git commit -m "chore: scaffold backend project structure"
```

---

## Task 1: 對比引擎 compare.py（核心，行足 TDD）

**用途**：將「原句」同「使用者講出嚟嘅文字」逐字對齊，輸出每個 token 嘅狀態（`ok` / `wrong` / `missing` / `extra`），同總分。

**Files:**
- Create: `backend/app/compare.py`
- Test: `backend/tests/test_compare.py`

- [ ] **Step 1: 寫第一個 failing test（normalize + 全對）**

Create `backend/tests/test_compare.py`:
```python
from app.compare import compare_sentence


def test_perfect_match_all_ok():
    result = compare_sentence("I'm a horse.", "im a horse")
    assert [t["status"] for t in result["tokens"]] == ["ok", "ok", "ok"]
    assert result["score"] == 1.0


def test_tokens_carry_reference_words():
    result = compare_sentence("I'm a horse.", "im a horse")
    assert [t["ref"] for t in result["tokens"]] == ["im", "a", "horse"]
```
（設計決定：對比前 normalize —— 轉細階、去標點、縮寫照原樣比對，所以原句 `I'm` 同講嘅 `im` 都 normalize 成 `im`。）

- [ ] **Step 2: 行 test 確認 fail**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_compare.py -q
```
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.compare'`。

- [ ] **Step 3: 寫最小實作**

Create `backend/app/compare.py`:
```python
import re
from difflib import SequenceMatcher


def normalize(text: str) -> list[str]:
    """轉細階、淨低字母數字同空格、split 成 token list。"""
    text = text.lower()
    text = re.sub(r"[^\w\s']", " ", text)   # 去標點（保留 apostrophe 先）
    text = text.replace("'", "")            # 縮寫去 apostrophe：im / dont
    return text.split()


def compare_sentence(reference: str, spoken: str) -> dict:
    ref_tokens = normalize(reference)
    hyp_tokens = normalize(spoken)
    matcher = SequenceMatcher(a=ref_tokens, b=hyp_tokens, autojunk=False)

    tokens: list[dict] = []
    correct = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i1, i2):
                tokens.append({"ref": ref_tokens[k], "status": "ok"})
                correct += 1
        elif tag == "replace":
            for k in range(i1, i2):
                tokens.append({"ref": ref_tokens[k], "status": "wrong"})
            for k in range(j1, j2):
                tokens.append({"ref": hyp_tokens[k], "status": "extra"})
        elif tag == "delete":           # 原句有、使用者漏咗
            for k in range(i1, i2):
                tokens.append({"ref": ref_tokens[k], "status": "missing"})
        elif tag == "insert":           # 使用者多講
            for k in range(j1, j2):
                tokens.append({"ref": hyp_tokens[k], "status": "extra"})

    score = correct / len(ref_tokens) if ref_tokens else 0.0
    return {"tokens": tokens, "score": score}
```

- [ ] **Step 4: 行 test 確認 pass**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_compare.py -q
```
Expected: PASS（2 passed）。

- [ ] **Step 5: 加錯漏字嘅 test**

加入 `backend/tests/test_compare.py`:
```python
def test_missing_word_marked():
    # 原句 4 字，使用者漏咗 "a"
    result = compare_sentence("I am a horse", "I am horse")
    statuses = {t["ref"]: t["status"] for t in result["tokens"]}
    assert statuses["a"] == "missing"
    assert result["score"] == 0.75  # 3/4 啱


def test_wrong_word_marked():
    result = compare_sentence("I am a horse", "I am a house")
    wrong = [t for t in result["tokens"] if t["status"] == "wrong"]
    extra = [t for t in result["tokens"] if t["status"] == "extra"]
    assert wrong and wrong[0]["ref"] == "horse"
    assert extra and extra[0]["ref"] == "house"


def test_empty_spoken_all_missing():
    result = compare_sentence("hello world", "")
    assert [t["status"] for t in result["tokens"]] == ["missing", "missing"]
    assert result["score"] == 0.0
```

- [ ] **Step 6: 行全部 test 確認 pass**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_compare.py -q
```
Expected: PASS（5 passed）。如果 `test_missing_word_marked` 唔係 0.75，檢查 normalize 有冇食錯字。

- [ ] **Step 7: Commit**

```powershell
git add app/compare.py tests/test_compare.py
git commit -m "feat: word-level comparison engine with difflib"
```

---

## Task 2: 切句 segmenter.py（行足 TDD）

**用途**：將 Whisper 嘅 segment list（每段有 text + start + end）合併/切成「一句一句」，每句帶 `start`/`end` 時間碼，畀前端定位播放。

**Files:**
- Create: `backend/app/segmenter.py`
- Test: `backend/tests/test_segmenter.py`

- [ ] **Step 1: 寫 failing test（句號切句）**

Create `backend/tests/test_segmenter.py`:
```python
from app.segmenter import segment_transcript


def test_splits_on_sentence_punctuation():
    raw = [
        {"text": "I'm a horse.", "start": 0.0, "end": 1.5},
        {"text": "You are a cat.", "start": 1.5, "end": 3.0},
    ]
    out = segment_transcript(raw)
    assert [s["text"] for s in out] == ["I'm a horse.", "You are a cat."]
    assert out[0]["start"] == 0.0 and out[0]["end"] == 1.5
    assert out[1]["start"] == 1.5 and out[1]["end"] == 3.0


def test_merges_fragments_until_punctuation():
    raw = [
        {"text": "I really", "start": 0.0, "end": 0.8},
        {"text": "love this show.", "start": 0.8, "end": 2.0},
    ]
    out = segment_transcript(raw)
    assert len(out) == 1
    assert out[0]["text"] == "I really love this show."
    assert out[0]["start"] == 0.0 and out[0]["end"] == 2.0
```

- [ ] **Step 2: 行 test 確認 fail**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_segmenter.py -q
```
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.segmenter'`。

- [ ] **Step 3: 寫最小實作**

Create `backend/app/segmenter.py`:
```python
import re

_END_PUNCT = re.compile(r"[.!?]['\")\]]?\s*$")


def segment_transcript(raw_segments: list[dict]) -> list[dict]:
    """合併 Whisper segment 成完整句子。

    規則：累積 segment 直到 text 以 . ! ? 結尾就斬一句。
    每句 start = 第一個 fragment 嘅 start，end = 最後一個嘅 end。
    """
    sentences: list[dict] = []
    buf_text: list[str] = []
    buf_start: float | None = None
    buf_end: float = 0.0

    for seg in raw_segments:
        text = seg["text"].strip()
        if not text:
            continue
        if buf_start is None:
            buf_start = seg["start"]
        buf_text.append(text)
        buf_end = seg["end"]

        if _END_PUNCT.search(text):
            sentences.append(
                {"text": " ".join(buf_text), "start": buf_start, "end": buf_end}
            )
            buf_text, buf_start = [], None

    # 後備：最後一段冇標點都要收返
    if buf_text:
        sentences.append(
            {"text": " ".join(buf_text), "start": buf_start, "end": buf_end}
        )
    return sentences
```

- [ ] **Step 4: 行 test 確認 pass**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_segmenter.py -q
```
Expected: PASS（2 passed）。

- [ ] **Step 5: 加後備切法 test（冇標點）**

加入 `backend/tests/test_segmenter.py`:
```python
def test_trailing_text_without_punctuation_is_kept():
    raw = [{"text": "no punctuation here", "start": 0.0, "end": 1.0}]
    out = segment_transcript(raw)
    assert len(out) == 1
    assert out[0]["text"] == "no punctuation here"
    assert out[0]["end"] == 1.0


def test_empty_segments_skipped():
    raw = [
        {"text": "   ", "start": 0.0, "end": 0.5},
        {"text": "Hello.", "start": 0.5, "end": 1.0},
    ]
    out = segment_transcript(raw)
    assert len(out) == 1
    assert out[0]["text"] == "Hello."
    assert out[0]["start"] == 0.5
```

- [ ] **Step 6: 行全部 test 確認 pass**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_segmenter.py -q
```
Expected: PASS（4 passed）。

- [ ] **Step 7: Commit**

```powershell
git add app/segmenter.py tests/test_segmenter.py
git commit -m "feat: transcript segmentation into timed sentences"
```

---

## Task 3: 劇集清單 shows.py

**用途**：內建劇集清單同對應 YouTube 搜尋字串。純資料 + 一個 lookup。

**Files:**
- Create: `backend/app/shows.py`
- Test: `backend/tests/test_shows.py`

- [ ] **Step 1: 寫 failing test**

Create `backend/tests/test_shows.py`:
```python
from app.shows import SHOWS, get_search_query, list_shows


def test_has_expected_shows():
    ids = {s["id"] for s in SHOWS}
    assert {"bojack", "simpsons", "rick_and_morty",
            "family_guy", "south_park", "bobs_burgers"} <= ids


def test_list_shows_returns_id_and_name():
    shows = list_shows()
    assert all("id" in s and "name" in s for s in shows)


def test_get_search_query_known():
    assert get_search_query("bojack") == "BoJack Horseman best scenes"


def test_get_search_query_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        get_search_query("not_a_show")
```

- [ ] **Step 2: 行 test 確認 fail**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_shows.py -q
```
Expected: FAIL —— `ModuleNotFoundError`。

- [ ] **Step 3: 寫實作**

Create `backend/app/shows.py`:
```python
SHOWS = [
    {"id": "bojack", "name": "BoJack Horseman",
     "query": "BoJack Horseman best scenes"},
    {"id": "simpsons", "name": "The Simpsons",
     "query": "The Simpsons best scenes"},
    {"id": "rick_and_morty", "name": "Rick and Morty",
     "query": "Rick and Morty best scenes"},
    {"id": "family_guy", "name": "Family Guy",
     "query": "Family Guy funniest moments"},
    {"id": "south_park", "name": "South Park",
     "query": "South Park best scenes"},
    {"id": "bobs_burgers", "name": "Bob's Burgers",
     "query": "Bob's Burgers best scenes"},
]

_BY_ID = {s["id"]: s for s in SHOWS}


def list_shows() -> list[dict]:
    return [{"id": s["id"], "name": s["name"]} for s in SHOWS]


def get_search_query(show_id: str) -> str:
    return _BY_ID[show_id]["query"]
```

- [ ] **Step 4: 行 test 確認 pass**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_shows.py -q
```
Expected: PASS（4 passed）。

- [ ] **Step 5: Commit**

```powershell
git add app/shows.py tests/test_shows.py
git commit -m "feat: curated show list with search queries"
```

---

## Task 4: SQLite 資料層 db.py（行足 TDD）

**用途**：存 materials（一段下載咗嘅 clip）、sentences（切好嘅句）、attempts（每次練習記錄 + 分數）。

**Files:**
- Create: `backend/app/db.py`
- Test: `backend/tests/test_db.py`

- [ ] **Step 1: 寫 failing test（建 material + sentences，攞返）**

Create `backend/tests/test_db.py`:
```python
from app.db import Database


def make_db(tmp_path):
    return Database(tmp_path / "test.sqlite3")


def test_add_material_and_get_sentences(tmp_path):
    db = make_db(tmp_path)
    mid = db.add_material(show_id="bojack", title="BoJack clip",
                          youtube_id="abc123", audio_path="data/audio/abc123.m4a")
    db.add_sentences(mid, [
        {"text": "I'm a horse.", "start": 0.0, "end": 1.5},
        {"text": "You are a cat.", "start": 1.5, "end": 3.0},
    ])
    sents = db.get_sentences(mid)
    assert len(sents) == 2
    assert sents[0]["text"] == "I'm a horse."
    assert sents[0]["start"] == 0.0
    assert "id" in sents[0]


def test_record_attempt_and_mark_status(tmp_path):
    db = make_db(tmp_path)
    mid = db.add_material("bojack", "clip", "abc", "p.m4a")
    db.add_sentences(mid, [{"text": "Hi.", "start": 0.0, "end": 1.0}])
    sid = db.get_sentences(mid)[0]["id"]
    db.record_attempt(sentence_id=sid, score=0.75, status="retry")
    attempts = db.get_attempts(sid)
    assert len(attempts) == 1
    assert attempts[0]["score"] == 0.75
    assert attempts[0]["status"] == "retry"
```

- [ ] **Step 2: 行 test 確認 fail**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_db.py -q
```
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.db'`。

- [ ] **Step 3: 寫實作**

Create `backend/app/db.py`:
```python
import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    show_id TEXT NOT NULL,
    title TEXT NOT NULL,
    youtube_id TEXT NOT NULL,
    audio_path TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sentences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL REFERENCES materials(id),
    idx INTEGER NOT NULL,
    text TEXT NOT NULL,
    start REAL NOT NULL,
    end REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sentence_id INTEGER NOT NULL REFERENCES sentences(id),
    score REAL NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def add_material(self, show_id: str, title: str,
                     youtube_id: str, audio_path: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO materials (show_id, title, youtube_id, audio_path) "
            "VALUES (?, ?, ?, ?)",
            (show_id, title, youtube_id, audio_path),
        )
        self.conn.commit()
        return cur.lastrowid

    def add_sentences(self, material_id: int, sentences: list[dict]) -> None:
        self.conn.executemany(
            "INSERT INTO sentences (material_id, idx, text, start, end) "
            "VALUES (?, ?, ?, ?, ?)",
            [(material_id, i, s["text"], s["start"], s["end"])
             for i, s in enumerate(sentences)],
        )
        self.conn.commit()

    def get_sentences(self, material_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, idx, text, start, end FROM sentences "
            "WHERE material_id = ? ORDER BY idx",
            (material_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_material(self, material_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM materials WHERE id = ?", (material_id,)
        ).fetchone()
        return dict(row) if row else None

    def record_attempt(self, sentence_id: int, score: float, status: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO attempts (sentence_id, score, status) VALUES (?, ?, ?)",
            (sentence_id, score, status),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_attempts(self, sentence_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, sentence_id, score, status FROM attempts "
            "WHERE sentence_id = ? ORDER BY id",
            (sentence_id,),
        ).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: 行 test 確認 pass**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_db.py -q
```
Expected: PASS（2 passed）。

- [ ] **Step 5: Commit**

```powershell
git add app/db.py tests/test_db.py
git commit -m "feat: sqlite data layer for materials, sentences, attempts"
```

---

## Task 5: YouTube wrapper youtube.py（mock test）

**用途**：用 yt-dlp 搜尋一條有英文字幕嘅 clip，抽音檔同字幕 segment。外部 IO，用 mock 測邏輯（篩選/錯誤處理），唔每次落網絡。

**Files:**
- Create: `backend/app/youtube.py`
- Test: `backend/tests/test_youtube.py`

- [ ] **Step 1: 寫 failing test（揀第一個有字幕嘅結果）**

Create `backend/tests/test_youtube.py`:
```python
from app import youtube


def test_pick_first_with_english_subs():
    entries = [
        {"id": "no_subs", "duration": 120, "subtitles": {}, "automatic_captions": {}},
        {"id": "good", "duration": 120, "subtitles": {"en": [{}]},
         "automatic_captions": {}},
    ]
    chosen = youtube.pick_candidate(entries)
    assert chosen["id"] == "good"


def test_pick_rejects_too_short_or_too_long():
    entries = [
        {"id": "too_short", "duration": 20, "subtitles": {"en": [{}]},
         "automatic_captions": {}},
        {"id": "too_long", "duration": 1200, "subtitles": {"en": [{}]},
         "automatic_captions": {}},
        {"id": "ok", "duration": 180, "subtitles": {"en": [{}]},
         "automatic_captions": {}},
    ]
    assert youtube.pick_candidate(entries)["id"] == "ok"


def test_pick_accepts_auto_captions_as_fallback():
    entries = [
        {"id": "auto", "duration": 120, "subtitles": {},
         "automatic_captions": {"en": [{}]}},
    ]
    assert youtube.pick_candidate(entries)["id"] == "auto"


def test_pick_returns_none_when_nothing_suitable():
    entries = [
        {"id": "x", "duration": 5, "subtitles": {}, "automatic_captions": {}},
    ]
    assert youtube.pick_candidate(entries) is None
```

- [ ] **Step 2: 行 test 確認 fail**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_youtube.py -q
```
Expected: FAIL —— `ModuleNotFoundError`。

- [ ] **Step 3: 寫實作**

Create `backend/app/youtube.py`:
```python
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
```

- [ ] **Step 4: 行 test 確認 pass**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_youtube.py -q
```
Expected: PASS（4 passed）。（淨係測 `pick_candidate` 純邏輯，唔掂網絡。）

- [ ] **Step 5: 寫一個 opt-in 真網絡 smoke test（預設 skip）**

加入 `backend/tests/test_youtube.py`:
```python
import os
import pytest


@pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="set RUN_NETWORK_TESTS=1 to run real yt-dlp search",
)
def test_real_search_returns_entries():
    entries = youtube.search("BoJack Horseman best scenes", limit=3)
    assert len(entries) >= 1
    assert "id" in entries[0]
```

- [ ] **Step 6: Commit**

```powershell
git add app/youtube.py tests/test_youtube.py
git commit -m "feat: yt-dlp search/download wrapper with candidate filtering"
```

---

## Task 6: Whisper wrapper transcribe.py

**用途**：包 faster-whisper。提供 (a) 轉原音成 segment list（餵 segmenter）；(b) 轉使用者錄音成純文字（餵 compare）。Lazy load model（第一次先載）。

**Files:**
- Create: `backend/app/transcribe.py`
- Test: `backend/tests/test_transcribe.py`

- [ ] **Step 1: 寫 failing test（用假 model 測 segment 格式轉換）**

Create `backend/tests/test_transcribe.py`:
```python
from app import transcribe


class _FakeSeg:
    def __init__(self, text, start, end):
        self.text, self.start, self.end = text, start, end


class _FakeModel:
    def transcribe(self, path, **kwargs):
        segs = [_FakeSeg(" Hello there.", 0.0, 1.2),
                _FakeSeg(" General Kenobi.", 1.2, 2.5)]
        return segs, {"language": "en"}


def test_transcribe_segments_shape(monkeypatch):
    monkeypatch.setattr(transcribe, "_get_model", lambda: _FakeModel())
    out = transcribe.transcribe_segments("dummy.m4a")
    assert out == [
        {"text": "Hello there.", "start": 0.0, "end": 1.2},
        {"text": "General Kenobi.", "start": 1.2, "end": 2.5},
    ]


def test_transcribe_text_joins(monkeypatch):
    monkeypatch.setattr(transcribe, "_get_model", lambda: _FakeModel())
    text = transcribe.transcribe_text("dummy.m4a")
    assert text == "Hello there. General Kenobi."
```

- [ ] **Step 2: 行 test 確認 fail**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_transcribe.py -q
```
Expected: FAIL —— `ModuleNotFoundError`。

- [ ] **Step 3: 寫實作**

Create `backend/app/transcribe.py`:
```python
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
```

- [ ] **Step 4: 行 test 確認 pass**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_transcribe.py -q
```
Expected: PASS（2 passed）。

- [ ] **Step 5: Commit**

```powershell
git add app/transcribe.py tests/test_transcribe.py
git commit -m "feat: faster-whisper transcription wrapper (lazy load)"
```

---

## Task 7: FastAPI 後端 main.py（route 接駁，TestClient + monkeypatch）

**用途**：串起所有部件，開 4 條 API + serve 前端靜態檔。

API：
- `GET /api/shows` → 劇集清單
- `POST /api/materials?show_id=bojack` → 自動搵片 + 抽音 + 轉文字 + 切句 + 入庫，回傳 material_id + sentences
- `POST /api/attempts` （multipart：sentence_id + 錄音 file）→ 轉錄音、對比、記錄，回傳 tokens + score
- `GET /api/audio/{youtube_id}` → 串原音檔（前端播放 + 慢放用）

**Files:**
- Create: `backend/app/main.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: 寫 failing test（/api/shows 同 monkeypatch 嘅 materials 流程）**

Create `backend/tests/test_api.py`:
```python
import io

from fastapi.testclient import TestClient

from app import main


def get_client(tmp_path, monkeypatch):
    # 用臨時 DB
    from app.db import Database
    monkeypatch.setattr(main, "db", Database(tmp_path / "t.sqlite3"))
    return TestClient(main.app)


def test_list_shows(tmp_path, monkeypatch):
    client = get_client(tmp_path, monkeypatch)
    r = client.get("/api/shows")
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert "bojack" in ids


def test_create_material_success(tmp_path, monkeypatch):
    client = get_client(tmp_path, monkeypatch)

    monkeypatch.setattr(main.youtube, "find_clip", lambda q: {
        "youtube_id": "abc", "title": "clip", "audio_path": "data/audio/abc.m4a"})
    monkeypatch.setattr(main.transcribe, "transcribe_segments", lambda p: [
        {"text": "I'm a horse.", "start": 0.0, "end": 1.5}])

    r = client.post("/api/materials", params={"show_id": "bojack"})
    assert r.status_code == 200
    body = r.json()
    assert body["material_id"] >= 1
    assert body["sentences"][0]["text"] == "I'm a horse."
    assert "id" in body["sentences"][0]


def test_create_material_no_clip_found(tmp_path, monkeypatch):
    client = get_client(tmp_path, monkeypatch)
    monkeypatch.setattr(main.youtube, "find_clip", lambda q: None)
    r = client.post("/api/materials", params={"show_id": "bojack"})
    assert r.status_code == 404


def test_submit_attempt_returns_tokens(tmp_path, monkeypatch):
    client = get_client(tmp_path, monkeypatch)
    # 先建 material + sentence
    monkeypatch.setattr(main.youtube, "find_clip", lambda q: {
        "youtube_id": "abc", "title": "clip", "audio_path": "p.m4a"})
    monkeypatch.setattr(main.transcribe, "transcribe_segments", lambda p: [
        {"text": "I am a horse.", "start": 0.0, "end": 1.5}])
    mat = client.post("/api/materials", params={"show_id": "bojack"}).json()
    sid = mat["sentences"][0]["id"]

    # 使用者錄音 → 假裝轉文字做 "I am a house"
    monkeypatch.setattr(main.transcribe, "transcribe_text", lambda p: "I am a house")
    files = {"audio": ("rec.webm", io.BytesIO(b"fake"), "audio/webm")}
    r = client.post("/api/attempts", data={"sentence_id": str(sid)}, files=files)
    assert r.status_code == 200
    body = r.json()
    assert "tokens" in body and "score" in body
    assert any(t["status"] == "wrong" for t in body["tokens"])
```

- [ ] **Step 2: 行 test 確認 fail**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_api.py -q
```
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.main'`。

- [ ] **Step 3: 寫實作**

Create `backend/app/main.py`:
```python
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import compare, segmenter, shows, transcribe, youtube
from app.config import AUDIO_DIR, DB_PATH
from app.db import Database

app = FastAPI(title="Shadowing")
db = Database(DB_PATH)


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
async def api_attempt(sentence_id: int = Form(...), audio: UploadFile = Form(...)):
    # 將錄音存臨時檔畀 whisper
    suffix = Path(audio.filename or "rec.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(audio.file, tmp)
        tmp_path = tmp.name

    spoken = transcribe.transcribe_text(tmp_path)
    Path(tmp_path).unlink(missing_ok=True)

    # 攞返原句文字
    row = db.conn.execute(
        "SELECT text FROM sentences WHERE id = ?", (sentence_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "sentence not found")

    result = compare.compare_sentence(row["text"], spoken)
    status = "pass" if result["score"] >= 0.8 else "retry"
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
```

- [ ] **Step 4: 行 test 確認 pass**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_api.py -q
```
Expected: PASS（5 passed）。

- [ ] **Step 5: 行晒全部 test**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
Expected: 全綠（compare 5 + segmenter 4 + shows 4 + db 2 + youtube 4 + transcribe 2 + api 5 = 26 passed，network test skipped）。

- [ ] **Step 6: Commit**

```powershell
git add app/main.py tests/test_api.py
git commit -m "feat: FastAPI endpoints wiring shows, materials, attempts, audio"
```

---

## Task 8: 前端 PWA（index.html + app.js + style.css）

**用途**：揀劇 → 撳「搵片」→ 逐句播原音（慢放/loop）→ 錄跟讀 → 顯示綠紅對比 → 並排重聽 → 標過咗/再練。

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/app.js`
- Create: `frontend/style.css`

> 前端無自動化單元測試（瀏覽器 UI）；驗收用 Task 10 嘅手動 smoke test。

- [ ] **Step 1: 寫 `frontend/index.html`**

Create `frontend/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Shadowing</title>
  <link rel="manifest" href="/manifest.webmanifest" />
  <link rel="stylesheet" href="/style.css" />
</head>
<body>
  <header><h1>Shadowing</h1></header>

  <section id="show-picker">
    <h2>揀一套劇</h2>
    <div id="shows" class="shows"></div>
    <button id="find-btn" disabled>搵片開始練</button>
    <p id="status" class="status"></p>
  </section>

  <section id="practice" hidden>
    <p id="material-title" class="title"></p>
    <p id="progress" class="progress"></p>

    <blockquote id="ref-text" class="ref"></blockquote>

    <div class="controls">
      <button id="play-orig">▶ 播原句</button>
      <label><input type="checkbox" id="slow" /> 0.75x 慢放</label>
      <label><input type="checkbox" id="loop" /> Loop</label>
    </div>

    <div class="controls">
      <button id="record">● 錄跟讀</button>
      <button id="play-mine" disabled>▶ 聽返自己</button>
    </div>

    <div id="result" class="result" hidden>
      <p class="score">分數：<span id="score"></span></p>
      <p id="tokens" class="tokens"></p>
    </div>

    <div class="controls">
      <button id="mark-pass">✓ 過咗，下一句</button>
      <button id="mark-retry">↻ 再練</button>
    </div>
  </section>

  <audio id="orig-audio"></audio>
  <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: 寫 `frontend/style.css`**

Create `frontend/style.css`:
```css
* { box-sizing: border-box; }
body { font-family: system-ui, sans-serif; margin: 0; padding: 1rem;
       max-width: 640px; margin-inline: auto; background: #faf7f2; color: #222; }
header h1 { font-size: 1.4rem; }
.shows { display: flex; flex-wrap: wrap; gap: .5rem; margin: .5rem 0; }
.shows button { padding: .5rem .8rem; border: 1px solid #ccc; border-radius: 8px;
                background: #fff; cursor: pointer; }
.shows button.selected { background: #2d6cdf; color: #fff; border-color: #2d6cdf; }
button { font-size: 1rem; padding: .6rem 1rem; border-radius: 8px;
         border: 1px solid #888; background: #fff; cursor: pointer; }
button:disabled { opacity: .5; cursor: not-allowed; }
.controls { display: flex; gap: .6rem; align-items: center; margin: .8rem 0;
            flex-wrap: wrap; }
.ref { font-size: 1.3rem; line-height: 1.6; background: #fff; padding: 1rem;
       border-radius: 10px; border: 1px solid #eee; }
.status { color: #666; min-height: 1.2em; }
.tokens span { padding: 0 .15em; border-radius: 4px; }
.tok-ok { color: #137333; }
.tok-wrong { color: #c5221f; text-decoration: underline; }
.tok-missing { color: #c5221f; background: #fde0df; }
.tok-extra { color: #b06000; font-style: italic; }
#record.recording { background: #c5221f; color: #fff; }
```

- [ ] **Step 3: 寫 `frontend/app.js`**

Create `frontend/app.js`:
```javascript
const API = "";  // 同源
let selectedShow = null;
let material = null;       // {material_id, youtube_id, title, sentences}
let idx = 0;
let mediaRecorder = null;
let recordedChunks = [];
let myAudioUrl = null;

const $ = (id) => document.getElementById(id);

async function loadShows() {
  const res = await fetch(`${API}/api/shows`);
  const shows = await res.json();
  const wrap = $("shows");
  wrap.innerHTML = "";
  shows.forEach((s) => {
    const b = document.createElement("button");
    b.textContent = s.name;
    b.onclick = () => {
      selectedShow = s.id;
      [...wrap.children].forEach((c) => c.classList.remove("selected"));
      b.classList.add("selected");
      $("find-btn").disabled = false;
    };
    wrap.appendChild(b);
  });
}

$("find-btn").onclick = async () => {
  $("status").textContent = "搵緊片同處理緊…（第一次載 Whisper model 會耐少少）";
  $("find-btn").disabled = true;
  try {
    const res = await fetch(`${API}/api/materials?show_id=${selectedShow}`,
                            { method: "POST" });
    if (!res.ok) {
      const err = await res.json();
      $("status").textContent = "✗ " + (err.detail || "出錯，試下另一套");
      $("find-btn").disabled = false;
      return;
    }
    material = await res.json();
    idx = 0;
    $("show-picker").hidden = true;
    $("practice").hidden = false;
    $("material-title").textContent = material.title;
    $("orig-audio").src = `${API}/api/audio/${material.youtube_id}`;
    loadSentence();
  } catch (e) {
    $("status").textContent = "✗ 網絡或伺服器出錯：" + e.message;
    $("find-btn").disabled = false;
  }
};

function loadSentence() {
  const s = material.sentences[idx];
  $("ref-text").textContent = s.text;
  $("progress").textContent = `第 ${idx + 1} / ${material.sentences.length} 句`;
  $("result").hidden = true;
  $("play-mine").disabled = true;
}

$("play-orig").onclick = () => {
  const s = material.sentences[idx];
  const a = $("orig-audio");
  a.playbackRate = $("slow").checked ? 0.75 : 1.0;
  a.currentTime = s.start;
  a.play();
  const stopAt = () => {
    if (a.currentTime >= s.end) {
      if ($("loop").checked) { a.currentTime = s.start; }
      else { a.pause(); a.removeEventListener("timeupdate", stopAt); }
    }
  };
  a.addEventListener("timeupdate", stopAt);
};

$("record").onclick = async () => {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    alert("冇咪權限：請喺瀏覽器允許麥克風使用。");
    return;
  }
  recordedChunks = [];
  mediaRecorder = new MediaRecorder(stream);
  mediaRecorder.ondataavailable = (e) => recordedChunks.push(e.data);
  mediaRecorder.onstop = () => {
    stream.getTracks().forEach((t) => t.stop());
    $("record").classList.remove("recording");
    $("record").textContent = "● 錄跟讀";
    const blob = new Blob(recordedChunks, { type: "audio/webm" });
    if (myAudioUrl) URL.revokeObjectURL(myAudioUrl);
    myAudioUrl = URL.createObjectURL(blob);
    $("play-mine").disabled = false;
    submitAttempt(blob);
  };
  mediaRecorder.start();
  $("record").classList.add("recording");
  $("record").textContent = "■ 停止";
};

$("play-mine").onclick = () => {
  if (myAudioUrl) new Audio(myAudioUrl).play();
};

async function submitAttempt(blob) {
  const s = material.sentences[idx];
  const fd = new FormData();
  fd.append("sentence_id", String(s.id));
  fd.append("audio", blob, "rec.webm");
  $("status").textContent = "對比緊…";
  const res = await fetch(`${API}/api/attempts`, { method: "POST", body: fd });
  $("status").textContent = "";
  const body = await res.json();
  renderResult(body);
}

function renderResult(body) {
  $("score").textContent = Math.round(body.score * 100) + "%";
  const tEl = $("tokens");
  tEl.innerHTML = "";
  body.tokens.forEach((t) => {
    const span = document.createElement("span");
    span.textContent = t.ref + " ";
    span.className = "tok-" + t.status;
    tEl.appendChild(span);
  });
  $("result").hidden = false;
}

function nextSentence() {
  if (idx + 1 < material.sentences.length) { idx++; loadSentence(); }
  else { $("ref-text").textContent = "🎉 呢條片練完！返去揀過套劇。";
         $("result").hidden = true; }
}

$("mark-pass").onclick = nextSentence;
$("mark-retry").onclick = () => { $("result").hidden = true;
                                  $("play-mine").disabled = true; };

loadShows();
```

- [ ] **Step 4: Commit**

```powershell
git add frontend/index.html frontend/app.js frontend/style.css
git commit -m "feat: PWA frontend - show picker, player, recorder, compare UI"
```

---

## Task 9: PWA manifest + service worker

**用途**：令個 app 可以「加到手機主畫面」當 app 用。

**Files:**
- Create: `frontend/manifest.webmanifest`
- Create: `frontend/sw.js`
- Modify: `frontend/index.html`（註冊 service worker）

- [ ] **Step 1: 寫 `frontend/manifest.webmanifest`**

Create `frontend/manifest.webmanifest`:
```json
{
  "name": "Shadowing",
  "short_name": "Shadowing",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#faf7f2",
  "theme_color": "#2d6cdf",
  "icons": [
    {
      "src": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='192' height='192'><rect width='192' height='192' fill='%232d6cdf'/><text x='96' y='130' font-size='120' text-anchor='middle' fill='white'>S</text></svg>",
      "sizes": "192x192",
      "type": "image/svg+xml"
    }
  ]
}
```
（用 inline SVG icon，唔使另外整圖。）

- [ ] **Step 2: 寫 `frontend/sw.js`**

Create `frontend/sw.js`:
```javascript
// 最簡 service worker：cache 靜態外殼，API 一律走網絡。
const CACHE = "shadowing-v1";
const SHELL = ["/", "/index.html", "/app.js", "/style.css",
               "/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith("/api/")) return;  // API 唔 cache
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request))
  );
});
```

- [ ] **Step 3: 喺 index.html 註冊 service worker**

Modify `frontend/index.html` —— 喺 `<script src="/app.js"></script>` 之後加：
```html
  <script>
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js");
    }
  </script>
```

- [ ] **Step 4: Commit**

```powershell
git add frontend/manifest.webmanifest frontend/sw.js frontend/index.html
git commit -m "feat: PWA manifest and service worker for installability"
```

---

## Task 10: End-to-end 手動 smoke test + README

**用途**：真係行一次成個流程，確認跑得通；寫低點起 server。

**Files:**
- Create: `README.md`

- [ ] **Step 1: 寫 `README.md`**

Create `README.md`:
```markdown
# Shadowing

英文跟讀練習 PWA：揀套成人動畫 → 自動搵 YouTube clip → 逐句播原音、錄跟讀、
Whisper 轉文字後同原句逐字對比畀 feedback。本機跑，唔使收費 API。

## 起 server

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

電腦開：http://localhost:8000
手機（同一 WiFi）開：http://<電腦區網IP>:8000 → 加到主畫面當 app 用。

## 行 test

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
# 真網絡搜尋測試（會落 YouTube）：
$env:RUN_NETWORK_TESTS=1; .\.venv\Scripts\python.exe -m pytest tests/test_youtube.py -q
```

## 法律
自動下載 YouTube 片段僅供個人學習離線練習用，唔作再分享。
```

- [ ] **Step 2: 起 server**

Run:
```powershell
cd "G:\我的雲端硬碟\AI\Shadowing\backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```
Expected: `Uvicorn running on http://127.0.0.1:8000`。

- [ ] **Step 3: 手動行成個流程（在瀏覽器）**

開 http://localhost:8000，逐項 check：
1. [ ] 見到劇集清單（6 套）
2. [ ] 揀一套 → 撳「搵片開始練」→ 等處理（第一次載 model 較耐）
3. [ ] 成功入到練習頁，見到第一句英文
4. [ ] 撳「▶ 播原句」聽到原音；剔「慢放」再播會慢
5. [ ] 撳「● 錄跟讀」（首次彈咪權限，允許）→ 講一次 → 撳停
6. [ ] 見到分數 + 綠/紅逐字對比
7. [ ] 撳「聽返自己」播到自己把聲
8. [ ] 撳「過咗，下一句」跳到下一句

如果第 2 步「搵唔到啱嘅片」→ 試另一套劇（部分劇英文字幕較少屬正常）。

- [ ] **Step 4: 確認全部 test 仍然綠**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
Expected: 全綠。

- [ ] **Step 5: Commit**

```powershell
git add README.md
git commit -m "docs: README with run + smoke test instructions"
```

---

## Self-Review（規劃者已核對）

**Spec coverage**：
- 自動搜尋素材（揀劇）→ Task 3 + Task 5 + Task 7 `/api/materials` ✓
- 抽音 + 字幕 → Task 5 `find_clip` / `download_audio` ✓
- 切句 → Task 2 segmenter ✓
- 播原句（慢放 + loop）→ Task 8 `play-orig` ✓
- 錄音 → Whisper 轉文字 → Task 6 + Task 8 recorder ✓
- 逐字對比標綠紅 → Task 1 compare + Task 8 `renderResult` ✓
- 並排重聽 → Task 8 `play-mine` ✓
- 標過咗/再練 + SQLite 記錄 → Task 4 db + Task 7 `/api/attempts` ✓
- PWA 加主畫面 → Task 9 ✓
- 錯誤處理（搵唔到片/無咪權限/model 載入慢）→ Task 7 HTTPException + Task 8 status/alert ✓

**Type consistency**：sentence dict 一路用 `{id, idx, text, start, end}`；compare 回傳 `{tokens:[{ref,status}], score}`；attempt 回傳加埋 `{spoken, status}`。前後一致 ✓。`find_clip` 回傳 `{youtube_id, title, audio_path}` ↔ `db.add_material(show_id, title, youtube_id, audio_path)` 對齊 ✓。

**Placeholder scan**：每個 code step 有完整 code，無 TBD/TODO ✓。
```
