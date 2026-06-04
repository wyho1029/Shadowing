from app.segmenter import segment_transcript


def test_splits_on_sentence_punctuation():
    raw = [
        {"text": "I'm a horse.", "start": 0.0, "end": 1.5},
        {"text": "You are a cat.", "start": 1.5, "end": 3.0},
    ]
    out = segment_transcript(raw)
    assert [s["text"] for s in out] == ["I'm a horse.", "You are a cat."]
    assert out[0]["start"] == 0.0 and out[0]["end"] == 1.5
    assert out[1]["start"] == 1.5 and out[1]["end"] == 3.0


def test_merges_fragments_until_punctuation():
    raw = [
        {"text": "I really", "start": 0.0, "end": 0.8},
        {"text": "love this show.", "start": 0.8, "end": 2.0},
    ]
    out = segment_transcript(raw)
    assert len(out) == 1
    assert out[0]["text"] == "I really love this show."
    assert out[0]["start"] == 0.0 and out[0]["end"] == 2.0


def test_trailing_text_without_punctuation_is_kept():
    raw = [{"text": "no punctuation here", "start": 0.0, "end": 1.0}]
    out = segment_transcript(raw)
    assert len(out) == 1
    assert out[0]["text"] == "no punctuation here"
    assert out[0]["end"] == 1.0


def test_empty_segments_skipped():
    raw = [
        {"text": "   ", "start": 0.0, "end": 0.5},
        {"text": "Hello.", "start": 0.5, "end": 1.0},
    ]
    out = segment_transcript(raw)
    assert len(out) == 1
    assert out[0]["text"] == "Hello."
    assert out[0]["start"] == 0.5
