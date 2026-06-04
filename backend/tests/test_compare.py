from app.compare import compare_sentence, normalize


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


def test_hyphenated_word_treated_as_two_tokens():
    # 連字號當作分隔：well-known → ["well", "known"]（pin 實 normalize contract）
    assert normalize("well-known fact") == ["well", "known", "fact"]


def test_empty_reference_zero_score_spoken_all_extra():
    # 實際 pipeline segmenter 會過濾空句；呢度 pin 防禦行為：
    # 空原句 → 講出嚟嘅字全部當 extra，score 0.0（唔會 crash）
    result = compare_sentence("", "anything said")
    assert [t["status"] for t in result["tokens"]] == ["extra", "extra"]
    assert result["score"] == 0.0


def test_both_empty_returns_empty_tokens_zero_score():
    result = compare_sentence("", "")
    assert result["tokens"] == []
    assert result["score"] == 0.0
