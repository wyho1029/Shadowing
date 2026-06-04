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
