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
