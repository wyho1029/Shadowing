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
            if not clip:
                continue
            if clip["clip_id"] in seen:
                Path(clip["audio_path"]).unlink(missing_ok=True)  # 重複片：清走已下載音檔
                continue
            # 下載被 cap / 失敗時 yt-dlp ignoreerrors 會吞錯，留低一個唔存在嘅路徑 → 跳
            if not Path(clip["audio_path"]).exists():
                continue
            try:
                raw = transcribe_fn(clip["audio_path"])
                sentences = segment_fn(raw)
            except Exception:
                # 個別片轉錄炸唔好殺成個 run（spec §7）：清走、跳去下一條
                Path(clip["audio_path"]).unlink(missing_ok=True)
                continue
            if not sentences:
                Path(clip["audio_path"]).unlink(missing_ok=True)  # 切唔到句：清走已下載音檔
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
