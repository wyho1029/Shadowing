from app import bilibili


class _FakeYDL:
    """假 yt_dlp.YoutubeDL：flat 抽取回固定集數，下載回一個 entry。"""
    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        if self.opts.get("extract_flat"):
            return {"entries": [{"id": None}, {"id": None}, {"id": None}]}  # 3 集
        return {"entries": [{"id": "BV1sH4y1c7dR_p2", "title": "ep2"}]}

    def prepare_filename(self, entry):
        return f"data/audio/{entry['id']}.m4a"


def test_part_count(monkeypatch):
    monkeypatch.setattr(bilibili.yt_dlp, "YoutubeDL", _FakeYDL)
    assert bilibili.part_count("https://b.example/BV") == 3


def test_find_clip_returns_dict(monkeypatch):
    monkeypatch.setattr(bilibili.yt_dlp, "YoutubeDL", _FakeYDL)
    monkeypatch.setattr(bilibili.random, "randint", lambda a, b: 2)
    clip = bilibili.find_clip("https://b.example/BV")
    assert clip["youtube_id"] == "BV1sH4y1c7dR_p2"
    assert clip["title"] == "ep2"
    assert clip["audio_path"].endswith("BV1sH4y1c7dR_p2.m4a")


def test_find_clip_none_when_no_parts(monkeypatch):
    class _EmptyYDL(_FakeYDL):
        def extract_info(self, url, download=False):
            return {"entries": []}

    monkeypatch.setattr(bilibili.yt_dlp, "YoutubeDL", _EmptyYDL)
    assert bilibili.find_clip("https://b.example/BV") is None
