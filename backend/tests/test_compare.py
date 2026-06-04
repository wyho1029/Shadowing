from app.compare import compare_sentence


def test_perfect_match_all_ok():
    result = compare_sentence("I'm a horse.", "im a horse")
    assert [t["status"] for t in result["tokens"]] == ["ok", "ok", "ok"]
    assert result["score"] == 1.0


def test_tokens_carry_reference_words():
    result = compare_sentence("I'm a horse.", "im a horse")
    assert [t["ref"] for t in result["tokens"]] == ["im", "a", "horse"]


def test_missing_word_marked():
    # 原句 4 字，使用者漏咗 "a"
    result = compare_sentence("I am a horse", "I am horse")
    statuses = {t["ref"]: t["status"] for t in result["tokens"]}
    assert statuses["a"] == "missing"
    assert result["score"] == 0.75  # 3/4 啱


def test_wrong_word_marked():
    result = compare_sentence("I am a horse", "I am a house")
    wrong = [t for t in result["tokens"] if t["status"] == "wrong"]
    extra = [t for t in result["tokens"] if t["status"] == "extra"]
    assert wrong and wrong[0]["ref"] == "horse"
    assert extra and extra[0]["ref"] == "house"


def test_empty_spoken_all_missing():
    result = compare_sentence("hello world", "")
    assert [t["status"] for t in result["tokens"]] == ["missing", "missing"]
    assert result["score"] == 0.0
