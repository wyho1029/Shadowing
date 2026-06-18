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
