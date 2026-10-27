"""LangGraph wiring: extract -> fan-out per ticker -> relevance -> rules -> impact -> write -> validate."""

import logging
import operator
from functools import lru_cache
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from . import config
from .catalog import RULES
from .decision import DecisionModel, make_decision_model
from .extract import CRITERIA_PATH, extract
from .llm import LLMStopError
from .profiles import load_profiles
from .rules import RuleOutcome, evaluate_ticker
from .schemas import Article, ArticleFacts, Impact, Relevance, TickerMention, TickerResult
from .validate import check
from .write import write_reasons

log = logging.getLogger(__name__)
MAX_WRITE_ATTEMPTS = 2


class GraphState(TypedDict, total=False):
    article: Article
    facts: ArticleFacts
    results: Annotated[list[TickerResult], operator.add]
    error: str


class TickerState(TypedDict, total=False):
    article: Article
    facts: ArticleFacts
    mention: TickerMention
    relevance: Relevance | None
    relevance_ids: list[str]
    relevance_conf: float
    outcome: RuleOutcome
    result: TickerResult
    feedback: list[str]
    attempts: int
    results: Annotated[list[TickerResult], operator.add]


@lru_cache
def decision_model() -> DecisionModel:
    return make_decision_model(CRITERIA_PATH.read_text(encoding="utf-8"))


# Option descriptions for DecisionModel questions (from tieu_chi_v2 Mục 2 and Mục 4).
RELEVANCE_OPTIONS = {
    Relevance.TT.value: "Bài nói về chính công ty, công ty con chưa niêm yết, lãnh đạo/cổ đông chủ chốt, "
                        "hoặc là một bên giao dịch, hoặc nêu số liệu riêng của mã",
    Relevance.GT.value: "Bài về công ty con/liên kết có mã niêm yết riêng, biến số ngành của mã, "
                        "bên liên quan chưa xác nhận sở hữu, hoặc chỉ nhắc tên minh họa",
    Relevance.KLQ.value: "Mã chỉ có tên trong danh sách, hoặc tin vĩ mô tổng quát không phân tích riêng mã",
}
IMPACT_OPTIONS = {
    Impact.TICH_CUC.value: "Thông tin MỚI có yếu tố thuận lợi rõ cho mã (tăng trưởng KQKD, hợp đồng, cổ tức, "
                           "mở rộng có hiệu quả, dòng vốn vào) và không có yếu tố bất lợi tương đương",
    Impact.TIEU_CUC.value: "Thông tin MỚI có yếu tố bất lợi rõ cho mã (giảm/lỗ, pha loãng thuần, nợ quá hạn, "
                           "phạt, dòng vốn rút) và không có yếu tố thuận lợi tương đương",
    Impact.TRUNG_LAP.value: "Hai chiều lợi/hại tương đương mà bài không lượng hóa tác động ròng; thiếu số liệu "
                            "xác định hướng; sự kiện kỹ thuật/hành chính; chuyển giao nội bộ tập đoàn",
}


def _facts_state(article: Article, facts: ArticleFacts, ticker: str) -> str:
    return (f"Mã đang xét: {ticker}\nTiêu đề: {article.title}\n"
            f"Dữ kiện đã trích (JSON):\n{facts.model_dump_json(exclude_defaults=True)}\n\n"
            f"<bai_bao>\n{article.content}\n</bai_bao>")


# ---------------------------------------------------------------------------
# article-level nodes
# ---------------------------------------------------------------------------

def node_extract(state: GraphState) -> dict:
    try:
        return {"facts": extract(state["article"])}
    except LLMStopError as exc:
        log.warning("extract stopped: %s", exc)
        return {"error": f"extract: {exc}"}


def fan_out(state: GraphState):
    facts = state.get("facts")
    if not facts or not facts.ticker_mentions:
        return END
    return [Send("ticker", {"article": state["article"], "facts": facts, "mention": m, "attempts": 0, "feedback": []})
            for m in facts.ticker_mentions]


# ---------------------------------------------------------------------------
# per-ticker nodes
# ---------------------------------------------------------------------------

def node_relevance(state: TickerState) -> dict:
    article, facts, m = state["article"], state["facts"], state["mention"]
    profile = load_profiles()[m.ticker]
    pre = evaluate_ticker(m, facts, profile, article.published_at)
    if pre.relevance is not None:
        return {"relevance": pre.relevance, "relevance_ids": pre.relevance_rule_ids, "relevance_conf": 1.0}
    d = decision_model().choice(
        _facts_state(article, facts, m.ticker),
        f"Mức độ liên quan của bài với mã {m.ticker} theo Mục 2 của tiêu chí?", RELEVANCE_OPTIONS)
    return {"relevance": Relevance(d.answer), "relevance_ids": ["G-5"], "relevance_conf": d.confidence}


def node_rules(state: TickerState) -> dict:
    article, m = state["article"], state["mention"]
    outcome = evaluate_ticker(m, state["facts"], load_profiles()[m.ticker], article.published_at,
                              relevance=state["relevance"], relevance_ids=state["relevance_ids"])
    return {"outcome": outcome}


def node_impact(state: TickerState) -> dict:
    o, article = state["outcome"], state["article"]
    result = TickerResult(
        ticker=o.ticker, relevance=o.relevance, priority=o.priority, impact=o.impact,
        priority_confidence=state.get("relevance_conf", 1.0),
        event_type=o.event.event_type if o.event else "",
        relevance_rule_ids=o.relevance_rule_ids, priority_rule_ids=o.priority_rule_ids,
        impact_rule_ids=o.impact_rule_ids, computed=o.computed, evidence=o.evidence, flags=list(o.flags),
    )
    if o.relevance != Relevance.KLQ and o.event is not None and o.impact is None:
        hint = f" Gợi ý quy tắc cần xét: {o.impact_hint} – {RULES.get(o.impact_hint, '')}." if o.impact_hint else ""
        d = decision_model().choice(
            _facts_state(article, state["facts"], o.ticker),
            f"Ảnh hưởng của thông tin mới trong bài đến mã {o.ticker} theo Mục 4 của tiêu chí "
            f"(sự kiện chính: [{o.event.event_type}] {o.event.description})?{hint}", IMPACT_OPTIONS)
        answer = d.answer
        result.impact, result.impact_confidence = Impact(answer), d.confidence
        if answer == Impact.TRUNG_LAP.value and o.impact_hint:
            result.impact_rule_ids = [o.impact_hint]
    if min(result.priority_confidence, result.impact_confidence) < config.LOW_CONFIDENCE:
        result.flags.append("low_confidence")
    return {"result": result}


def node_write(state: TickerState) -> dict:
    r, o = state["result"].model_copy(deep=True), state["outcome"]
    try:
        reasons = write_reasons(state["article"], r, o.event.description if o.event else "", state.get("feedback"))
        r.relevance_reason, r.priority_reason, r.impact_reason = (
            reasons.relevance_reason, reasons.priority_reason, reasons.impact_reason)
    except LLMStopError as exc:
        r.flags.append("needs_review")
        r.flags.append(f"write_stopped:{exc.stop_reason}")
        return {"result": r, "attempts": MAX_WRITE_ATTEMPTS, "feedback": []}
    return {"result": r, "attempts": state.get("attempts", 0) + 1}


def node_validate(state: TickerState) -> dict:
    r = state["result"]
    if "needs_review" in r.flags:
        return {"feedback": []}
    profile = load_profiles()[r.ticker]
    errors = check(r, state["article"].content, extra_sources=[profile.raw_yaml])
    return {"feedback": errors}


def after_validate(state: TickerState):
    if state.get("feedback") and state.get("attempts", 0) < MAX_WRITE_ATTEMPTS:
        return "write"
    return "finish"


def node_finish(state: TickerState) -> dict:
    r = state["result"]
    if state.get("feedback"):
        r.flags.append("validation_failed")
        r.flags.extend(f"validate:{e}" for e in state["feedback"])
    return {"results": [r]}


def skip_if_irrelevant(state: TickerState):
    o = state["outcome"]
    return "end" if o.relevance == Relevance.KLQ or o.event is None else "impact"


def build_ticker_graph():
    g = StateGraph(TickerState)
    g.add_node("relevance", node_relevance)
    g.add_node("rules", node_rules)
    g.add_node("impact", node_impact)
    g.add_node("write", node_write)
    g.add_node("validate", node_validate)
    g.add_node("finish", node_finish)
    g.add_edge(START, "relevance")
    g.add_edge("relevance", "rules")
    g.add_conditional_edges("rules", skip_if_irrelevant, {"impact": "impact", "end": END})
    g.add_edge("impact", "write")
    g.add_edge("write", "validate")
    g.add_conditional_edges("validate", after_validate, {"write": "write", "finish": "finish"})
    g.add_edge("finish", END)
    return g.compile()


@lru_cache
def ticker_graph():
    return build_ticker_graph()


def node_ticker(state: TickerState) -> dict:
    # Run the per-ticker subgraph and hand back only `results`, so parallel
    # branches don't all write `article`/`facts` into the parent state.
    out = ticker_graph().invoke(state)
    return {"results": out.get("results", [])}


@lru_cache
def build_graph():
    g = StateGraph(GraphState)
    g.add_node("extract", node_extract)
    g.add_node("ticker", node_ticker)
    g.add_edge(START, "extract")
    g.add_conditional_edges("extract", fan_out, ["ticker", END])
    g.add_edge("ticker", END)
    return g.compile()


def evaluate(article: Article) -> list[TickerResult]:
    """Entry point for the main system: one article -> one result per relevant watchlist ticker."""
    out = build_graph().invoke({"article": article, "results": []})
    if out.get("error"):
        raise LLMStopError(out["error"])
    order = {t: i for i, t in enumerate(article.watchlist)}
    return sorted(out.get("results", []), key=lambda r: order.get(r.ticker, 99))
