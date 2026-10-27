"""Graph wiring with the Claude calls stubbed out (no API key needed)."""

from datetime import date

import pytest

import pipeline.graph as graph
from pipeline.schemas import (Article, ArticleFacts, EventFact, Figure, Impact, Priority,
                              Reasons, Relevance, TickerMention)

ARTICLE = Article(
    title="Công ty con của Masan đăng ký mua 73 triệu cổ phiếu MCH; khối ngoại bán ròng FPT",
    published_at=date(2026, 10, 9),
    content="Masan đăng ký mua 73 triệu cổ phiếu MCH, giá trị khoảng 10.400 tỷ đồng. "
            "Khối ngoại bán ròng 107 tỷ đồng mã FPT. HPG nằm trong danh sách tăng giá.",
)

FACTS = ArticleFacts(
    events=[
        EventFact(event_id="e1", event_type="A05", description="Masan mua thêm 73 triệu CP MCH",
                  subject_entity="Masan Consumer", parties=["Masan"], is_new_info=True,
                  is_update_of_announced_event=False,
                  figures=[Figure(metric="transaction_value_vnd", value=10_400e9, unit="VND",
                                  quote="giá trị khoảng 10.400 tỷ đồng")]),
        EventFact(event_id="e2", event_type="A23", description="Khối ngoại bán ròng FPT",
                  subject_entity="FPT", is_new_info=True, is_update_of_announced_event=False,
                  figures=[Figure(metric="foreign_net_vnd", value=-107e9, unit="VND",
                                  quote="Khối ngoại bán ròng 107 tỷ đồng mã FPT")]),
    ],
    ticker_mentions=[
        TickerMention(ticker="MSN", role="party", via_entity="Masan Consumer", event_ids=["e1"]),
        TickerMention(ticker="FPT", role="data", event_ids=["e2"]),
        TickerMention(ticker="HPG", role="list_only"),
    ],
)


class FakeDM:
    def choice(self, state, question, options):
        return options[0], {o: (1.0 if i == 0 else 0.0) for i, o in enumerate(options)}


def fake_write(article, r, event_desc, feedback=None):
    rel = f"{r.relevance.value} ({r.relevance_rule_ids[0]})."
    pri = f"{r.priority.value} ({r.priority_rule_ids[0]})."
    imp = f"{r.impact.value} ({(r.impact_rule_ids or ['I-YT-8'])[0]})."
    return Reasons(relevance_reason=rel, priority_reason=pri, impact_reason=imp)


@pytest.fixture(autouse=True)
def stub(monkeypatch):
    monkeypatch.setattr(graph, "extract", lambda article: FACTS)
    monkeypatch.setattr(graph, "write_reasons", fake_write)
    monkeypatch.setattr(graph, "decision_model", lambda: FakeDM())


def test_fan_out_returns_relevant_tickers_only():
    results = graph.evaluate(ARTICLE)
    by_ticker = {r.ticker: r for r in results}
    assert set(by_ticker) == {"MSN", "FPT"}  # HPG list_only -> Không liên quan, dropped

    msn = by_ticker["MSN"]
    assert (msn.relevance, msn.priority, msn.impact) == (Relevance.TT, Priority.TB, Impact.TICH_CUC)
    assert "missing_denominator" in msn.flags

    fpt = by_ticker["FPT"]
    assert (fpt.relevance, fpt.priority, fpt.impact) == (Relevance.TT, Priority.TB, Impact.TIEU_CUC)
    assert fpt.priority_reason.startswith("Trung bình")
    assert not any(f.startswith("validation_failed") for f in fpt.flags)


def test_validation_failure_retries_then_flags(monkeypatch):
    calls = []

    def bad_write(article, r, event_desc, feedback=None):
        calls.append(feedback)
        return Reasons(relevance_reason="x", priority_reason="y", impact_reason="z")

    monkeypatch.setattr(graph, "write_reasons", bad_write)
    results = graph.evaluate(ARTICLE)
    assert all("validation_failed" in r.flags for r in results)
    assert len(calls) == 2 * len(results)          # one retry per ticker
    assert any(fb for fb in calls)                 # retry received the validation errors
