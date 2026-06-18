# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Shadowing — a local English shadowing-practice PWA. Pick an adult-animation show → backend auto-sources a clip (a show's bound Bilibili collection if it has one, otherwise a yt-dlp YouTube search) → downloads audio → faster-whisper transcribes it into timed sentences → the user plays each sentence, records themselves shadowing → their recording is transcribed and compared word-by-word (difflib) for ok/wrong/missing/extra feedback → SQLite stores attempts. Everything runs locally; no paid APIs. (Source clips are English-spoken by virtue of the show list — we transcribe the audio with Whisper rather than relying on any platform's subtitles.)

## Commands

All Python commands run through the venv interpreter from the `backend/` directory (Windows / PowerShell). The path contains non-ASCII characters — always quote it.

```powershell
# one-time setup
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# run the app (serves API + frontend at http://localhost:8000)
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# full test suite
.\.venv\Scripts\python.exe -m pytest -q

# a single test
.\.venv\Scripts\python.exe -m pytest tests/test_compare.py::test_missing_word_marked -v

# opt-in real-network test (actually hits YouTube; skipped by default)
$env:RUN_NETWORK_TESTS=1; .\.venv\Scripts\python.exe -m pytest tests/test_youtube.py -q
```

There is no frontend build step or linter — `frontend/` is plain static HTML/JS/CSS served by FastAPI's StaticFiles mount.

## Architecture

The backend is a thin FastAPI layer (`backend/app/main.py`) wiring together small, independently-tested modules. The two endpoints that matter each compose several modules:

- **`POST /api/materials?show_id=`** is the ingestion pipeline: pick a clip → `transcribe.transcribe_segments` (faster-whisper) → `segmenter.segment_transcript` (merge Whisper fragments into `.!?`-terminated sentences with timecodes) → persist via `db`. Returns `{material_id, youtube_id, title, sentences}`. Clip selection prefers a show's bound Bilibili collection (`shows.get_bilibili_collection` → `bilibili.find_clip`, picks a random part from a multi-P collection) and falls back to `youtube.find_clip` (`shows.get_search_query` → yt-dlp search + duration filter + download) when there's no collection or Bilibili can't be reached. Both return the same `{youtube_id, title, audio_path}` shape so downstream code is source-agnostic.
- **`POST /api/attempts`** is the scoring path: save uploaded recording to a temp file → `transcribe.transcribe_text` → `db.get_sentence_text` → `compare.compare_sentence` → `db.record_attempt`. Returns `{spoken, tokens, score, status}`.

`compare.py` is the core: it normalizes both strings (lowercase, strip punctuation, drop apostrophes so "I'm"→"im"; hyphens split into two tokens) and aligns them with `difflib.SequenceMatcher`. Every token (including spoken-only "extra" words) carries a `ref` key, so the frontend can always render `tokens[].ref` + `tokens[].status`. `score` = (#ok) / (len of reference tokens).

### Data shape contract (must stay aligned end-to-end)

- A sentence is `{id, idx, text, start, end}` everywhere (db rows, API responses, `app.js`).
- `/api/audio/{youtube_id}` globs `data/audio/{youtube_id}.*`; `download_audio` prefers m4a but may yield webm/opus, so `api_audio` sets an explicit `media_type` per extension (see `_AUDIO_MIME`) — keep that map in sync if new formats appear.
- `app.js` plays a sentence by seeking the single `<audio>` element to `sentence.start` and stopping at `sentence.end` via a `timeupdate` listener; it waits for `loadedmetadata` before the first seek (a cold seek is clamped to 0 otherwise).

### Storage & lifecycle

- SQLite at `backend/data/shadowing.sqlite3`; downloaded audio at `backend/data/audio/` (both gitignored). The `db` module is the only place that touches SQL — add query methods there rather than reaching into `db.conn` from `main.py`.
- The shared `Database` connection uses `check_same_thread=False`; tests monkeypatch `main.db` with a fresh temp-file DB per test.

## Testing approach

Strict TDD throughout. Pure logic (`compare`, `segmenter`, `db`, `shows`) is unit-tested directly. External IO is never hit in the default suite: `youtube` tests cover only the pure `pick_candidate` filter; `transcribe` tests inject a fake model by monkeypatching `_get_model`; API tests use FastAPI `TestClient` with `youtube.find_clip` / `transcribe.*` monkeypatched. faster-whisper is lazy-loaded (`transcribe._get_model`) so importing modules never loads the model.

## Constraints

- Source clips come only from YouTube/Bilibili (yt-dlp); Netflix/Disney+ full episodes are DRM-protected and intentionally out of scope. Downloaded clips are for personal offline practice only.
- Some sources block unauthenticated yt-dlp (YouTube occasionally asks to "confirm you're not a bot"; Bilibili returns HTTP 412). `config.py` enables cookies via a Netscape `cookies.txt` in `backend/` (preferred, `YTDLP_COOKIE_FILE`) or by borrowing browser cookies (`YTDLP_COOKIES_FROM_BROWSER`); with neither, Bilibili sourcing just returns `None` and the pipeline falls back to YouTube. `youtube._base_opts()` is the single place that wires cookies into every yt-dlp call (and `bilibili` reuses it).
- Keep new work scoped to the v1 core loop. Deferred to v2 (see README): user-uploaded audio, a progress dashboard, vocabulary cards.
