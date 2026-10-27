"""KB's 22 labelled cases (KB Test Template 2026.10.20) against the rule layer.

Facts are hand-written to mirror what `extract` should produce for each article.
Where KB's impact depends on judgment the rules hand to the DecisionModel, the
test asserts impact is delegated (None) and checks the hint instead.
"""

from datetime import date

import pytest

from pipeline.profiles import load_profiles
from pipeline.rules import evaluate_ticker
from pipeline.schemas import (ArticleFacts, EventFact, Figure, Impact, Priority,
                              Relevance, TickerMention)

CAO, TB, THAP = Priority.CAO, Priority.TB, Priority.THAP
POS, NEG, NEU = Impact.TICH_CUC, Impact.TIEU_CUC, Impact.TRUNG_LAP
TY = 1_000_000_000
DM = None  # impact delegated to the DecisionModel


def f(metric, value, unit="", quote="q"):
    return Figure(metric=metric, value=value, unit=unit, quote=quote)


def ev(event_type, subject, figures=(), new=True, update=False, **flags):
    return EventFact(event_id="e1", event_type=event_type, description="d", subject_entity=subject,
                     is_new_info=new, is_update_of_announced_event=update, figures=list(figures), **flags)


def run(ticker, role, event, via="", day=date(2026, 10, 20), multi=False):
    facts = ArticleFacts(events=[event], multi_ticker_equal=multi,
                         ticker_mentions=[TickerMention(ticker=ticker, role=role, via_entity=via, event_ids=["e1"])])
    return evaluate_ticker(facts.ticker_mentions[0], facts, load_profiles()[ticker], day)


CASES = [
    # id, ticker, role, via, event, expected priority, expected impact (DM = delegated), extra checks
    ("VD-FPT-bai-giai-thich-gia-giam", "FPT", "subject", "",
     ev("A24", "FPT", [f("foreign_net_vnd", -14_700 * TY)]),
     TB, NEU),
    ("5-FPT-lai-Q3-ky-luc", "FPT", "subject", "", ev("A01", "FPT", [f("npat_growth_pct", 17.5)]), CAO, POS),
    ("6-FPT-NVIDIA-du-lieu", "FPT", "party", "", ev("A14", "FPT"), THAP, NEU),
    ("7-Vietcap-du-bao-FPT", "FPT", "subject", "", ev("A24", "FPT"), TB, NEU),
    ("8-bai-ngan-hang-co-so-FPT", "FPT", "data", "", ev("A23", "FPT", [f("foreign_net_vnd", -60 * TY)]), TB, NEG),
    ("9-FPT-3-giai-phap-AI", "FPT", "subject", "", ev("A13", "FPT"), TB, POS),
    ("10-NVL-gia-han-chao-ban", "NVL", "subject", "",
     ev("A07", "Novaland", [f("issue_shares", 800_700_000), f("charter_capital_vnd", 24_020 * TY)],
        update=True, proceeds_for_debt=True),
     TB, NEU),
    ("11-NVL-lai-vuot-KH-218-can", "NVL", "subject", "",
     ev("A01", "Novaland", [f("plan_completion_pct", 150)], offsetting_factor=True), CAO, DM),
    ("12-vo-ong-Nhon-ban-CP", "NVL", "subject", "", ev("A22", "Bà Hoàng Thu Châu"), TB, NEU),
    ("13-MSN-lai-9T-vuot-KH", "MSN", "subject", "",
     ev("A01", "Masan", [f("plan_completion_pct", 105), f("npat_growth_pct", 120)]), CAO, POS),
    ("14-MSN-nang-so-huu-MCH", "MSN", "party", "Masan Consumer",
     ev("A05", "Masan Consumer", [f("transaction_value_vnd", 10_400 * TY)], parties=["Masan"]), TB, POS),
    ("15-Elmet-mua-4.99-MSR", "MSN", "party", "Masan High-Tech Materials",
     ev("A04", "Masan High-Tech Materials", [f("transaction_value_vnd", 3_100 * TY)], parties=["Masan", "Elmet"]),
     TB, POS),
    ("16-MSR-tam-ung-co-tuc", "MSN", "subject", "Masan High-Tech Materials",
     ev("A03", "Masan High-Tech Materials", [f("dps_vnd", 2_000)], intra_group_transfer=True), TB, NEU),
    ("17-HPG-ban-5.5tr-tan-HRC", "HPG", "subject", "", ev("A02", "Hòa Phát", [f("kpi_yoy_pct", 59)]), CAO, POS),
    ("18-HPG-ban-heo-trung", "HPG", "subject", "Hòa Phát Nông nghiệp",
     ev("A02", "Hòa Phát Nông nghiệp", [f("kpi_yoy_pct", 20)], core_segment=False), TB, POS),
    ("19-HPG-gop-8000-ty-sieu-do-thi", "HPG", "party", "",
     ev("A12", "Hòa Phát", [f("investment_value_vnd", 8_000 * TY)], new_business_line=True), CAO, DM),
    ("20-con-ong-Long-mua-50tr-CP", "HPG", "subject", "", ev("A21", "Trần Vũ Minh"), TB, POS),
    ("21-HPG-khoi-ngoai-mua-ron", "HPG", "subject", "", ev("A23", "HPG", [f("foreign_net_vnd", 128 * TY)]), TB, POS),
    ("22-MWG-GDKHQ-co-tuc-1000d", "MWG", "subject", "",
     ev("A09", "Thế Giới Di Động", [f("dps_vnd", 1_000), f("share_price_vnd", 76_000)], update=True), TB, POS),
    ("23-Hieu-Em-ban-1tr-MWG", "MWG", "subject", "", ev("A22", "Đoàn Văn Hiểu Em"), TB, NEU),
    ("24-MWG-thu-5.7-ty-USD-9T", "MWG", "subject", "", ev("A01", "Thế Giới Di Động", [f("revenue_growth_pct", 30)]), CAO, POS),
    ("25-DMX-nganh-hang-AI-Robotics", "MWG", "subject", "Điện Máy Xanh",
     ev("A03", "Điện Máy Xanh"), TB, NEU),
]


@pytest.mark.parametrize("case_id,ticker,role,via,event,exp_priority,exp_impact", CASES, ids=[c[0] for c in CASES])
def test_kb_case(case_id, ticker, role, via, event, exp_priority, exp_impact):
    out = run(ticker, role, event, via=via)
    assert out.relevance in (Relevance.TT, Relevance.GT)
    assert out.priority == exp_priority, (out.priority, out.priority_rule_ids, out.computed)
    assert out.impact == exp_impact, (out.impact, out.impact_rule_ids, out.impact_hint)


def test_dmx_is_indirect_after_listing_and_direct_before():
    event = ev("A03", "Điện Máy Xanh")
    after = run("MWG", "subject", event, via="Điện Máy Xanh", day=date(2026, 10, 5))
    before = run("MWG", "subject", event, via="Điện Máy Xanh", day=date(2026, 7, 1))
    assert after.relevance == Relevance.GT and after.relevance_rule_ids == ["R-GT-a1"]
    assert before.relevance == Relevance.TT and before.relevance_rule_ids == ["R-TT-2"]


def test_update_downgrades_issuance_and_computes_dilution():
    out = run("NVL", "subject",
              ev("A07", "Novaland", [f("issue_shares", 800_700_000), f("charter_capital_vnd", 24_020 * TY)], update=True))
    assert "P-MOD-1" in out.priority_rule_ids
    assert out.computed["Tỷ lệ phát hành / CP lưu hành"].startswith("33,3%")


def test_listed_sub_cao_is_capped_without_parent_quantification():
    big = ev("A04", "Masan High-Tech Materials", [f("transaction_value_vnd", 3_100 * TY)], new_business_line=True)
    out = run("MSN", "party", big, via="Masan High-Tech Materials")
    assert out.priority == TB and "P-MOD-3" in out.priority_rule_ids


def test_list_only_is_not_relevant():
    out = run("NVL", "list_only", ev("A35", "VN-Index"))
    assert out.relevance == Relevance.KLQ and out.priority is None


def test_insider_floor_and_control_change():
    assert run("NVL", "subject", ev("A22", "Diamond Properties"), via="Diamond Properties").priority == TB
    out = run("NVL", "subject", ev("A22", "Diamond Properties", control_change=True), via="Diamond Properties")
    assert out.priority == CAO and out.impact == NEG


def test_missing_denominator_is_flagged_not_guessed():
    out = run("MSN", "party", ev("A12", "Masan", [f("investment_value_vnd", 500 * TY)]))
    assert out.priority == TB and "missing_denominator" in out.flags


def test_index_exclusion_is_neutral_when_offset_by_fundamentals_with_numbers():
    excluded = ev("A27", "Thế Giới Di Động")
    bhx = EventFact(event_id="e2", event_type="A02", description="BHX +32% (đã công bố)", subject_entity="Bách Hóa Xanh",
                    is_new_info=False, is_update_of_announced_event=False, figures=[f("kpi_yoy_pct", 32)])
    facts = ArticleFacts(events=[excluded, bhx],
                         ticker_mentions=[TickerMention(ticker="MWG", role="subject", event_ids=["e1", "e2"])])
    m = facts.ticker_mentions[0]
    out = evaluate_ticker(m, facts, load_profiles()["MWG"], date(2026, 9, 1))
    assert out.event.event_type == "A27" and out.priority == Priority.TB
    assert out.impact == Impact.TRUNG_LAP and out.impact_rule_ids == ["I-TL-a"]
    alone = run("MWG", "subject", ev("A27", "Thế Giới Di Động"))
    assert alone.impact == Impact.TIEU_CUC and alone.impact_rule_ids == ["I-YT-8"]
