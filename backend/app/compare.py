import re
from difflib import SequenceMatcher


def normalize(text: str) -> list[str]:
    """轉細階、淨低字母數字同空格、split 成 token list。"""
    text = text.lower()
    text = re.sub(r"[^\w\s']", " ", text)   # 去標點（保留 apostrophe 先）
    text = text.replace("'", "")            # 縮寫去 apostrophe：im / dont
    return text.split()


def compare_sentence(reference: str, spoken: str) -> dict:
    ref_tokens = normalize(reference)
    hyp_tokens = normalize(spoken)
    matcher = SequenceMatcher(a=ref_tokens, b=hyp_tokens, autojunk=False)

    tokens: list[dict] = []
    correct = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i1, i2):
                tokens.append({"ref": ref_tokens[k], "status": "ok"})
                correct += 1
        elif tag == "replace":
            for k in range(i1, i2):
                tokens.append({"ref": ref_tokens[k], "status": "wrong"})
            for k in range(j1, j2):
                tokens.append({"ref": hyp_tokens[k], "status": "extra"})
        elif tag == "delete":           # 原句有、使用者漏咗
            for k in range(i1, i2):
                tokens.append({"ref": ref_tokens[k], "status": "missing"})
        elif tag == "insert":           # 使用者多講
            for k in range(j1, j2):
                tokens.append({"ref": hyp_tokens[k], "status": "extra"})

    score = correct / len(ref_tokens) if ref_tokens else 0.0
    return {"tokens": tokens, "score": score}
