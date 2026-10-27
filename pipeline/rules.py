"""tieu_chi_v2 as code: relevance from roles, priority thresholds/modifiers/floors,
and the deterministic part of impact. Anything that needs judgment returns None
so the graph can hand it to the DecisionModel.
"""

from dataclasses import dataclass, field
from datetime import date

from .catalog import CATALOG, EventSpec
from .profiles import Profile
from .schemas import (ArticleFacts, EventFact, Evidence, Impact, Priority,
                      Relevance, TickerMention)

TB, CAO, THAP = Priority.TB, Priority.CAO, Priority.THAP
POS, NEG, NEU = Impact.TICH_CUC, Impact.TIEU_CUC, Impact.TRUNG_LAP
TY = 1_000_000_000  # 1 tỷ đồng


@dataclass
class Ctx:
    profile: Profile
    published_at: date
    fin: dict
    listed_sub_event: bool = False


@dataclass
class TierResult:
    tier: Priority | None
    rule_ids: list[str] = field(default_factory=list)
    computed: dict[str, str] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    from_data: bool = False  # tier backed by a figure with a denominator


@dataclass
class RuleOutcome:
    ticker: str
    relevance: Relevance | None                  # None -> DecisionModel
    relevance_rule_ids: list[str]
    event: EventFact | None = None
    priority: Priority | None = None
    priority_rule_ids: list[str] = field(default_factory=list)
    impact: Impact | None = None                 # None -> DecisionModel
    impact_rule_ids: list[str] = field(default_factory=list)
    impact_hint: str = ""                        # rule id suggested to the DecisionModel
    computed: dict[str, str] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def fig(ev: EventFact, metric: str) -> float | None:
    for f in ev.figures:
        if f.metric == metric:
            return f.value
    return None


def pct(x: float) -> str:
    return f"{x:.1f}%".replace(".", ",")


def ty(x: float) -> str:
    return f"{x / TY:,.0f} tỷ đồng".replace(",", ".")


def _ratio(num: float | None, den: float | None) -> float | None:
    if num is None or not den:
        return None
    return abs(num) / den * 100


# ---------------------------------------------------------------------------
# Relevance (Mục 2)
# ---------------------------------------------------------------------------

def decide_relevance(m: TickerMention, facts: ArticleFacts, ctx: Ctx) -> tuple[Relevance | None, list[str]]:
    events = [e for e in facts.events if e.event_id in m.event_ids]
    if any(e.event_type == "A33" for e in events) and m.role in ("macro", "list_only", "sector"):
        return Relevance.KLQ, ["R-KLQ-2"]

    match m.role:
        case "party":
            return Relevance.TT, ["R-TT-3"]
        case "data":
            return Relevance.TT, ["R-TT-4"]
        case "sector":
            return Relevance.GT, ["R-GT-b"]
        case "ecosystem":
            return Relevance.GT, ["R-GT-a2"]
        case "illustrative":
            return Relevance.GT, ["R-GT-a3"]
        case "list_only":
            return Relevance.KLQ, ["R-KLQ-1"]
        case "macro":
            return Relevance.KLQ, ["R-KLQ-2"]
        case "unclear":
            return None, []
        case "subject":
            ent = ctx.profile.find_entity(m.via_entity) if m.via_entity else None
            if ent is None:
                return Relevance.TT, ["R-TT-1"]
            if ent.kind == "shareholder":
                return Relevance.TT, ["R-TT-1"]
            if ent.is_listed_on(ctx.published_at):
                return Relevance.GT, ["R-GT-a1"]
            return Relevance.TT, ["R-TT-2"]
    return None, []


def is_listed_sub_event(ev: EventFact, ctx: Ctx) -> bool:
    """Event whose subject is a separately listed subsidiary/associate of the ticker (G-5)."""
    ent = ctx.profile.find_entity(ev.subject_entity)
    if ent is not None and ent.kind != "shareholder" and ent.is_listed_on(ctx.published_at):
        return True
    return ev.event_type in ("A03", "A04", "A05")


# ---------------------------------------------------------------------------
# Thresholds (Mục 3.2)
# ---------------------------------------------------------------------------

def th_results(ev: EventFact, ctx: Ctx) -> TierResult:
    rev, npat, plan = fig(ev, "revenue_growth_pct"), fig(ev, "npat_growth_pct"), fig(ev, "plan_completion_pct")
    if rev is None and npat is None and plan is None:
        return TierResult(TB, ["P-TH-01", "P-MOD-5"], flags=["missing_numbers"])
    computed = {}
    if rev is not None:
        computed["Tăng trưởng doanh thu"] = pct(rev)
    if npat is not None:
        computed["Tăng trưởng lợi nhuận"] = pct(npat)
    if plan is not None:
        computed["Hoàn thành kế hoạch năm"] = pct(plan)
    if (rev is not None and abs(rev) > 10) or (npat is not None and abs(npat) > 15) or (plan is not None and plan >= 100):
        return TierResult(CAO, ["P-TH-01"], computed, from_data=True)
    biggest = max(abs(x) for x in (rev, npat) if x is not None) if (rev is not None or npat is not None) else 0
    return TierResult(TB if biggest >= 5 else THAP, ["P-TH-01"], computed, from_data=True)


def _shares_outstanding(ev: EventFact, ctx: Ctx) -> tuple[float | None, str]:
    if (s := fig(ev, "shares_outstanding")):
        return s, "bài"
    if (cap := fig(ev, "charter_capital_vnd")):
        return cap / 10_000, "vốn điều lệ trong bài / mệnh giá 10.000đ"
    if (s := ctx.fin.get("shares_outstanding")):
        return s, f"hồ sơ mã ({ctx.fin.get('as_of')})"
    return None, ""


def th_issuance(ev: EventFact, ctx: Ctx) -> TierResult:
    p = fig(ev, "issue_pct")
    computed, source = {}, "bài"
    if p is None:
        shares = fig(ev, "issue_shares")
        den, source = _shares_outstanding(ev, ctx)
        p = _ratio(shares, den)
        if shares is not None and p is None:
            return TierResult(TB, ["P-TH-02", "P-MOD-5"], flags=["missing_denominator"])
    if p is None:
        return TierResult(TB, ["P-TH-02", "P-MOD-5"], flags=["missing_numbers"])
    computed["Tỷ lệ phát hành / CP lưu hành"] = f"{pct(p)} (mẫu số: {source})"
    tier = CAO if p > 10 else TB if p >= 3 else THAP
    return TierResult(tier, ["P-TH-02"], computed, from_data=True)


def th_dividend(ev: EventFact, ctx: Ctx) -> TierResult:
    y, payout = fig(ev, "dividend_yield_pct"), fig(ev, "payout_pct")
    computed = {}
    if y is None:
        dps = fig(ev, "dps_vnd")
        price = fig(ev, "share_price_vnd") or ctx.fin.get("share_price")
        y = _ratio(dps, price)
    if y is not None:
        computed["Lợi suất cổ tức"] = pct(y)
    if payout is not None:
        computed["Tỷ lệ chi trả / LNST"] = pct(payout)
    if (y is not None and y >= 6) or (payout is not None and payout >= 60):
        return TierResult(CAO, ["P-TH-03"], computed, from_data=True)
    return TierResult(TB, ["P-TH-03"], computed, from_data=bool(computed))


def th_contract(ev: EventFact, ctx: Ctx) -> TierResult:
    value, backlog = fig(ev, "contract_value_vnd"), fig(ev, "backlog_growth_pct")
    if value is None and backlog is None:
        return TierResult(TB, ["P-TH-04", "P-MOD-5"], flags=["contract_value_missing"])
    r = _ratio(value, ctx.fin.get("revenue_ttm"))
    computed = {}
    if r is not None:
        computed["Giá trị HĐ / DT TTM"] = pct(r)
    if backlog is not None:
        computed["Tăng backlog"] = pct(backlog)
    if r is None and backlog is None:
        return TierResult(TB, ["P-TH-04"], flags=["missing_denominator"])
    if (r or 0) >= 10 or (backlog or 0) >= 20:
        return TierResult(CAO, ["P-TH-04"], computed, from_data=True)
    if (r or 0) >= 3 or (backlog or 0) >= 5:
        return TierResult(TB, ["P-TH-04"], computed, from_data=True)
    return TierResult(THAP, ["P-TH-04"], computed, from_data=True)


def _investment_tier(value: float | None, ev: EventFact, ctx: Ctx, rule: str) -> TierResult:
    cap = fig(ev, "capacity_increase_pct")
    if value is None and cap is None:
        return TierResult(TB, [rule, "P-MOD-5"], flags=["missing_numbers"])
    computed = {}
    if value is not None:
        computed["Giá trị"] = ty(value)
    if ev.new_business_line and value is not None and value >= 1_000 * TY:
        computed["Lĩnh vực mới"] = "có"
        return TierResult(CAO, [rule], computed, from_data=True)
    r_ta, r_eq = _ratio(value, ctx.fin.get("total_assets")), _ratio(value, ctx.fin.get("equity"))
    if r_ta is not None:
        computed["Giá trị / tổng tài sản"] = pct(r_ta)
    if r_eq is not None:
        computed["Giá trị / VCSH"] = pct(r_eq)
    if cap is not None:
        computed["Công suất tăng thêm"] = pct(cap)
    if r_ta is None and r_eq is None and cap is None:
        return TierResult(TB, [rule], computed, flags=["missing_denominator"])
    if (r_ta or 0) > 10 or (r_eq or 0) > 20 or (cap or 0) > 20:
        return TierResult(CAO, [rule], computed, from_data=True)
    if (r_ta or 0) >= 3 or (r_eq or 0) >= 5 or (cap or 0) >= 5:
        return TierResult(TB, [rule], computed, from_data=True)
    return TierResult(THAP, [rule], computed, from_data=True)


def th_investment(ev: EventFact, ctx: Ctx) -> TierResult:
    return _investment_tier(fig(ev, "investment_value_vnd") or fig(ev, "transaction_value_vnd"), ev, ctx, "P-TH-05")


def th_transaction(ev: EventFact, ctx: Ctx) -> TierResult:
    return _investment_tier(fig(ev, "transaction_value_vnd") or fig(ev, "investment_value_vnd"), ev, ctx, "P-TH-05")


def th_project_stop(ev: EventFact, ctx: Ctx) -> TierResult:
    return _investment_tier(fig(ev, "project_value_vnd") or fig(ev, "investment_value_vnd"), ev, ctx, "P-TH-12")


def th_kpi(ev: EventFact, ctx: Ctx) -> TierResult:
    k = fig(ev, "kpi_yoy_pct")
    if k is None:
        return TierResult(TB, ["P-TH-06", "P-MOD-5"], flags=["missing_numbers"])
    computed = {"KPI YoY": pct(k)}
    if not ev.core_segment:
        computed["Mảng"] = "không cốt lõi"
        return TierResult(TB if abs(k) >= 10 else THAP, ["P-TH-06"], computed, from_data=True)
    tier = CAO if abs(k) >= 30 else TB if abs(k) >= 10 else THAP
    return TierResult(tier, ["P-TH-06"], computed, from_data=True)


def th_legal(ev: EventFact, ctx: Ctx) -> TierResult:
    return TierResult(CAO if ev.material_project_with_numbers else TB, ["P-TH-11"], from_data=ev.material_project_with_numbers)


def th_penalty(ev: EventFact, ctx: Ctx) -> TierResult:
    return TierResult(CAO if ev.affects_main_market else TB, ["A16"])


def th_insider(ev: EventFact, ctx: Ctx) -> TierResult:
    computed = {}
    if (own := fig(ev, "ownership_after_pct")) is not None:
        computed["Sở hữu sau giao dịch"] = pct(own)
    return TierResult(CAO if ev.control_change else TB, ["P-TH-10"], computed, from_data=ev.control_change)


def th_foreign(ev: EventFact, ctx: Ctx) -> TierResult:
    cum = fig(ev, "foreign_cum_pct_shares")
    computed = {}
    if (net := fig(ev, "foreign_net_vnd")) is not None:
        computed["Khối ngoại ròng"] = ty(net)
    if cum is not None:
        computed["Lũy kế / CP lưu hành"] = pct(cum)
    if ev.foreign_cumulative_focus and cum is not None:
        return TierResult(CAO, ["P-TH-09"], computed, from_data=True)
    return TierResult(TB, ["P-TH-09"], computed)


THRESHOLDS = {
    "results": th_results, "issuance": th_issuance, "dividend": th_dividend,
    "contract": th_contract, "investment": th_investment, "transaction": th_transaction,
    "project_stop": th_project_stop, "kpi": th_kpi, "legal": th_legal, "penalty": th_penalty,
    "insider": th_insider, "foreign": th_foreign,
}


# ---------------------------------------------------------------------------
# Priority (Mục 3.2 → 3.3 → 3.4)
# ---------------------------------------------------------------------------

def priority_for_event(ev: EventFact, spec: EventSpec, relevance: Relevance, facts: ArticleFacts, ctx: Ctx) -> TierResult:
    if spec.threshold:
        res = THRESHOLDS[spec.threshold](ev, ctx)
    else:
        res = TierResult(spec.priority, [spec.code])
    tier = res.tier or spec.priority or TB
    ids = [spec.code, *[r for r in res.rule_ids if r != spec.code]]

    is_update = ev.is_update_of_announced_event or ev.event_type == "A07"
    if is_update and not ev.update_changes_terms:
        tier = Priority.from_rank(tier.rank - 1)
        ids.append("P-MOD-1")
    if relevance == Relevance.GT and tier == CAO:
        tier = TB
        ids.append("P-MOD-2")
    if ctx.listed_sub_event and not ev.parent_impact_quantified and tier == CAO:
        tier = TB
        ids.append("P-MOD-3")
    if facts.multi_ticker_equal and tier == CAO and not res.from_data:
        tier = TB
        ids.append("P-MOD-4")
    if spec.floor_tb and tier == THAP:
        tier = TB
        ids.append("P-SAN")
    return TierResult(tier, ids, res.computed, res.flags, res.from_data)


# ---------------------------------------------------------------------------
# Impact (Mục 4) — deterministic part
# ---------------------------------------------------------------------------

def imp_results(ev: EventFact, ctx: Ctx) -> tuple[Impact | None, list[str], str]:
    if ev.offsetting_factor:
        return None, [], "I-TL-a"
    signs = [x for x in (fig(ev, "revenue_growth_pct"), fig(ev, "npat_growth_pct")) if x is not None]
    plan = fig(ev, "plan_completion_pct")
    if plan is not None:
        signs.append(plan - 100 if plan < 100 else 1)
    if signs and all(s > 0 for s in signs):
        return POS, ["I-YT-1"], ""
    if signs and all(s < 0 for s in signs):
        return NEG, ["I-YT-1"], ""
    return None, [], "I-TL-a"


def imp_subsidiary(ev, ctx):
    if ev.intra_group_transfer:
        return NEU, ["I-TL-e"], ""
    if not ev.parent_impact_quantified and not ev.figures:
        return NEU, ["I-TL-b"], ""
    return None, [], ""


def imp_kpi(ev, ctx):
    k = fig(ev, "kpi_yoy_pct")
    if ev.offsetting_factor or k is None or k == 0:
        return None, [], "I-TL-a" if ev.offsetting_factor else "I-TL-b"
    return (POS if k > 0 else NEG), ["I-YT-3"], ""


def imp_issuance(ev, ctx):
    if ev.proceeds_for_debt:
        return NEU, ["I-TL-a"], ""
    return NEG, ["I-YT-7"], ""


def imp_dividend(ev, ctx):
    return (NEG, ["I-YT-7"], "") if ev.dividend_cut else (POS, ["I-YT-7"], "")


def imp_esop(ev, ctx):
    return (NEU, ["I-TL-a"], "") if ev.performance_conditions else (NEG, ["I-YT-7"], "")


def imp_insider_sell(ev, ctx):
    return (NEG, ["I-YT-8"], "") if ev.control_change else (NEU, ["I-TL-f"], "")


def imp_foreign(ev, ctx):
    net = fig(ev, "foreign_net_vnd")
    if net is None:
        return None, [], ""
    return (POS if net > 0 else NEG), ["I-YT-8"], ""


IMPACT_HANDLERS = {
    "results": imp_results, "subsidiary": imp_subsidiary, "issuance": imp_issuance,
    "dividend": imp_dividend, "esop": imp_esop, "insider_sell": imp_insider_sell,
    "foreign": imp_foreign, "kpi": imp_kpi,
}


def impact_for_event(ev: EventFact, spec: EventSpec, facts: ArticleFacts, ctx: Ctx) -> tuple[Impact | None, list[str], str]:
    if isinstance(spec.impact, Impact):
        return spec.impact, [spec.impact_rule] if spec.impact_rule else [], ""
    if spec.impact == "DM":
        imp, ids, hint = None, [], ""
    else:
        imp, ids, hint = IMPACT_HANDLERS[spec.impact](ev, ctx)
    if imp is None and facts.multi_ticker_equal:
        hint = hint or "I-TL-c"
    return imp, ids, hint


# ---------------------------------------------------------------------------
# Per-ticker orchestration
# ---------------------------------------------------------------------------

def events_for(m: TickerMention, facts: ArticleFacts) -> list[EventFact]:
    by_id = {e.event_id: e for e in facts.events}
    events = [by_id[i] for i in m.event_ids if i in by_id]
    return events or list(facts.events)


def evaluate_ticker(m: TickerMention, facts: ArticleFacts, profile: Profile, published_at: date,
                    relevance: Relevance | None = None, relevance_ids: list[str] | None = None) -> RuleOutcome:
    """Apply v2 to one ticker. Pass `relevance` when it was resolved by the DecisionModel."""
    ctx = Ctx(profile=profile, published_at=published_at, fin=profile.financials_at(published_at))
    if relevance is None:
        relevance, relevance_ids = decide_relevance(m, facts, ctx)
    out = RuleOutcome(ticker=m.ticker, relevance=relevance, relevance_rule_ids=relevance_ids or [])
    if relevance is None or relevance == Relevance.KLQ:
        return out

    candidates = events_for(m, facts)
    fresh = [e for e in candidates if e.is_new_info or e.is_update_of_announced_event] or candidates
    if not fresh:
        out.flags.append("no_event")
        return out

    best: tuple[EventFact, TierResult] | None = None
    for ev in fresh:
        ctx.listed_sub_event = is_listed_sub_event(ev, ctx)
        res = priority_for_event(ev, CATALOG[ev.event_type], relevance, facts, ctx)
        if best is None or res.tier.rank > best[1].tier.rank:
            best = (ev, res)
    ev, res = best
    ctx.listed_sub_event = is_listed_sub_event(ev, ctx)
    spec = CATALOG[ev.event_type]

    out.event, out.priority, out.priority_rule_ids = ev, res.tier, res.rule_ids
    out.computed, out.flags = res.computed, list(res.flags)
    if len(fresh) > 1:
        out.priority_rule_ids.append("G-4")
    if ctx.listed_sub_event:
        out.priority_rule_ids.append("G-5")

    out.impact, out.impact_rule_ids, out.impact_hint = impact_for_event(ev, spec, facts, ctx)
    out.evidence = [Evidence(quote=f.quote, metric=f.metric) for f in ev.figures]
    if facts.conflicting_numbers:
        out.flags.append("conflicting_numbers")
    return out
