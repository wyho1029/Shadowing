import re

_END_PUNCT = re.compile(r"[.!?]['\")\]]?\s*$")


def segment_transcript(raw_segments: list[dict]) -> list[dict]:
    """合併 Whisper segment 成完整句子。

    規則：累積 segment 直到 text 以 . ! ? 結尾就斬一句。
    每句 start = 第一個 fragment 嘅 start，end = 最後一個嘅 end。
    """
    sentences: list[dict] = []
    buf_text: list[str] = []
    buf_start: float | None = None
    buf_end: float = 0.0

    for seg in raw_segments:
        text = seg["text"].strip()
        if not text:
            continue
        if buf_start is None:
            buf_start = seg["start"]
        buf_text.append(text)
        buf_end = seg["end"]

        if _END_PUNCT.search(text):
            sentences.append(
                {"text": " ".join(buf_text), "start": buf_start, "end": buf_end}
            )
            buf_text, buf_start = [], None

    # 後備：最後一段冇標點都要收返
    if buf_text:
        sentences.append(
            {"text": " ".join(buf_text), "start": buf_start, "end": buf_end}
        )
    return sentences
