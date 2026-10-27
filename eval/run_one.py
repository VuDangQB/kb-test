"""Run the pipeline on one or a few articles and compare with the golden labels.

    uv run python -m eval.run_one WL-041
    uv run python -m eval.run_one WL-041 WL-043 KB-8 KB-VD
    uv run python -m eval.run_one https://dantri.com.vn/... [--title "..."]
    uv run python -m eval.run_one WL-041 --extract-only     # 1 Claude call: show extracted facts only
    uv run python -m eval.run_one WL-041 --repeat 5         # run 5 times, report consistency + timing
    uv run python -m eval.run_one WL-041 --phoenix          # also send traces to Phoenix (uv run phoenix serve)

IDs: WL-xxx → research/watchlist_labels_v2.csv; KB-n / KB-VD → KB's workbook (--xlsx or KB_XLSX).
A bare URL is looked up in both sets; if it is in neither, it runs without expected labels.
Results are saved to eval/out/one/<id>.json (all runs, timing and per-call tokens).
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import anthropic

from eval.fetch import fetch
from eval.runstats import agreement, fmt_run, timing_summary
from pipeline import Article, config, evaluate, llm, tracing
from pipeline.extract import extract
from pipeline.llm import USAGE, LLMStopError

ROOT = Path(__file__).resolve().parent.parent
WL_CSV = ROOT / "research" / "watchlist_labels_v2.csv"
KB_XLSX = os.environ.get(
    "KB_XLSX", "/mnt/c/Users/VuDang/Downloads/KB Test Template for AI News Article Evaluation_2026.10.20.xlsx")
OUT = Path(__file__).resolve().parent / "out" / "one"
WATCHLIST = ["NVL", "MSN", "FPT", "HPG", "MWG"]


@dataclass
class Case:
    id: str
    url: str
    title: str = ""
    published_at: date | None = None
    ticker: str = ""                 # ticker the expected labels refer to
    expected: dict | None = None     # relevance / event_type / priority / impact / rules / reason
    other_tickers: str = ""          # free-text expectations for other tickers (watchlist set)


def wl_cases() -> list[Case]:
    with WL_CSV.open(encoding="utf-8-sig") as fh:
        return [Case(r["id"], r["url"], r["title"], date.fromisoformat(r["date"]), r["ticker"],
                     {k: r[k] for k in ("relevance", "event_type", "priority", "impact", "rules", "reason")},
                     r["other_tickers"])
                for r in csv.DictReader(fh)]


def kb_cases(xlsx: str) -> list[Case]:
    from eval.run_eval import read_kb
    if not Path(xlsx).exists():
        return []
    return [Case(f"KB-{r.stt}", r.url, r.title, None, r.ticker,
                 {"priority": r.exp_priority, "impact": r.exp_impact})
            for r in read_kb(xlsx)]


def resolve(token: str, xlsx: str, title: str) -> Case:
    token = token.strip()
    if token.lower().startswith("http"):
        for c in wl_cases() + kb_cases(xlsx):
            if c.url.strip() == token:
                return c
        return Case("URL", token, title)
    m = re.fullmatch(r"(?i)(WL|KB)[-_ ]?(\w+)", token)
    if not m:
        raise SystemExit(f"Không hiểu '{token}'. Dùng WL-041, KB-8, KB-VD hoặc một URL.")
    kind, num = m.group(1).upper(), m.group(2).upper()
    if kind == "WL":
        want = f"WL-{int(num):03d}" if num.isdigit() else f"WL-{num}"
        pool = wl_cases()
    else:
        want = f"KB-{num}"
        pool = kb_cases(xlsx)
        if not pool:
            raise SystemExit(f"Không thấy file KB: {xlsx} (đặt --xlsx hoặc KB_XLSX)")
    for c in pool:
        if c.id.upper() == want:
            return c
    raise SystemExit(f"Không có bài {want}")


def mark(pred: str, exp: str | None) -> str:
    if not exp:
        return pred or "—"
    return f"{pred or '—'}  {'✅' if pred == exp else f'❌ (golden: {exp})'}"


FIELDS = (("relevance", "Relevance"), ("event_type", "Sự kiện"), ("priority", "Priority"), ("impact", "Ảnh hưởng"))


def labels(r) -> dict:
    return {"relevance": r.relevance.value, "event_type": r.event_type,
            "priority": r.priority.value if r.priority else "", "impact": r.impact.value if r.impact else ""}


def fact_labels(facts) -> dict[str, dict]:
    """--extract-only: per ticker, its role and the event types it is linked to."""
    types = {e.event_id: e.event_type for e in facts.events}
    return {m.ticker: {"role": m.role, "event_type": " ".join(types.get(i, "?") for i in m.event_ids)}
            for m in facts.ticker_mentions}


def print_golden(case: Case) -> None:
    exp = case.expected or {}
    print(f"\n=== {case.id} · {case.title or case.url}")
    if case.expected:
        print(f"Golden [{case.ticker}]: " + " / ".join(v for k, _ in FIELDS if (v := exp.get(k))))
        if exp.get("reason"):
            print(f"  lý do: {exp['reason']}")
    if case.other_tickers:
        print(f"  mã khác: {case.other_tickers}")


def show(case: Case, results) -> None:
    exp = case.expected or {}
    if not results:
        print("Pipeline: không mã watchlist nào liên quan")
    for r in results:
        main = r.ticker == case.ticker
        e = exp if main else {}
        got = labels(r)
        print(f"\n--- {r.ticker}{'  (mã của golden)' if main else ''}")
        print(f"Relevance : {mark(got['relevance'], e.get('relevance'))}")
        print(f"Sự kiện   : {mark(got['event_type'], e.get('event_type'))}")
        print(f"Priority  : {mark(got['priority'], e.get('priority'))}   (p={r.priority_confidence:.2f})")
        print(f"Ảnh hưởng : {mark(got['impact'], e.get('impact'))}   (p={r.impact_confidence:.2f})")
        print(f"Quy tắc   : {' '.join(r.rule_ids)}" + (f"   (golden: {e['rules']})" if e.get("rules") else ""))
        if r.computed:
            print("Số đã tính: " + "; ".join(f"{k} = {v}" for k, v in r.computed.items()))
        if r.flags:
            print(f"Cờ        : {', '.join(r.flags)}")
        for name, text in (("Lý giải Relevance", r.relevance_reason), ("Lý giải Priority", r.priority_reason),
                           ("Lý giải Ảnh hưởng", r.impact_reason)):
            if text:
                print(f"{name}: {text}")
    if case.ticker and case.ticker not in {r.ticker for r in results} \
            and exp.get("relevance") not in (None, "Không liên quan"):
        print(f"\n❌ Pipeline không trả kết quả cho {case.ticker} (golden: {exp.get('relevance')})")


def compact(case: Case, run: dict) -> str:
    """One line per run: labels of every ticker, ✅/❌ for the golden ticker."""
    if run.get("error"):
        return run["error"]
    parts = []
    for t, got in run["labels"].items():
        e = (case.expected or {}) if t == case.ticker else {}
        if "role" in got:  # extract-only
            ok = "" if not e.get("event_type") else (" ✅" if got["event_type"] == e["event_type"] else " ❌")
            parts.append(f"{t}: {got['role']} {got['event_type']}{ok}")
            continue
        vals = [got[k] for k, _ in FIELDS if k != "relevance"]
        marks = "".join("" if not e.get(k) else ("✅" if got[k] == e[k] else "❌") for k, _ in FIELDS if k != "relevance")
        parts.append(f"{t}: {'/'.join(v or '—' for v in vals)} {marks}".rstrip())
    return " | ".join(parts) or "không mã nào liên quan"


def consistency(case: Case, runs: list[dict]) -> list[str]:
    ok = [r for r in runs if not r.get("error")]
    if len(ok) < 2:
        return []
    lines = [f"\nĐộ ổn định qua {len(ok)} lần chạy:"]
    tickers = sorted({t for r in ok for t in r["labels"]}, key=lambda t: (t != case.ticker, t))
    keys = ("role", "event_type") if "role" in next(iter(ok[0]["labels"].values()), {}) else [k for k, _ in FIELDS]
    for t in tickers:
        for k in keys:
            vals = [r["labels"].get(t, {}).get(k, "(không có)") for r in ok]
            dist, share = agreement(vals)
            exp = (case.expected or {}).get(k) if t == case.ticker else None
            hit = f" · khớp golden {sum(v == exp for v in vals)}/{len(vals)}" if exp else ""
            flag = "" if share == 1 else "  ⚠️"
            lines.append(f"  {t:<4} {k:<11}: {dist} (đồng nhất {share:.0%}){hit}{flag}")
    return lines


def run_case(case: Case, args, session: str) -> list[dict]:
    fetched = fetch(case.url, case.title, refresh=args.refresh)
    print_golden(case)
    if fetched.text is None:
        print(f"không lấy được bài — {fetched.error}")
        return []
    for w in fetched.warnings:
        print(f"cảnh báo crawl: {w}")
    article = Article(title=case.title or fetched.text.split("\n", 1)[0][:200], url=case.url,
                      published_at=fetched.published_at or case.published_at or date.today(),
                      content=fetched.text, watchlist=WATCHLIST)
    runs = []
    for i in range(1, args.repeat + 1):
        started = time.perf_counter()
        run = {"run": i, "error": ""}
        try:
            tags = [case.id, "extract-only" if args.extract_only else "full"]
            meta = {"case": case.id, "run": i, "model": config.CLAUDE_MODEL}
            with tracing.run_attributes(session_id=session, metadata=meta, tags=tags), llm.collect() as calls:
                if args.extract_only:
                    facts = extract(article)
                    run["labels"], run["facts"] = fact_labels(facts), facts.model_dump(mode="json")
                else:
                    results = evaluate(article)
                    run["labels"] = {r.ticker: labels(r) for r in results}
                    run["results"] = [r.model_dump(mode="json") for r in results]
        except LLMStopError as exc:
            run["error"] = f"Claude dừng — {exc}"
        run["seconds"] = round(time.perf_counter() - started, 2)
        run["calls"] = calls
        runs.append(run)

        if args.repeat == 1 or args.verbose:
            if args.repeat > 1:
                print(f"\n# Lần {i}")
            if run["error"]:
                print(run["error"])
            elif args.extract_only:
                print(json.dumps(run["facts"], ensure_ascii=False, indent=2))
            else:
                show(case, results)
            print(f"\n⏱  {fmt_run(run['seconds'], run['calls'])}")
        else:
            print(f"#{i:<2} {compact(case, run)}   ⏱ {fmt_run(run['seconds'], run['calls'])}")

    for line in consistency(case, runs) + ([""] + timing_summary(runs) if len(runs) > 1 else []):
        print(line)
    return runs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("items", nargs="+", help="WL-041, KB-8, KB-VD hoặc URL")
    ap.add_argument("--title", default="", help="tiêu đề khi chạy URL ngoài bộ golden")
    ap.add_argument("--xlsx", default=KB_XLSX)
    ap.add_argument("--extract-only", action="store_true", help="chỉ chạy bước trích xuất (1 lần gọi Claude)")
    ap.add_argument("--repeat", type=int, default=1, help="số lần chạy lại mỗi bài để đo độ ổn định")
    ap.add_argument("--verbose", "-v", action="store_true", help="in chi tiết mọi lần chạy khi --repeat > 1")
    ap.add_argument("--phoenix", action="store_true", help="gửi trace sang Phoenix (cần `uv run phoenix serve`)")
    ap.add_argument("--refresh", action="store_true", help="crawl lại, bỏ qua cache")
    args = ap.parse_args(argv)
    if args.repeat < 1:
        ap.error("--repeat phải ≥ 1")

    cases = [resolve(t, args.xlsx, args.title) for t in args.items]
    if args.phoenix:  # before the Anthropic client exists (see pipeline/tracing.py)
        if why := tracing.setup():
            print(f"Phoenix tắt: {why}", file=sys.stderr)
        else:
            print(f"Phoenix: đang gửi trace tới {os.environ.get('PHOENIX_COLLECTOR_ENDPOINT', tracing.DEFAULT_ENDPOINT)}")
    try:
        llm.client()
    except (TypeError, RuntimeError, anthropic.AuthenticationError) as exc:
        print(f"Không gọi được Claude: {exc}\nChạy `set -a; source .env; set +a` rồi thử lại.", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for case in cases:
        slug = case.id if case.id != "URL" else "url-" + re.sub(r"\W+", "-", case.url)[-60:]
        runs = run_case(case, args, session=f"{slug}-{stamp}")
        if not runs:
            continue
        suffix = ".facts" if args.extract_only else ""
        path = OUT / f"{slug}{suffix}.json"
        path.write_text(json.dumps({"case": case.id, "url": case.url, "ticker": case.ticker,
                                    "expected": case.expected or {}, "model": config.CLAUDE_MODEL,
                                    "effort": config.EFFORT, "started": stamp, "runs": runs},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"→ {path.relative_to(ROOT)}")

    print(f"\nTổng Claude: {USAGE['calls']} lần gọi · input {USAGE['input_tokens']:,} "
          f"(cache đọc {USAGE['cache_read_input_tokens']:,}, ghi {USAGE['cache_creation_input_tokens']:,}) · "
          f"output {USAGE['output_tokens']:,}")
    tracing.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
