import io

from fastapi.testclient import TestClient

from app import main


def get_client(tmp_path, monkeypatch):
    from app.db import Database
    monkeypatch.setattr(main, "db", Database(tmp_path / "t.sqlite3"))
    return TestClient(main.app)


def test_list_shows(tmp_path, monkeypatch):
    client = get_client(tmp_path, monkeypatch)
    r = client.get("/api/shows")
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()}
    assert "bojack" in ids


def test_create_material_success(tmp_path, monkeypatch):
    client = get_client(tmp_path, monkeypatch)

    monkeypatch.setattr(main.youtube, "find_clip", lambda q: {
        "youtube_id": "abc", "title": "clip", "audio_path": "data/audio/abc.m4a"})
    monkeypatch.setattr(main.transcribe, "transcribe_segments", lambda p: [
        {"text": "I'm a horse.", "start": 0.0, "end": 1.5}])

    r = client.post("/api/materials", params={"show_id": "bojack"})
    assert r.status_code == 200
    body = r.json()
    assert body["material_id"] >= 1
    assert body["sentences"][0]["text"] == "I'm a horse."
    assert "id" in body["sentences"][0]


def test_create_material_no_clip_found(tmp_path, monkeypatch):
    client = get_client(tmp_path, monkeypatch)
    monkeypatch.setattr(main.youtube, "find_clip", lambda q: None)
    r = client.post("/api/materials", params={"show_id": "bojack"})
    assert r.status_code == 404


def test_submit_attempt_returns_tokens(tmp_path, monkeypatch):
    client = get_client(tmp_path, monkeypatch)
    monkeypatch.setattr(main.youtube, "find_clip", lambda q: {
        "youtube_id": "abc", "title": "clip", "audio_path": "p.m4a"})
    monkeypatch.setattr(main.transcribe, "transcribe_segments", lambda p: [
        {"text": "I am a horse.", "start": 0.0, "end": 1.5}])
    mat = client.post("/api/materials", params={"show_id": "bojack"}).json()
    sid = mat["sentences"][0]["id"]

    monkeypatch.setattr(main.transcribe, "transcribe_text", lambda p: "I am a house")
    files = {"audio": ("rec.webm", io.BytesIO(b"fake"), "audio/webm")}
    r = client.post("/api/attempts", data={"sentence_id": str(sid)}, files=files)
    assert r.status_code == 200
    body = r.json()
    assert "tokens" in body and "score" in body
    assert any(t["status"] == "wrong" for t in body["tokens"])
