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
