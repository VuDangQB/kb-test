"""Jev scorecard and its use in the graph, with the Jev client faked (no API key needed)."""

from datetime import date
from types import SimpleNamespace

import pytest

import pipeline.graph as graph
import pipeline.jev_scorecard as sc
from pipeline import config
from pipeline.schemas import Article, ArticleFacts, EventFact, Figure, Reasons, TickerMention

ARTICLE = Article(title="MWG đứng ngoài danh sách FTSE, nhưng BHX và kho tiền vẫn đáng chú ý",
                  published_at=date(2026, 9, 1),
                  content="MWG không có tên trong 117 cổ phiếu FTSE bổ sung. BHX doanh thu 8 tháng tăng 32%.")
FACTS = ArticleFacts(
    events=[
        EventFact(event_id="E1", event_type="A27", description="MWG không vào rổ FTSE", subject_entity="MWG",
                  is_new_info=True, is_update_of_announced_event=False),
        EventFact(event_id="E2", event_type="A02", description="BHX tăng 32%", subject_entity="Bách Hóa Xanh",
                  is_new_info=True, is_update_of_announced_event=False,
                  figures=[Figure(metric="kpi_yoy_pct", value=32, unit="%", quote="tăng 32%")]),
    ],
    ticker_mentions=[TickerMention(ticker="MWG", role="subject", event_ids=["E1", "E2"])],
)


def choice(answer, probs, conf=0.5):
    return SimpleNamespace(type="choice", choice=answer, probabilities=probs, confidence=conf)


def noul(p):
    return SimpleNamespace(type="noul", noul=p)


class FakeJev:
    def __init__(self, answers):
        self.answers, self.questions = answers, None

    def system_one(self, state, questions):
        self.questions = questions
        return SimpleNamespace(answers=self.answers, model="jev-test",
                               usage=SimpleNamespace(input_tokens=2100, output_tokens=60))


ANSWERS = {
    "MWG__relevance": choice("Trực tiếp", {"Trực tiếp": 0.95, "Gián tiếp": 0.04, "Không liên quan": 0.01}),
    "MWG__main_event": choice("E1", {"E1": 0.7, "E2": 0.3}),
    "MWG__is_new": noul(0.9),
    "MWG__is_update": noul(0.1),
    "MWG__has_numbers": noul(0.8),
    "MWG__offsetting": noul(0.85),
    "MWG__priority": choice("Cao", {"Cao": 0.6, "Trung bình": 0.35, "Thấp": 0.05}),
    "MWG__impact": choice("Trung lập", {"Tích cực": 0.2, "Tiêu cực": 0.2, "Trung lập": 0.6}),
    "MWG__impact_score": SimpleNamespace(type="score", score=1.9, confidence=0.4,
                                         probabilities={"0": 0.05, "1": 0.2, "2": 0.5, "3": 0.2, "4": 0.05}),
}


def test_questions_cover_every_decision_and_main_event_only_when_needed():
    qs = sc.build_questions(FACTS)
    assert {k.split(sc.SEP)[1] for k in qs if sc.SEP + "ev" + sc.SEP not in k} == {
        "relevance", "main_event", "is_new", "is_update", "has_numbers", "offsetting", "priority", "impact",
        "impact_score"}
    assert {k for k in qs if "__ev__" in k} == {f"MWG__ev__{e}__{q}" for e in ("E1", "E2")
                                               for q in ("role", "impact")}
    assert set(qs["MWG__main_event"].criteria) == {"E1", "E2"}
    single = FACTS.model_copy(update={"events": FACTS.events[:1]})
    assert "MWG__main_event" not in sc.build_questions(single)


def test_score_article_parses_answers_per_ticker(monkeypatch):
    monkeypatch.setattr(sc, "client", lambda: FakeJev(ANSWERS))
    out = sc.score_article(ARTICLE, FACTS)["MWG"]
    assert out["main_event"]["answer"] == "E1" and out["main_event"]["p"] == 0.7
    assert out["offsetting"] == {"answer": True, "p": 0.85}
    assert out["impact_score"]["score"] == pytest.approx(-0.1)


@pytest.fixture
def jev_graph(monkeypatch):
    monkeypatch.setattr(config, "DECISION_BACKEND", "jev")
    monkeypatch.setattr(sc, "client", lambda: FakeJev(ANSWERS))
    monkeypatch.setattr(graph, "extract", lambda article: FACTS)
    monkeypatch.setattr(graph, "write_reasons", lambda a, r, d, feedback=None: Reasons(
        relevance_reason=f"{r.relevance.value} ({r.relevance_rule_ids[0]}).",
        priority_reason=f"{r.priority.value} ({r.priority_rule_ids[0]}).",
        impact_reason=f"{r.impact.value} ({r.impact_rule_ids[0]})."))


def test_jev_picks_main_event_and_code_keeps_thresholds(jev_graph):
    [r] = graph.evaluate(ARTICLE)
    # Without Jev the A02 KPI (+32%, Cao) would win; Jev's focus event is the FTSE exclusion.
    assert r.event_type == "A27" and r.priority.value == "Trung bình" and "G-9" in r.priority_rule_ids
    assert r.impact.value == "Trung lập" and r.impact_rule_ids == ["I-TL-a"]   # offset by BHX
    assert "jev_disagrees:priority=Cao(0.60)" in r.flags                         # shadow score differs
    assert r.scores["main_event"]["answer"] == "E1"


def test_without_jev_highest_priority_event_wins(monkeypatch, jev_graph):
    monkeypatch.setattr(config, "DECISION_BACKEND", "claude")
    [r] = graph.evaluate(ARTICLE)
    assert r.event_type == "A02" and r.priority.value == "Cao" and "G-6" in r.priority_rule_ids
    assert r.scores == {}


def test_jev_failure_falls_back_to_rules(monkeypatch, jev_graph):
    class Broken:
        def system_one(self, **_):
            raise ConnectionError("down")
    monkeypatch.setattr(sc, "client", lambda: Broken())
    [r] = graph.evaluate(ARTICLE)
    assert r.event_type == "A02" and r.scores == {} and "jev_missing" in r.flags


def test_jev_offsetting_turns_index_exclusion_neutral(monkeypatch, jev_graph):
    # BHX extracted without a usable metric: only Jev's offsetting judgment can trigger the A27 exception.
    facts = FACTS.model_copy(update={"events": [FACTS.events[0], FACTS.events[1].model_copy(update={"figures": [
        Figure(metric="other", value=40_100e9, unit="VND", quote="40.100 tỷ đồng")]})]})
    monkeypatch.setattr(graph, "extract", lambda article: facts)
    [r] = graph.evaluate(ARTICLE)
    assert r.event_type == "A27" and r.impact.value == "Trung lập" and r.impact_rule_ids == ["I-TL-a"]


def test_per_event_roles_and_extract_disagreement(monkeypatch, jev_graph):
    answers = dict(ANSWERS, **{
        "MWG__ev__E1__role": choice("Trọng tâm", {"Trọng tâm": 0.9, "Bối cảnh": 0.1}),
        "MWG__ev__E2__role": choice("Bối cảnh", {"Bối cảnh": 0.7, "Ngược chiều": 0.3}),   # extract said "new"
        "MWG__ev__E2__impact": choice("Tích cực", {"Tích cực": 0.8, "Tiêu cực": 0.05, "Trung lập": 0.15}),
    })
    monkeypatch.setattr(sc, "client", lambda: FakeJev(answers))
    [r] = graph.evaluate(ARTICLE)
    ev = r.scores["events"]
    assert ev["E2"]["event_type"] == "A02" and ev["E2"]["extract_is_new"] is True
    assert ev["E2"]["role"]["answer"] == "Bối cảnh" and ev["E2"]["impact"]["answer"] == "Tích cực"
    assert "jev_disagrees:E2.role=Bối cảnh(0.70)/extract=mới" in r.flags


def test_boundaries_merge_details_drop_background_and_offset(monkeypatch, jev_graph):
    from pipeline.schemas import ROLE_BACKGROUND, ROLE_DETAIL, ROLE_FOCUS, ROLE_OFFSET
    from pipeline.profiles import load_profiles
    from pipeline.rules import evaluate_ticker
    issue = EventFact(event_id="E1", event_type="A06", description="NVL chào bán 800 triệu CP", subject_entity="Novaland",
                      is_new_info=True, is_update_of_announced_event=False,
                      figures=[Figure(metric="issue_shares", value=800e6, unit="cổ phiếu", quote="800 triệu cổ phiếu")])
    capital = EventFact(event_id="E2", event_type="A06", description="Vốn điều lệ hiện tại", subject_entity="Novaland",
                        is_new_info=True, is_update_of_announced_event=False,
                        figures=[Figure(metric="charter_capital_vnd", value=19_500e9, unit="VND", quote="19.500 tỷ")])
    old_kqkd = EventFact(event_id="E3", event_type="A01", description="Lãi 9 tháng", subject_entity="Novaland",
                         is_new_info=True, is_update_of_announced_event=False,
                         figures=[Figure(metric="npat_growth_pct", value=300, unit="%", quote="tăng 300%")])
    facts = ArticleFacts(events=[issue, capital, old_kqkd],
                         ticker_mentions=[TickerMention(ticker="NVL", role="subject", event_ids=["E1", "E2", "E3"])])
    m = facts.ticker_mentions[0]
    roles = {"E1": ROLE_FOCUS, "E2": ROLE_DETAIL, "E3": ROLE_BACKGROUND}
    o = evaluate_ticker(m, facts, load_profiles()["NVL"], date(2026, 10, 20), event_roles=roles)
    # E2's charter capital gives the denominator: 800 tr / 1.950 tr CP = 41% → Cao; E3 (Cao by itself) is ignored.
    assert o.event.event_id == "E1" and o.priority.value == "Cao" and "G-9" in o.priority_rule_ids
    assert "41,0%" in next(iter(o.computed.values()))
    roles["E3"] = ROLE_OFFSET
    o = evaluate_ticker(m, facts, load_profiles()["NVL"], date(2026, 10, 20), event_roles=roles)
    assert o.event.event_id == "E1"  # the offset never becomes the focus


def test_price_only_event_is_never_the_focus_when_fundamentals_exist(monkeypatch, jev_graph):
    price = EventFact(event_id="E3", event_type="A35", description="HPG tăng 2,99%", subject_entity="HPG",
                      is_new_info=True, is_update_of_announced_event=False)
    output = EventFact(event_id="E1", event_type="A02", description="Sản lượng 9T +39%", subject_entity="HPG",
                       is_new_info=True, is_update_of_announced_event=False,
                       figures=[Figure(metric="kpi_yoy_pct", value=39, unit="%", quote="tăng 39%")])
    facts = ArticleFacts(events=[output, price],
                         ticker_mentions=[TickerMention(ticker="HPG", role="subject", event_ids=["E1", "E3"])])
    answers = {"HPG__main_event": choice("E3", {"E3": 0.99, "E1": 0.01}),
               "HPG__impact": choice("Tích cực", {"Tích cực": 1.0, "Tiêu cực": 0.0, "Trung lập": 0.0})}
    monkeypatch.setattr(sc, "client", lambda: FakeJev(answers))
    monkeypatch.setattr(graph, "extract", lambda article: facts)
    [r] = graph.evaluate(ARTICLE.model_copy(update={"watchlist": ["HPG"]}))
    assert r.event_type == "A02" and r.priority.value == "Cao" and r.impact.value == "Tích cực"
    assert "focus_not_price_only:E3→E1" in r.flags
