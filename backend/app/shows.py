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
