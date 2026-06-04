from app.db import Database


def make_db(tmp_path):
    return Database(tmp_path / "test.sqlite3")


def test_add_material_and_get_sentences(tmp_path):
    db = make_db(tmp_path)
    mid = db.add_material(show_id="bojack", title="BoJack clip",
                          youtube_id="abc123", audio_path="data/audio/abc123.m4a")
    db.add_sentences(mid, [
        {"text": "I'm a horse.", "start": 0.0, "end": 1.5},
        {"text": "You are a cat.", "start": 1.5, "end": 3.0},
    ])
    sents = db.get_sentences(mid)
    assert len(sents) == 2
    assert sents[0]["text"] == "I'm a horse."
    assert sents[0]["start"] == 0.0
    assert "id" in sents[0]


def test_record_attempt_and_mark_status(tmp_path):
    db = make_db(tmp_path)
    mid = db.add_material("bojack", "clip", "abc", "p.m4a")
    db.add_sentences(mid, [{"text": "Hi.", "start": 0.0, "end": 1.0}])
    sid = db.get_sentences(mid)[0]["id"]
    db.record_attempt(sentence_id=sid, score=0.75, status="retry")
    attempts = db.get_attempts(sid)
    assert len(attempts) == 1
    assert attempts[0]["score"] == 0.75
    assert attempts[0]["status"] == "retry"
