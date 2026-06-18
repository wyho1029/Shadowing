# Replenisher（磨片廠）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將現有 yt-dlp + Whisper pipeline 重構成一個可由 Windows Task Scheduler 每日跑嘅腳本，自動維持每套劇嘅「未練片」緩衝量，並將音檔 + `manifest.json` 寫入 Drive 同步資料夾。

**Architecture:** 三個新 Python module（純邏輯為主、外部 IO 注入）：`sourcing`（Bilibili 優先 + YouTube fallback 的取片）、`library`（讀寫 `manifest.json` / `progress.json`，原子寫入）、`replenish`（orchestration + CLI）。重用現有 `youtube` / `bilibili` / `transcribe` / `segmenter` 不變。現行 FastAPI / SQLite **暫不動**（留到 Plan 2 練習亭落實時退役），確保現有測試仍綠。

**Tech Stack:** Python 3.10、stdlib（`json` / `shutil` / `pathlib` / `os` / `datetime`）、pytest（沿用現有 monkeypatch + `tmp_path` 模式）。Plan 1 無新增依賴。

**Spec:** [docs/superpowers/specs/2026-06-18-shadowing-google-rebuild-design.md](../specs/2026-06-18-shadowing-google-rebuild-design.md)

> **Commit 慣例：** 本 repo commit message 結尾要加 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer。以下各步 `git commit` 為簡潔只寫標題，執行時請補上 trailer。所有指令喺 `backend/` 目錄、用 venv interpreter 跑（路徑含非 ASCII，記得引號）。

---

## 契約修正（相對 spec §6）

- manifest 嘅每條 clip 存 **`audio_file`**（檔名，例如 `"BV1sH4y1c7dR_p3.m4a"`）而非 spec 寫嘅 `audio_url`。原因：本機 replenisher 冇 Drive API，唔知 Drive 連結。Plan 2 嘅 Apps Script 會喺派發 manifest 時將 `audio_file` 解析成 Drive 直connect link（`audio_url`）。
- buffer 度量單位定為「**每套劇未練 clip 條數**」（`TARGET_UNPLAYED_PER_SHOW`），解決 spec §11「target buffer 數值」一項。預設 `3`。

## File Structure

| 檔案 | 責任 | 動作 |
|------|------|------|
| `backend/app/config.py` | 加 library 路徑常數 + target buffer | Modify |
| `backend/app/library.py` | manifest / progress 讀寫（原子）、加 clip、計未練數、計需補數 | Create |
| `backend/app/sourcing.py` | 取片：Bilibili 合集優先、YouTube fallback，正規化 clip dict | Create |
| `backend/app/replenish.py` | orchestration（`replenish_once`）+ 搬檔 + CLI `main()` | Create |
| `backend/tests/test_library.py` | library 單元測試 | Create |
| `backend/tests/test_sourcing.py` | sourcing 單元測試（monkeypatch bilibili/youtube/shows） | Create |
| `backend/tests/test_replenish.py` | replenish orchestration 單元測試（注入假 collaborators） | Create |

manifest.json / progress.json schema（library 產生）：

```jsonc
// manifest.json
{
  "version": 1,
  "updated_at": "2026-06-18T03:00:00+00:00",
  "shows": [
    { "id": "bojack", "name": "BoJack Horseman",
      "clips": [
        { "clip_id": "BV1sH4y1c7dR_p3", "source": "bilibili", "title": "...",
          "audio_file": "BV1sH4y1c7dR_p3.m4a",
          "sentences": [ {"idx":0,"text":"...","start":1.2,"end":4.8} ] } ] }
  ]
}
// progress.json
{ "version": 1, "done_clips": [], "attempts": [] }
```

---

## Task 1: config — library 路徑 + target buffer

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: 加常數同建資料夾**

喺 `config.py` 末（`AUDIO_DIR.mkdir(exist_ok=True)` 之後）加：

```python
# ── 新片庫（Plan 1 Replenisher）──────────────────────────────────────────────
# 磨片廠寫呢度;Drive 桌面版自動 sync 上雲(整個 project 已喺 Drive 同步資料夾)。
LIBRARY_DIR = DATA_DIR / "library"
LIBRARY_AUDIO_DIR = LIBRARY_DIR / "audio"
MANIFEST_PATH = LIBRARY_DIR / "manifest.json"
PROGRESS_PATH = LIBRARY_DIR / "progress.json"

# 每套劇要保持幾多條「未練」片;低過就補。
TARGET_UNPLAYED_PER_SHOW = 3

LIBRARY_DIR.mkdir(exist_ok=True)
LIBRARY_AUDIO_DIR.mkdir(exist_ok=True)
```

- [ ] **Step 2: 驗證 import**

Run: `.\.venv\Scripts\python.exe -c "from app.config import MANIFEST_PATH, LIBRARY_AUDIO_DIR, TARGET_UNPLAYED_PER_SHOW; print(MANIFEST_PATH)"`
Expected: 印出 manifest 路徑、無 error。

- [ ] **Step 3: 確認現有測試仍綠**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: 全部 PASS（無新測試，純加常數）。

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py
git commit -m "feat(replenish): add library paths and target buffer to config"
```

---

## Task 2: library — manifest / progress 讀寫 + 緩衝計算

**Files:**
- Create: `backend/app/library.py`
- Test: `backend/tests/test_library.py`

- [ ] **Step 1: 寫失敗測試**

`backend/tests/test_library.py`：

```python
from app import library


def test_load_missing_returns_empty(tmp_path):
    m = library.load_manifest(tmp_path / "nope.json")
    assert m["shows"] == [] and m["version"] == 1
    p = library.load_progress(tmp_path / "nope.json")
    assert p["done_clips"] == []


def _clip(cid):
    return {"clip_id": cid, "source": "youtube", "title": cid}


def test_add_clip_creates_show_and_indexes_sentences(tmp_path):
    m = library.load_manifest(tmp_path / "m.json")
    library.add_clip(m, "bojack", "BoJack Horseman", _clip("abc"), "abc.m4a",
                     [{"text": "Hi.", "start": 0.0, "end": 1.0},
                      {"text": "Bye.", "start": 1.0, "end": 2.0}])
    show = m["shows"][0]
    assert show["id"] == "bojack" and show["name"] == "BoJack Horseman"
    clip = show["clips"][0]
    assert clip["clip_id"] == "abc"
    assert clip["source"] == "youtube"
    assert clip["audio_file"] == "abc.m4a"
    assert [s["idx"] for s in clip["sentences"]] == [0, 1]
    assert clip["sentences"][1]["text"] == "Bye."


def test_add_clip_reuses_existing_show_entry(tmp_path):
    m = library.load_manifest(tmp_path / "m.json")
    library.add_clip(m, "bojack", "BoJack", _clip("a"), "a.m4a",
                     [{"text": "x.", "start": 0, "end": 1}])
    library.add_clip(m, "bojack", "BoJack", _clip("b"), "b.m4a",
                     [{"text": "y.", "start": 0, "end": 1}])
    assert len(m["shows"]) == 1
    assert len(m["shows"][0]["clips"]) == 2


def test_existing_clip_ids(tmp_path):
    m = library.load_manifest(tmp_path / "m.json")
    library.add_clip(m, "bojack", "BoJack", _clip("a"), "a.m4a",
                     [{"text": "x.", "start": 0, "end": 1}])
    assert library.existing_clip_ids(m) == {"a"}


def test_unplayed_excludes_done_clips(tmp_path):
    m = library.load_manifest(tmp_path / "m.json")
    for cid in ("a", "b"):
        library.add_clip(m, "bojack", "BoJack", _clip(cid), f"{cid}.m4a",
                         [{"text": "x.", "start": 0, "end": 1}])
    prog = {"version": 1, "done_clips": ["a"], "attempts": []}
    assert library.unplayed_count(m, prog, "bojack") == 1


def test_clips_needed_per_show(tmp_path):
    m = library.load_manifest(tmp_path / "m.json")
    library.add_clip(m, "bojack", "BoJack", _clip("a"), "a.m4a",
                     [{"text": "x.", "start": 0, "end": 1}])
    prog = library.load_progress(tmp_path / "p.json")
    needs = library.clips_needed(m, prog, target=3, show_ids=["bojack", "simpsons"])
    assert needs == {"bojack": 2, "simpsons": 3}


def test_save_manifest_is_atomic_and_reloads(tmp_path):
    path = tmp_path / "m.json"
    m = library.load_manifest(path)
    library.add_clip(m, "bojack", "BoJack", _clip("a"), "a.m4a",
                     [{"text": "x.", "start": 0, "end": 1}])
    library.save_manifest(m, path)
    assert path.exists()
    assert not (tmp_path / "m.json.tmp").exists()   # temp 已 rename 走
    reloaded = library.load_manifest(path)
    assert reloaded["shows"][0]["clips"][0]["clip_id"] == "a"
    assert reloaded["updated_at"] is not None
```

- [ ] **Step 2: 跑測試確認 fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_library.py -q`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.library'`）。

- [ ] **Step 3: 寫實作**

`backend/app/library.py`：

```python
"""片庫狀態：manifest.json（生產出嚟嘅片+逐句字幕）同 progress.json（練到邊）。

全部寫入 Drive 同步資料夾，靠 Drive 桌面版 sync 上雲。寫入用「先寫 temp 再 rename」
原子操作，避免 Drive sync 到寫一半嘅檔。manifest 存 audio_file（檔名）;Drive 連結
由 Plan 2 嘅 Apps Script 解析。
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

VERSION = 1


def _empty_manifest() -> dict:
    return {"version": VERSION, "updated_at": None, "shows": []}


def _empty_progress() -> dict:
    return {"version": VERSION, "done_clips": [], "attempts": []}


def load_manifest(path) -> dict:
    p = Path(path)
    if not p.exists():
        return _empty_manifest()
    return json.loads(p.read_text(encoding="utf-8"))


def load_progress(path) -> dict:
    p = Path(path)
    if not p.exists():
        return _empty_progress()
    return json.loads(p.read_text(encoding="utf-8"))


def _atomic_write_json(data: dict, path) -> None:
    p = Path(path)
    tmp = p.parent / (p.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)   # 同檔系統下原子 rename


def save_manifest(manifest: dict, path) -> None:
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_write_json(manifest, path)


def _show_entry(manifest: dict, show_id: str, show_name: str) -> dict:
    for s in manifest["shows"]:
        if s["id"] == show_id:
            return s
    entry = {"id": show_id, "name": show_name, "clips": []}
    manifest["shows"].append(entry)
    return entry


def existing_clip_ids(manifest: dict) -> set:
    return {c["clip_id"] for s in manifest["shows"] for c in s["clips"]}


def add_clip(manifest: dict, show_id: str, show_name: str,
             clip: dict, audio_file: str, sentences: list[dict]) -> None:
    entry = _show_entry(manifest, show_id, show_name)
    entry["clips"].append({
        "clip_id": clip["clip_id"],
        "source": clip["source"],
        "title": clip["title"],
        "audio_file": audio_file,
        "sentences": [
            {"idx": i, "text": s["text"], "start": s["start"], "end": s["end"]}
            for i, s in enumerate(sentences)
        ],
    })


def unplayed_count(manifest: dict, progress: dict, show_id: str) -> int:
    done = set(progress.get("done_clips", []))
    for s in manifest["shows"]:
        if s["id"] == show_id:
            return sum(1 for c in s["clips"] if c["clip_id"] not in done)
    return 0


def clips_needed(manifest: dict, progress: dict, target: int,
                 show_ids: list[str]) -> dict:
    """每套劇仲差幾多條未練片先到 target。只回有需要（>0）嘅。"""
    needs = {}
    for sid in show_ids:
        have = unplayed_count(manifest, progress, sid)
        if have < target:
            needs[sid] = target - have
    return needs
```

- [ ] **Step 4: 跑測試確認 pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_library.py -q`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/library.py backend/tests/test_library.py
git commit -m "feat(replenish): library module for manifest/progress + buffer calc"
```

---

## Task 3: sourcing — 取片（Bilibili 優先 + YouTube fallback）

**Files:**
- Create: `backend/app/sourcing.py`
- Test: `backend/tests/test_sourcing.py`

> 把現行 `main.py:34-41` 內嵌嘅取片邏輯抽出成可重用 function（main.py 不動，留待 Plan 2 退役）。

- [ ] **Step 1: 寫失敗測試**

`backend/tests/test_sourcing.py`：

```python
from app import sourcing


def _boom(*a, **k):
    raise AssertionError("唔應該被叫到")


def test_prefers_bilibili_when_collection(monkeypatch):
    monkeypatch.setattr(sourcing.shows, "get_bilibili_collection",
                        lambda sid: "http://b.example/BV")
    monkeypatch.setattr(sourcing.bilibili, "find_clip",
                        lambda url: {"youtube_id": "BV_p1", "title": "ep1",
                                     "audio_path": "a/BV_p1.m4a"})
    monkeypatch.setattr(sourcing.youtube, "find_clip", _boom)  # 唔應 fallback
    clip = sourcing.find_clip_for_show("bojack")
    assert clip == {"clip_id": "BV_p1", "source": "bilibili",
                    "title": "ep1", "audio_path": "a/BV_p1.m4a"}


def test_falls_back_to_youtube_when_no_collection(monkeypatch):
    monkeypatch.setattr(sourcing.shows, "get_bilibili_collection", lambda sid: None)
    monkeypatch.setattr(sourcing.shows, "get_search_query", lambda sid: "q")
    monkeypatch.setattr(sourcing.youtube, "find_clip",
                        lambda q: {"youtube_id": "yt1", "title": "T",
                                   "audio_path": "a/yt1.m4a"})
    clip = sourcing.find_clip_for_show("simpsons")
    assert clip["source"] == "youtube" and clip["clip_id"] == "yt1"


def test_bilibili_fails_then_youtube(monkeypatch):
    monkeypatch.setattr(sourcing.shows, "get_bilibili_collection",
                        lambda sid: "http://b.example/BV")
    monkeypatch.setattr(sourcing.bilibili, "find_clip", lambda url: None)
    monkeypatch.setattr(sourcing.shows, "get_search_query", lambda sid: "q")
    monkeypatch.setattr(sourcing.youtube, "find_clip",
                        lambda q: {"youtube_id": "yt1", "title": "T",
                                   "audio_path": "a/yt1.m4a"})
    clip = sourcing.find_clip_for_show("bojack")
    assert clip["source"] == "youtube"


def test_returns_none_when_all_sources_fail(monkeypatch):
    monkeypatch.setattr(sourcing.shows, "get_bilibili_collection", lambda sid: None)
    monkeypatch.setattr(sourcing.shows, "get_search_query", lambda sid: "q")
    monkeypatch.setattr(sourcing.youtube, "find_clip", lambda q: None)
    assert sourcing.find_clip_for_show("simpsons") is None
```

- [ ] **Step 2: 跑測試確認 fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_sourcing.py -q`
Expected: FAIL（`No module named 'app.sourcing'`）。

- [ ] **Step 3: 寫實作**

`backend/app/sourcing.py`：

```python
"""取片：該套劇綁咗 Bilibili 合集就優先抽,抽唔到就 fallback 去 YouTube 搜尋。

正規化成統一 clip dict（clip_id / source / title / audio_path），畀 replenish 用。
"""
from app import bilibili, shows, youtube


def find_clip_for_show(show_id: str) -> dict | None:
    clip = None
    source = None
    collection = shows.get_bilibili_collection(show_id)
    if collection:
        clip = bilibili.find_clip(collection)
        source = "bilibili"
    if clip is None:
        clip = youtube.find_clip(shows.get_search_query(show_id))
        source = "youtube"
    if clip is None:
        return None
    return {
        "clip_id": clip["youtube_id"],
        "source": source,
        "title": clip["title"],
        "audio_path": clip["audio_path"],
    }
```

- [ ] **Step 4: 跑測試確認 pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_sourcing.py -q`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/sourcing.py backend/tests/test_sourcing.py
git commit -m "feat(replenish): sourcing module (bilibili-preferred, youtube fallback)"
```

---

## Task 4: replenish — orchestration `replenish_once`

**Files:**
- Create: `backend/app/replenish.py`
- Test: `backend/tests/test_replenish.py`

- [ ] **Step 1: 寫失敗測試**

`backend/tests/test_replenish.py`：

```python
from app import library, replenish


def _fake_segment_ok(raw):
    return [{"text": "Hello world.", "start": 0.0, "end": 2.0}]


def _make_source(tmp_path):
    """source_fn：每次叫整一個新假音檔，clip_id 遞增（模擬真下載落 temp）。"""
    counter = {"n": 0}
    dl = tmp_path / "dl"
    dl.mkdir(exist_ok=True)

    def source_fn(show_id):
        counter["n"] += 1
        cid = f"{show_id}_{counter['n']}"
        f = dl / f"{cid}.m4a"
        f.write_bytes(b"fake-audio")
        return {"clip_id": cid, "source": "youtube",
                "title": cid, "audio_path": str(f)}
    return source_fn


def test_replenish_fills_to_target_and_moves_audio(tmp_path):
    audio_dir = tmp_path / "library_audio"
    audio_dir.mkdir()
    manifest = library.load_manifest(tmp_path / "m.json")
    progress = library.load_progress(tmp_path / "p.json")

    replenish.replenish_once(
        manifest=manifest, progress=progress, show_ids=["bojack"],
        show_names={"bojack": "BoJack Horseman"}, target=2,
        source_fn=_make_source(tmp_path),
        transcribe_fn=lambda p: ["raw"], segment_fn=_fake_segment_ok,
        audio_dest_dir=audio_dir,
    )
    clips = manifest["shows"][0]["clips"]
    assert len(clips) == 2
    assert (audio_dir / clips[0]["audio_file"]).exists()   # 音檔已搬入庫


def test_replenish_skips_when_source_returns_none(tmp_path):
    audio_dir = tmp_path / "la"; audio_dir.mkdir()
    manifest = library.load_manifest(tmp_path / "m.json")
    progress = library.load_progress(tmp_path / "p.json")
    replenish.replenish_once(
        manifest=manifest, progress=progress, show_ids=["bojack"],
        show_names={"bojack": "BoJack"}, target=2,
        source_fn=lambda sid: None, transcribe_fn=lambda p: ["raw"],
        segment_fn=_fake_segment_ok, audio_dest_dir=audio_dir,
    )
    assert manifest["shows"] == []


def test_replenish_skips_empty_sentences(tmp_path):
    audio_dir = tmp_path / "la"; audio_dir.mkdir()
    manifest = library.load_manifest(tmp_path / "m.json")
    progress = library.load_progress(tmp_path / "p.json")
    replenish.replenish_once(
        manifest=manifest, progress=progress, show_ids=["bojack"],
        show_names={"bojack": "BoJack"}, target=2,
        source_fn=_make_source(tmp_path), transcribe_fn=lambda p: ["raw"],
        segment_fn=lambda raw: [], audio_dest_dir=audio_dir,
    )
    assert manifest["shows"] == []


def test_replenish_respects_existing_unplayed(tmp_path):
    audio_dir = tmp_path / "la"; audio_dir.mkdir()
    manifest = library.load_manifest(tmp_path / "m.json")
    library.add_clip(manifest, "bojack", "BoJack",
                     {"clip_id": "old", "source": "youtube", "title": "old"},
                     "old.m4a", [{"text": "x.", "start": 0, "end": 1}])
    progress = library.load_progress(tmp_path / "p.json")
    replenish.replenish_once(
        manifest=manifest, progress=progress, show_ids=["bojack"],
        show_names={"bojack": "BoJack"}, target=2,
        source_fn=_make_source(tmp_path), transcribe_fn=lambda p: ["raw"],
        segment_fn=_fake_segment_ok, audio_dest_dir=audio_dir,
    )
    # 本身 1 條未練，target 2 → 只補 1 條
    assert len(manifest["shows"][0]["clips"]) == 2


def test_replenish_dedupes_repeated_clip_id(tmp_path):
    audio_dir = tmp_path / "la"; audio_dir.mkdir()
    dl = tmp_path / "dl"; dl.mkdir()

    def same_clip(show_id):
        f = dl / "dup.m4a"
        f.write_bytes(b"x")
        return {"clip_id": "dup", "source": "youtube",
                "title": "dup", "audio_path": str(f)}

    manifest = library.load_manifest(tmp_path / "m.json")
    progress = library.load_progress(tmp_path / "p.json")
    replenish.replenish_once(
        manifest=manifest, progress=progress, show_ids=["bojack"],
        show_names={"bojack": "BoJack"}, target=3,
        source_fn=same_clip, transcribe_fn=lambda p: ["raw"],
        segment_fn=_fake_segment_ok, audio_dest_dir=audio_dir,
    )
    # 同一 clip_id 只入一次
    assert len(manifest["shows"][0]["clips"]) == 1
```

- [ ] **Step 2: 跑測試確認 fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_replenish.py -q`
Expected: FAIL（`No module named 'app.replenish'`）。

- [ ] **Step 3: 寫實作**

`backend/app/replenish.py`：

```python
"""磨片廠 orchestration：補滿每套劇嘅未練緩衝，將音檔搬入庫、寫入 manifest。

重嘅嘢（下載 + Whisper 轉錄）喺呢度發生，同練習時刻完全脫鈎。
collaborators（取片 / 轉錄 / 切句）以參數注入，方便單元測試。
"""
import shutil
from pathlib import Path

from app import library, segmenter, shows, sourcing, transcribe
from app.config import (
    LIBRARY_AUDIO_DIR,
    MANIFEST_PATH,
    PROGRESS_PATH,
    TARGET_UNPLAYED_PER_SHOW,
)


def move_into_library(src_path: str, dest_dir) -> str:
    """將下載落 temp 嘅音檔搬入片庫，回傳檔名（manifest 用）。"""
    src = Path(src_path)
    dest = Path(dest_dir) / src.name
    shutil.move(str(src), str(dest))
    return dest.name


def replenish_once(*, manifest, progress, show_ids, show_names, target,
                   source_fn, transcribe_fn, segment_fn, audio_dest_dir) -> dict:
    """補滿緩衝。每套劇最多嘗試 needs 次取片（有界，避免無限迴圈）。

    個別片取唔到 / 切唔到句 / clip_id 重複 → skip 嗰條，繼續其餘。
    就地更新並回傳 manifest。
    """
    needs = library.clips_needed(manifest, progress, target, show_ids)
    seen = library.existing_clip_ids(manifest)
    for show_id, n in needs.items():
        for _ in range(n):
            clip = source_fn(show_id)
            if not clip or clip["clip_id"] in seen:
                continue
            raw = transcribe_fn(clip["audio_path"])
            sentences = segment_fn(raw)
            if not sentences:
                continue
            audio_file = move_into_library(clip["audio_path"], audio_dest_dir)
            library.add_clip(manifest, show_id, show_names[show_id],
                             clip, audio_file, sentences)
            seen.add(clip["clip_id"])
    return manifest


def main():
    manifest = library.load_manifest(MANIFEST_PATH)
    progress = library.load_progress(PROGRESS_PATH)
    show_ids = [s["id"] for s in shows.SHOWS]
    show_names = {s["id"]: s["name"] for s in shows.SHOWS}
    replenish_once(
        manifest=manifest, progress=progress, show_ids=show_ids,
        show_names=show_names, target=TARGET_UNPLAYED_PER_SHOW,
        source_fn=sourcing.find_clip_for_show,
        transcribe_fn=transcribe.transcribe_segments,
        segment_fn=segmenter.segment_transcript,
        audio_dest_dir=LIBRARY_AUDIO_DIR,
    )
    library.save_manifest(manifest, MANIFEST_PATH)
    total = sum(len(s["clips"]) for s in manifest["shows"])
    print(f"replenish done; shows={len(manifest['shows'])} clips={total}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑測試確認 pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_replenish.py -q`
Expected: 全部 PASS。

- [ ] **Step 5: 跑全套測試確認無回歸**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: 全部 PASS（包含原有測試）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/replenish.py backend/tests/test_replenish.py
git commit -m "feat(replenish): orchestration to top up per-show unplayed buffer"
```

---

## Task 5: CLI `main()` 接線測試（注入式）

**Files:**
- Test: `backend/tests/test_replenish.py`（加 case）

> `main()` 係薄 glue，但值得鎖住「會讀 manifest/progress → 跑 replenish_once → save_manifest」呢條線。

- [ ] **Step 1: 加失敗測試**

喺 `backend/tests/test_replenish.py` 末加：

```python
def test_main_loads_runs_and_saves(monkeypatch, tmp_path):
    calls = {}
    monkeypatch.setattr(replenish.library, "load_manifest",
                        lambda p: {"version": 1, "updated_at": None, "shows": []})
    monkeypatch.setattr(replenish.library, "load_progress",
                        lambda p: {"version": 1, "done_clips": [], "attempts": []})

    def fake_run(**kw):
        calls["ran"] = True
        return kw["manifest"]
    monkeypatch.setattr(replenish, "replenish_once", fake_run)

    def fake_save(manifest, path):
        calls["saved"] = True
    monkeypatch.setattr(replenish.library, "save_manifest", fake_save)

    replenish.main()
    assert calls.get("ran") and calls.get("saved")
```

- [ ] **Step 2: 跑測試確認 fail（或直接 pass）**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_replenish.py::test_main_loads_runs_and_saves -v`
Expected: 因為 `main()` 已喺 Task 4 寫好，呢個 case 應該直接 PASS。若 FAIL，按 message 修 `main()` 接線。

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_replenish.py
git commit -m "test(replenish): lock main() load/run/save wiring"
```

---

## Task 6: Windows Task Scheduler 每日排程（ops，手動）

**Files:** 無（系統設定）

> 唔係 pytest 測試，係一次性 ops 設定。重嘅下載 + Whisper 喺呢度跑。

- [ ] **Step 1: 註冊每日任務**

喺 PowerShell（非 venv 都得）跑（路徑含非 ASCII，全句用引號）：

```powershell
schtasks /Create /SC DAILY /ST 03:00 /TN "ShadowingReplenish" /F /TR "powershell -NoProfile -WindowStyle Hidden -Command \"Set-Location 'G:\我的雲端硬碟\AI\Shadowing\backend'; & '.\.venv\Scripts\python.exe' -m app.replenish\""
```

- [ ] **Step 2: 手動跑一次驗證**

Run: `schtasks /Run /TN "ShadowingReplenish"`
然後等佢完成（首次會載 Whisper model，耐）。

- [ ] **Step 3: 確認產出**

檢查 `backend/data/library/manifest.json` 存在、有 `shows[].clips[].sentences`，且 `backend/data/library/audio/` 有對應音檔。
（`backend/data/` 已喺 `.gitignore`，唔會入 git。）

- [ ] **Step 4: 記錄**

唔使 commit code。可喺 README 或一個 `docs/ops-replenish.md` 記低排程指令同改時間方法（可選）。

---

## Task 7: 真網絡端到端 smoke（手動、opt-in）

**Files:** 無

- [ ] **Step 1: 清空再跑一次**

確保 `backend/cookies.txt` 已備（Bilibili 需要）。喺 `backend/`：
Run: `.\.venv\Scripts\python.exe -m app.replenish`
Expected: 印 `replenish done; shows=N clips=M`，`M > 0`。

- [ ] **Step 2: 抽查一條 clip 嘅句子合理**

用 Python 讀 `data/library/manifest.json`，確認某條 clip 嘅 `sentences` 係英文、有 `start < end` 時間碼、`audio_file` 喺 `data/library/audio/` 搵到。

- [ ] **Step 3: 重跑確認唔會超額**

再跑一次 `.\.venv\Scripts\python.exe -m app.replenish`；因每套劇已達 `TARGET_UNPLAYED_PER_SHOW`，應該幾乎唔再下載（clips 數目大致不變）。

---

## Self-Review（已對 spec 核對）

- **Spec §4.1 replenisher**：Task 1–6 覆蓋（config、sourcing、library、replenish、scheduler）。
- **Spec §5 補片觸發**：`clips_needed` 讀 `progress.done_clips` 計未練數；每日 schtasks 保持緩衝（Task 4 + 6）。
- **Spec §6 manifest/progress 形狀**：library 產生（Task 2）；`audio_url`→`audio_file` 修正已標明，Plan 2 解析。
- **Spec §7 原子寫入 + 個別失敗 skip**：`_atomic_write_json` + `os.replace`（Task 2）；source None / 空 sentences / 重複 clip_id 皆 skip（Task 4）。
- **Spec §9 測試**：緩衝計算、library、sourcing、replenish 全部單元測試；外部 IO 注入假件，不入預設套件。
- **唔屬 Plan 1**：Apps Script / PWA / JS compare port（Plan 2）；FastAPI / SQLite 退役（Plan 2）。Plan 1 純加法，現有測試保持綠。
- **Placeholder scan**：無 TBD；所有步驟含完整 code / 指令。
- **型別一致**：clip dict（`clip_id`/`source`/`title`/`audio_path`）由 sourcing 產生，replenish 與 library.add_clip 一致使用；`clips_needed(manifest, progress, target, show_ids)`、`add_clip(manifest, show_id, show_name, clip, audio_file, sentences)`、`replenish_once(...)` 簽名前後一致。
