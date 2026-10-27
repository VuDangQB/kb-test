"""Jev scorecard: one TypeSafe Jev call per article, scoring every decision for every ticker.

The graph uses some answers as decisions (main event, relevance when the role is unclear,
impact when the criteria need judgment, Thấp vs Trung bình when the article has no numbers)
and keeps the rest as shadow scores to compare with the rule engine (`jev_disagrees` flag).

Scores per ticker, keyed by question:
  choice  → {"answer", "p", "confidence", "probabilities"}
  noul    → {"answer": bool, "p"}                 (p = probability of yes)
  score   → {"score", "confidence", "probabilities"}
plus scores[ticker]["events"][event_id] = {"event_type", "description", "extract_is_new", "role", "impact"}
— one row per extracted event linked to the ticker. `role` draws the event boundaries (ROLE_OPTIONS):
the focus event, details of it, opposite factors set against it, other news, background.
"""

import json
import time
from functools import lru_cache

from . import config, llm, tracing
from .rules import events_for
from .schemas import (ROLE_BACKGROUND, ROLE_DETAIL, ROLE_FOCUS, ROLE_OFFSET, ROLE_OTHER, Article, ArticleFacts,
                      EventFact, Impact, Priority, Relevance)

SEP = "__"  # question name = f"{ticker}{SEP}{key}" or f"{ticker}{SEP}ev{SEP}{event_id}{SEP}{key}"

RELEVANCE_OPTIONS = {
    Relevance.TT.value: "Bài nói về chính công ty, công ty con chưa niêm yết, lãnh đạo/cổ đông chủ chốt, "
                        "hoặc là một bên giao dịch, hoặc nêu số liệu riêng của mã",
    Relevance.GT.value: "Bài về công ty con/liên kết có mã niêm yết riêng, biến số ngành của mã, "
                        "bên liên quan chưa xác nhận sở hữu, hoặc chỉ nhắc tên minh họa",
    Relevance.KLQ.value: "Mã chỉ có tên trong danh sách, hoặc tin vĩ mô tổng quát không phân tích riêng mã",
}
PRIORITY_OPTIONS = {
    Priority.CAO.value: "Thông tin mới có số liệu cho thấy độ lớn vượt ngưỡng vật chất so với quy mô doanh nghiệp, "
                        "hoặc làm thay đổi cấu trúc vốn, quyền kiểm soát, lĩnh vực kinh doanh, trạng thái chỉ số toàn cầu",
    Priority.TB.value: "Có ý nghĩa thực chất nhưng độ lớn ở mức trung gian, hoặc loại sự kiện quan trọng nhưng bài "
                       "thiếu số để lượng hóa, hoặc chỉ là cập nhật của sự kiện đã công bố",
    Priority.THAP.value: "Không tạo thay đổi lượng hóa được với doanh thu, lợi nhuận, cấu trúc vốn hay rủi ro; "
                         "hoặc mã chỉ mang tính minh họa",
}
IMPACT_OPTIONS = {
    Impact.TICH_CUC.value: "Thông tin MỚI có yếu tố thuận lợi rõ cho mã (tăng trưởng KQKD, hợp đồng, cổ tức, "
                           "mở rộng có hiệu quả, dòng vốn vào) và không có yếu tố bất lợi tương đương",
    Impact.TIEU_CUC.value: "Thông tin MỚI có yếu tố bất lợi rõ cho mã (giảm/lỗ, pha loãng thuần, nợ quá hạn, "
                           "phạt, dòng vốn rút) và không có yếu tố thuận lợi tương đương",
    Impact.TRUNG_LAP.value: "Hai chiều lợi/hại tương đương mà bài không lượng hóa tác động ròng; thiếu số liệu "
                            "xác định hướng; sự kiện kỹ thuật/hành chính; chuyển giao nội bộ tập đoàn",
}
ROLE_OPTIONS = {
    ROLE_FOCUS: "Chính là tin bài muốn đưa về mã này",
    ROLE_DETAIL: "Một phần của cùng sự kiện trọng tâm: chi tiết, số liệu, diễn biến, điều kiện của nó",
    ROLE_OFFSET: "Thông tin khác được bài đặt cạnh tin chính để so sánh hoặc bù trừ, tác động theo hướng ngược lại",
    ROLE_OTHER: "Một tin mới khác về mã, độc lập với tin chính",
    ROLE_BACKGROUND: "Thông tin đã công bố, lịch sử, số liệu nhắc lại hoặc nhận định chung làm nền",
}
IMPACT_SCALE = ["Rất tiêu cực", "Tiêu cực", "Trung lập", "Tích cực", "Rất tích cực"]  # score 0..4 → −2..+2


@lru_cache
def client():
    from typesafe_sdk import TypeSafeClient  # reads TYPESAFE_API_KEY
    return TypeSafeClient(model=config.JEV_MODEL, timeout=config.JEV_TIMEOUT)


def fresh_events(mention, facts: ArticleFacts) -> list[EventFact]:
    """Events the rule engine may pick as the main one (same filter as rules.evaluate_ticker)."""
    candidates = events_for(mention, facts)
    return [e for e in candidates if e.is_new_info or e.is_update_of_announced_event] or candidates


def build_questions(facts: ArticleFacts) -> dict:
    from typesafe_sdk import Choice, Noul, Score
    qs = {}
    for m in facts.ticker_mentions:
        t = m.ticker
        q = lambda key, question: qs.__setitem__(f"{t}{SEP}{key}", question)  # noqa: E731
        q("relevance", Choice(instructions=f"Mức độ liên quan của bài với mã {t}?", criteria=RELEVANCE_OPTIONS))
        events = events_for(m, facts)
        if len(events) >= 2:
            q("main_event", Choice(
                instructions=f"Sự kiện nào là TRỌNG TÂM của bài đối với mã {t}: điều bài chủ yếu muốn đưa tin, "
                             f"không phải bối cảnh hay yếu tố được nêu để so sánh/bù trừ?",
                criteria={e.event_id: f"[{e.event_type}] {e.description}" for e in events}))
        for e in events:  # event boundaries: what each extracted event is to the article's story about t
            about = f"thông tin \"[{e.event_type}] {e.description}\""
            q(f"ev{SEP}{e.event_id}{SEP}role",
              Choice(instructions=f"Trong bài, {about} đóng vai trò gì đối với mã {t}?", criteria=ROLE_OPTIONS))
            q(f"ev{SEP}{e.event_id}{SEP}impact",
              Choice(instructions=f"Riêng {about}: ảnh hưởng đến mã {t}?", criteria=IMPACT_OPTIONS))
        q("is_new", Noul(instructions=f"Bài có thông tin MỚI về mã {t} (không chỉ nhắc lại thông tin đã công bố)?"))
        q("is_update", Noul(instructions=f"Thông tin chính về {t} chỉ là cập nhật tiến độ/thủ tục của sự kiện đã "
                                         f"công bố trước đó (gia hạn, chốt quyền, ngày GDKHQ, kết quả giao dịch đã đăng ký)?"))
        q("has_numbers", Noul(instructions=f"Bài có số liệu định lượng riêng của {t} đủ để so với quy mô doanh nghiệp "
                                           f"(giá trị, tỷ lệ, tăng trưởng)?"))
        q("offsetting", Noul(instructions=f"Bài nêu cả yếu tố thuận lợi và bất lợi cho {t} ở quy mô tương đương?"))
        q("priority", Choice(instructions=f"Mức độ quan trọng của bài đối với mã {t}?", criteria=PRIORITY_OPTIONS))
        q("impact", Choice(instructions=f"Ảnh hưởng của thông tin mới trong bài đến mã {t}?", criteria=IMPACT_OPTIONS))
        q("impact_score", Score(instructions=f"Mức tác động của thông tin mới trong bài đến mã {t}?",
                                criteria=IMPACT_SCALE))
    return qs


def _parse(answer) -> dict:
    match answer.type:
        case "choice":
            probs = {k: float(v) for k, v in answer.probabilities.items()}
            return {"answer": answer.choice, "p": round(probs.get(answer.choice, 0.0), 3),
                    "confidence": round(float(answer.confidence), 3), "probabilities": probs}
        case "noul":
            return {"answer": answer.noul >= 0.5, "p": round(float(answer.noul), 3)}
        case "score":
            return {"score": round(float(answer.score) - 2, 2),  # −2..+2
                    "confidence": round(float(answer.confidence), 3),
                    "probabilities": {IMPACT_SCALE[int(k)] if str(k).isdigit() else k: float(v)
                                      for k, v in answer.probabilities.items()}}
    return {}


def score_article(article: Article, facts: ArticleFacts) -> dict[str, dict[str, dict]]:
    """One Jev call for all tickers in `facts`. Returns {ticker: {question_key: score}}."""
    questions = build_questions(facts)
    if not questions:
        return {}
    state = f"Tiêu đề: {article.title}\nNgày đăng: {article.published_at}\n\n<bai_bao>\n{article.content}\n</bai_bao>"
    started = time.perf_counter()
    payload = json.dumps({"questions": {k: v.model_dump() for k, v in questions.items()}}, ensure_ascii=False)
    with tracing.llm_span("jev.scorecard", "typesafe", config.JEV_MODEL, payload) as set_result:
        resp = client().system_one(state=state, questions=questions)
        out: dict[str, dict[str, dict]] = {}
        by_id = {e.event_id: e for e in facts.events}
        for name, answer in resp.answers.items():
            parts = name.split(SEP)
            score = _parse(getattr(answer, "root", answer))
            if len(parts) == 4 and parts[1] == "ev":  # ticker, "ev", event_id, key
                ev = by_id.get(parts[2])
                row = out.setdefault(parts[0], {}).setdefault("events", {}).setdefault(parts[2], {
                    "event_type": ev.event_type if ev else "", "description": ev.description if ev else "",
                    "extract_is_new": ev.is_new_info if ev else None})
                row[parts[3]] = score
            else:
                out.setdefault(parts[0], {})[parts[1]] = score
        set_result(json.dumps(out, ensure_ascii=False), resp.usage.input_tokens or 0,
                   resp.usage.output_tokens or 0, resp.model)
    llm.record("scorecard", time.perf_counter() - started, "jev",
               input_tokens=resp.usage.input_tokens or 0, output_tokens=resp.usage.output_tokens or 0)
    return out
