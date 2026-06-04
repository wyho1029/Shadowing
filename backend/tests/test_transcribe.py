from app import transcribe


class _FakeSeg:
    def __init__(self, text, start, end):
        self.text, self.start, self.end = text, start, end


class _FakeModel:
    def transcribe(self, path, **kwargs):
        segs = [_FakeSeg(" Hello there.", 0.0, 1.2),
                _FakeSeg(" General Kenobi.", 1.2, 2.5)]
        return segs, {"language": "en"}


def test_transcribe_segments_shape(monkeypatch):
    monkeypatch.setattr(transcribe, "_get_model", lambda: _FakeModel())
    out = transcribe.transcribe_segments("dummy.m4a")
    assert out == [
        {"text": "Hello there.", "start": 0.0, "end": 1.2},
        {"text": "General Kenobi.", "start": 1.2, "end": 2.5},
    ]


def test_transcribe_text_joins(monkeypatch):
    monkeypatch.setattr(transcribe, "_get_model", lambda: _FakeModel())
    text = transcribe.transcribe_text("dummy.m4a")
    assert text == "Hello there. General Kenobi."
