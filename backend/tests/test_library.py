from app import library


def test_load_missing_returns_empty(tmp_path):
    m = library.load_manifest(tmp_path / "nope.json")
    assert m["shows"] == [] and m["version"] == 1
    p = library.load_progress(tmp_path / "nope.json")
    assert p["done_clips"] == []


def _clip(cid):
    return {"clip_id": cid, "source": "youtube", "title": cid}


def test_add_clip_creates_show_and_indexes_sentences(tmp_path):
    m = library.load_manifest(tmp_path / "m.json")
    library.add_clip(m, "bojack", "BoJack Horseman", _clip("abc"), "abc.m4a",
                     [{"text": "Hi.", "start": 0.0, "end": 1.0},
                      {"text": "Bye.", "start": 1.0, "end": 2.0}])
    show = m["shows"][0]
    assert show["id"] == "bojack" and show["name"] == "BoJack Horseman"
    clip = show["clips"][0]
    assert clip["clip_id"] == "abc"
    assert clip["source"] == "youtube"
    assert clip["audio_file"] == "abc.m4a"
    assert [s["idx"] for s in clip["sentences"]] == [0, 1]
    assert clip["sentences"][1]["text"] == "Bye."


def test_add_clip_reuses_existing_show_entry(tmp_path):
    m = library.load_manifest(tmp_path / "m.json")
    library.add_clip(m, "bojack", "BoJack", _clip("a"), "a.m4a",
                     [{"text": "x.", "start": 0, "end": 1}])
    library.add_clip(m, "bojack", "BoJack", _clip("b"), "b.m4a",
                     [{"text": "y.", "start": 0, "end": 1}])
    assert len(m["shows"]) == 1
    assert len(m["shows"][0]["clips"]) == 2


def test_existing_clip_ids(tmp_path):
    m = library.load_manifest(tmp_path / "m.json")
    library.add_clip(m, "bojack", "BoJack", _clip("a"), "a.m4a",
                     [{"text": "x.", "start": 0, "end": 1}])
    assert library.existing_clip_ids(m) == {"a"}


def test_unplayed_excludes_done_clips(tmp_path):
    m = library.load_manifest(tmp_path / "m.json")
    for cid in ("a", "b"):
        library.add_clip(m, "bojack", "BoJack", _clip(cid), f"{cid}.m4a",
                         [{"text": "x.", "start": 0, "end": 1}])
    prog = {"version": 1, "done_clips": ["a"], "attempts": []}
    assert library.unplayed_count(m, prog, "bojack") == 1


def test_clips_needed_per_show(tmp_path):
    m = library.load_manifest(tmp_path / "m.json")
    library.add_clip(m, "bojack", "BoJack", _clip("a"), "a.m4a",
                     [{"text": "x.", "start": 0, "end": 1}])
    prog = library.load_progress(tmp_path / "p.json")
    needs = library.clips_needed(m, prog, target=3, show_ids=["bojack", "simpsons"])
    assert needs == {"bojack": 2, "simpsons": 3}


def test_save_manifest_is_atomic_and_reloads(tmp_path):
    path = tmp_path / "m.json"
    m = library.load_manifest(path)
    library.add_clip(m, "bojack", "BoJack", _clip("a"), "a.m4a",
                     [{"text": "x.", "start": 0, "end": 1}])
    library.save_manifest(m, path)
    assert path.exists()
    assert not (tmp_path / "m.json.tmp").exists()   # temp 已 rename 走
    reloaded = library.load_manifest(path)
    assert reloaded["shows"][0]["clips"][0]["clip_id"] == "a"
    assert reloaded["updated_at"] is not None
