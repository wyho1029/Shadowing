# 每套劇：YouTube 搜尋字串（fallback）+ 可選 Bilibili 合集（curated shadowing 系列，優先）。
# Bilibili 合集要有 cookies 先抽到（見 config）；搵到啱嘅可以陸續加落其他劇。
SHOWS = [
    {"id": "bojack", "name": "BoJack Horseman",
     "query": "BoJack Horseman best scenes",
     "bilibili": "https://www.bilibili.com/video/BV1sH4y1c7dR/"},
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


def get_bilibili_collection(show_id: str) -> str | None:
    """該套劇綁定嘅 Bilibili 合集 URL；冇就回 None。"""
    return _BY_ID[show_id].get("bilibili")
