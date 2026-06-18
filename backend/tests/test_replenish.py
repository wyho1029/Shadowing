from app import library, replenish


def _fake_segment_ok(raw):
    return [{"text": "Hello world.", "start": 0.0, "end": 2.0}]


def _make_source(tmp_path):
    """source_fn：每次叫整一個新假音檔，clip_id 遞增（模擬真下載落 temp）。"""
    counter = {"n": 0}
    dl = tmp_path / "dl"
    dl.mkdir(exist_ok=True)

    def source_fn(show_id):
        counter["n"] += 1
        cid = f"{show_id}_{counter['n']}"
        f = dl / f"{cid}.m4a"
        f.write_bytes(b"fake-audio")
        return {"clip_id": cid, "source": "youtube",
                "title": cid, "audio_path": str(f)}
    return source_fn


def test_replenish_fills_to_target_and_moves_audio(tmp_path):
    audio_dir = tmp_path / "library_audio"
    audio_dir.mkdir()
    manifest = library.load_manifest(tmp_path / "m.json")
    progress = library.load_progress(tmp_path / "p.json")

    replenish.replenish_once(
        manifest=manifest, progress=progress, show_ids=["bojack"],
        show_names={"bojack": "BoJack Horseman"}, target=2,
        source_fn=_make_source(tmp_path),
        transcribe_fn=lambda p: ["raw"], segment_fn=_fake_segment_ok,
        audio_dest_dir=audio_dir,
    )
    clips = manifest["shows"][0]["clips"]
    assert len(clips) == 2
    assert (audio_dir / clips[0]["audio_file"]).exists()   # 音檔已搬入庫


def test_replenish_skips_when_source_returns_none(tmp_path):
    audio_dir = tmp_path / "la"; audio_dir.mkdir()
    manifest = library.load_manifest(tmp_path / "m.json")
    progress = library.load_progress(tmp_path / "p.json")
    replenish.replenish_once(
        manifest=manifest, progress=progress, show_ids=["bojack"],
        show_names={"bojack": "BoJack"}, target=2,
        source_fn=lambda sid: None, transcribe_fn=lambda p: ["raw"],
        segment_fn=_fake_segment_ok, audio_dest_dir=audio_dir,
    )
    assert manifest["shows"] == []


def test_replenish_skips_empty_sentences(tmp_path):
    audio_dir = tmp_path / "la"; audio_dir.mkdir()
    manifest = library.load_manifest(tmp_path / "m.json")
    progress = library.load_progress(tmp_path / "p.json")
    replenish.replenish_once(
        manifest=manifest, progress=progress, show_ids=["bojack"],
        show_names={"bojack": "BoJack"}, target=2,
        source_fn=_make_source(tmp_path), transcribe_fn=lambda p: ["raw"],
        segment_fn=lambda raw: [], audio_dest_dir=audio_dir,
    )
    assert manifest["shows"] == []


def test_replenish_respects_existing_unplayed(tmp_path):
    audio_dir = tmp_path / "la"; audio_dir.mkdir()
    manifest = library.load_manifest(tmp_path / "m.json")
    library.add_clip(manifest, "bojack", "BoJack",
                     {"clip_id": "old", "source": "youtube", "title": "old"},
                     "old.m4a", [{"text": "x.", "start": 0, "end": 1}])
    progress = library.load_progress(tmp_path / "p.json")
    replenish.replenish_once(
        manifest=manifest, progress=progress, show_ids=["bojack"],
        show_names={"bojack": "BoJack"}, target=2,
        source_fn=_make_source(tmp_path), transcribe_fn=lambda p: ["raw"],
        segment_fn=_fake_segment_ok, audio_dest_dir=audio_dir,
    )
    # 本身 1 條未練，target 2 → 只補 1 條
    assert len(manifest["shows"][0]["clips"]) == 2


def test_replenish_dedupes_repeated_clip_id(tmp_path):
    audio_dir = tmp_path / "la"; audio_dir.mkdir()
    dl = tmp_path / "dl"; dl.mkdir()

    def same_clip(show_id):
        f = dl / "dup.m4a"
        f.write_bytes(b"x")
        return {"clip_id": "dup", "source": "youtube",
                "title": "dup", "audio_path": str(f)}

    manifest = library.load_manifest(tmp_path / "m.json")
    progress = library.load_progress(tmp_path / "p.json")
    replenish.replenish_once(
        manifest=manifest, progress=progress, show_ids=["bojack"],
        show_names={"bojack": "BoJack"}, target=3,
        source_fn=same_clip, transcribe_fn=lambda p: ["raw"],
        segment_fn=_fake_segment_ok, audio_dest_dir=audio_dir,
    )
    # 同一 clip_id 只入一次
    assert len(manifest["shows"][0]["clips"]) == 1


def test_main_loads_runs_and_saves(monkeypatch, tmp_path):
    calls = {}
    monkeypatch.setattr(replenish.library, "load_manifest",
                        lambda p: {"version": 1, "updated_at": None, "shows": []})
    monkeypatch.setattr(replenish.library, "load_progress",
                        lambda p: {"version": 1, "done_clips": [], "attempts": []})

    def fake_run(**kw):
        calls["ran"] = True
        return kw["manifest"]
    monkeypatch.setattr(replenish, "replenish_once", fake_run)

    def fake_save(manifest, path):
        calls["saved"] = True
    monkeypatch.setattr(replenish.library, "save_manifest", fake_save)

    replenish.main()
    assert calls.get("ran") and calls.get("saved")
