"""Node `write`: three short justifications (relevance, priority, impact) for fixed labels."""

from . import config, llm
from .catalog import RULES
from .extract import CRITERIA_PATH, article_message
from .schemas import Article, Reasons, TickerResult

WRITE_SYSTEM = """Bạn viết phần CĂN CỨ cho các nhãn đánh giá tin tức chứng khoán đã được hệ thống quy tắc chốt. Người đọc là chuyên viên KB Securities.

Yêu cầu cho mỗi lý giải (relevance_reason, priority_reason, impact_reason):
- 1–3 câu tiếng Việt, ngắn gọn, dễ hiểu.
- Nêu đúng tên nhãn đã chốt (VD "Trực tiếp", "Trung bình", "Trung lập") và KHÔNG đổi nhãn.
- Trích ít nhất một mã quy tắc trong ngoặc, lấy từ danh sách mã quy tắc được cung cấp cho đúng trường đó, VD "(R-TT-3)", "(P-TH-02, P-MOD-1)".
- Dẫn số liệu cụ thể từ bài hoặc từ mục "Số liệu đã tính". Chỉ dùng con số có trong bài, trong mục "Số liệu đã tính", hoặc trong hồ sơ mã; giữ nguyên cách viết số.
- Nếu Priority không phải Cao, nêu điều còn thiếu hoặc điều đã hạ bậc (VD "có ý nghĩa ... nhưng chưa ...", "chỉ cập nhật lịch của đợt phát hành đã công bố").
- Với tin công ty con có mã riêng, nói rõ quan hệ với mã đang xét (VD "MSR, công ty con Masan sở hữu ~87,46%").
- Văn phong khách quan: không khuyến nghị mua/bán/nắm giữ, không dự đoán giá, không dùng tiêu đề giật gân làm căn cứ.
- Nếu impact_rule_ids trống: chọn yếu tố phù hợp trong Mục 4 của tiêu chí (I-YT-1…I-YT-10 hoặc I-TL-a…I-TL-f) và trích mã đó."""


def _rules_block(ids: list[str]) -> str:
    return "\n".join(f"  - {i}: {RULES.get(i, '')}" for i in ids) or "  (trống)"


def labels_message(article: Article, r: TickerResult, event_desc: str, feedback: list[str]) -> str:
    computed = "\n".join(f"  - {k}: {v}" for k, v in r.computed.items()) or "  (không có)"
    evidence = "\n".join(f"  - \"{e.quote}\"" for e in r.evidence) or "  (không có)"
    parts = [
        article_message(article),
        f"\nMã đang xét: {r.ticker}",
        f"Sự kiện chính: [{r.event_type}] {event_desc}",
        f"\nRelevance: {r.relevance.value}\nMã quy tắc relevance:\n{_rules_block(r.relevance_rule_ids)}",
        f"\nPriority: {r.priority.value if r.priority else '-'}\nMã quy tắc priority:\n{_rules_block(r.priority_rule_ids)}",
        f"\nẢnh hưởng: {r.impact.value if r.impact else '-'}\nMã quy tắc impact:\n{_rules_block(r.impact_rule_ids)}",
        f"\nSố liệu đã tính:\n{computed}",
        f"\nCâu trích dẫn chứng:\n{evidence}",
    ]
    if r.flags:
        parts.append(f"\nCờ: {', '.join(r.flags)}")
    if feedback:
        parts.append("\nBản trước chưa đạt, sửa các lỗi sau:\n" + "\n".join(f"  - {x}" for x in feedback))
    return "\n".join(parts)


def write_reasons(article: Article, r: TickerResult, event_desc: str, feedback: list[str] | None = None) -> Reasons:
    system = [WRITE_SYSTEM, "# Tiêu chí đánh giá\n\n" + CRITERIA_PATH.read_text(encoding="utf-8")]
    return llm.parse(system, labels_message(article, r, event_desc, feedback or []), Reasons,
                     effort=config.EFFORT["write"], max_tokens=6000, stage="write")
