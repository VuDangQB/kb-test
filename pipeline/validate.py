"""Node `validate`: consistency checks on a finished TickerResult."""

import re

from .catalog import RULES
from .schemas import Priority, Relevance, TickerResult

RULE_ID = re.compile(r"\b(?:[RPIG]-[A-Z0-9]+(?:-[A-Za-z0-9]+)*|A\d{2})\b")
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
ADVICE = re.compile(
    r"nên\s+(mua|bán|nắm giữ|chốt lời|cắt lỗ|gom)|khuyến nghị\s+(mua|bán|nắm giữ)|"
    r"(giá|cổ phiếu)\s+(sẽ|chắc chắn)\s+(tăng|giảm)|cơ hội mua vào",
    re.IGNORECASE)


def _digits(text: str) -> set[str]:
    return {re.sub(r"[.,]", "", tok) for tok in NUMBER.findall(RULE_ID.sub(" ", text))}


def check(r: TickerResult, content: str, extra_sources: list[str] = ()) -> list[str]:
    errors: list[str] = []
    if r.priority == Priority.CAO and r.relevance != Relevance.TT:
        errors.append("Priority Cao nhưng Relevance không phải Trực tiếp")

    allowed = _digits(content)
    for src in [*extra_sources, *r.computed.values(), *(e.quote for e in r.evidence)]:
        allowed |= _digits(src)

    fields = [
        ("relevance_reason", r.relevance_reason, r.relevance_rule_ids, r.relevance.value),
        ("priority_reason", r.priority_reason, r.priority_rule_ids, r.priority.value if r.priority else ""),
        ("impact_reason", r.impact_reason, r.impact_rule_ids, r.impact.value if r.impact else ""),
    ]
    for name, text, ids, label in fields:
        if not text.strip():
            errors.append(f"{name}: trống")
            continue
        if label and label.casefold() not in text.casefold():
            errors.append(f"{name}: không nêu nhãn '{label}'")
        cited = set(RULE_ID.findall(text))
        if ids and not cited & set(ids):
            errors.append(f"{name}: phải trích ít nhất một mã trong {ids}")
        if not ids and name == "impact_reason" and not any(c.startswith("I-") for c in cited):
            errors.append(f"{name}: phải trích một yếu tố I-YT-* hoặc I-TL-*")
        unknown = [c for c in cited if c not in RULES]
        if unknown:
            errors.append(f"{name}: mã quy tắc không tồn tại {unknown}")
        for d in _digits(text):
            if len(d) > 2 and d not in allowed and not re.fullmatch(r"20\d\d", d):
                errors.append(f"{name}: con số '{d}' không có trong bài hoặc số liệu đã tính")
        if ADVICE.search(text):
            errors.append(f"{name}: có câu mang tính khuyến nghị/dự đoán giá")
    return errors
