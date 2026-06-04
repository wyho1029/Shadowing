from app import youtube


def test_pick_first_in_duration_range():
    # flat 搜尋結果只有 id/title/duration（冇 subtitles 欄位）；揀第一個長度合理嘅
    entries = [
        {"id": "first", "duration": 120, "title": "a"},
        {"id": "second", "duration": 200, "title": "b"},
    ]
    assert youtube.pick_candidate(entries)["id"] == "first"


def test_pick_rejects_too_short_or_too_long():
    entries = [
        {"id": "too_short", "duration": 20, "title": "a"},
        {"id": "too_long", "duration": 1200, "title": "b"},
        {"id": "ok", "duration": 180, "title": "c"},
    ]
    assert youtube.pick_candidate(entries)["id"] == "ok"


def test_pick_handles_missing_duration():
    # flat entry 偶爾冇 duration（live / 私人片）→ 當唔合格 skip
    entries = [
        {"id": "no_dur", "title": "a"},
        {"id": "ok", "duration": 90, "title": "b"},
    ]
    assert youtube.pick_candidate(entries)["id"] == "ok"


def test_pick_returns_none_when_nothing_suitable():
    entries = [
        {"id": "x", "duration": 5, "title": "a"},
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
