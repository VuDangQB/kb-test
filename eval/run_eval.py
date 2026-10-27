"""Run the pipeline on KB's test workbook and score it against KB's Expected labels only.

    uv run python -m eval.run_eval "/mnt/c/Users/.../KB Test Template ... .xlsx" [--limit N] [--workers 4]
        [--repeat N]   run the whole set N times and report run-to-run consistency
        [--phoenix]    send traces to Phoenix (`uv run phoenix serve` in another terminal)

Writes eval/out/report.md and eval/out/results.csv (one line per article per run, with time and tokens). The "AI trả ra" columns in
KB's workbook come from another system and are ignored.
"""

import argparse
import csv
import json
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from pathlib import Path

import anthropic
import openpyxl

from eval.fetch import fetch
from eval.runstats import agreement, spread, sum_tokens, timing_summary
from pipeline import Article, config, tracing
from pipeline.graph import evaluate_detailed
from pipeline import llm
from pipeline.llm import USAGE, LLMStopError

OUT = Path(__file__).resolve().parent / "out"
PRIORITIES = ["Cao", "Trung bình", "Thấp"]
IMPACTS = ["Tích cực", "Tiêu cực", "Trung lập"]
WATCHLIST = ["NVL", "MSN", "FPT", "HPG", "MWG"]
SESSION = datetime.now().strftime("%Y%m%d-%H%M%S")  # groups this invocation's traces in Phoenix


@dataclass
class Row:
    stt: str
    ticker: str
    title: str
    url: str
    exp_priority: str
    exp_impact: str
    pred: dict = field(default_factory=dict)
    error: str = ""
    run: int = 1
    events: str = ""
    seconds: float = 0.0
    calls: list = field(default_factory=list)

    @property
    def pri_pass(self) -> bool:
        return self.pred.get("priority") == self.exp_priority

    @property
    def imp_pass(self) -> bool:
        return self.pred.get("impact") == self.exp_impact


def norm_label(value) -> str:
    return " ".join(str(value or "").split()).strip()


def read_kb(path: str) -> list[Row]:
    ws = openpyxl.load_workbook(path, data_only=True)["Template"]
    rows = []
    for r in range(4, 205):  # row 4 = "VD", data rows 5..204
        title = ws[f"C{r}"].value
        if not title:
            continue
        rows.append(Row(
            stt=norm_label(ws[f"A{r}"].value) or str(r - 4),
            ticker=norm_label(ws[f"B{r}"].value).upper(),
            title=norm_label(title),
            url=norm_label(ws[f"D{r}"].value),
            exp_priority=norm_label(ws[f"F{r}"].value),
            exp_impact=norm_label(ws[f"J{r}"].value),
        ))
    return rows


def events_summary(facts, ticker: str) -> str:
    """One line per extracted event of `ticker`: id [type] (cũ) description {metric=value; ...} + Jev role."""
    if facts is None:
        return ""
    mention = next((m for m in facts.ticker_mentions if m.ticker == ticker), None)
    ids = set(mention.event_ids) if mention and mention.event_ids else {e.event_id for e in facts.events}
    lines = []
    for e in facts.events:
        if e.event_id in ids:
            figs = "; ".join(f"{f.metric}={f.value:g}" for f in e.figures)
            lines.append(f"{e.event_id} [{e.event_type}]{'' if e.is_new_info else ' (cũ)'} {e.description}"
                         + (f" {{{figs}}}" if figs else ""))
    return "\n".join(lines)


def run_row(row: Row) -> Row:
    fetched = fetch(row.url, row.title)
    if fetched.text is None:
        row.error = fetched.error
        return row
    article = Article(title=row.title, url=row.url, published_at=fetched.published_at or date.today(),
                      content=fetched.text, watchlist=WATCHLIST)
    started, calls = time.perf_counter(), []
    meta = {"case": f"KB-{row.stt}", "run": row.run, "model": config.CLAUDE_MODEL}
    try:
        with tracing.run_attributes(session_id=f"KB-{row.stt}-{SESSION}", metadata=meta,
                                    tags=[f"KB-{row.stt}", "run_eval"]), llm.collect() as calls:
            results, facts = evaluate_detailed(article)
    except LLMStopError as exc:
        row.error = f"llm_stopped: {exc}"
        return row
    finally:
        row.seconds = round(time.perf_counter() - started, 2)
        row.calls = calls
    row.events = events_summary(facts, row.ticker)
    match = next((r for r in results if r.ticker == row.ticker), None)
    if match is None:
        row.pred = {"relevance": "Không liên quan", "priority": "", "impact": ""}
        return row
    row.pred = {
        "relevance": match.relevance.value,
        "priority": match.priority.value if match.priority else "",
        "impact": match.impact.value if match.impact else "",
        "event_type": match.event_type,
        "rule_ids": " ".join(match.rule_ids),
        "computed": json.dumps(match.computed, ensure_ascii=False),
        "relevance_reason": match.relevance_reason,
        "priority_reason": match.priority_reason,
        "impact_reason": match.impact_reason,
        "flags": " | ".join(match.flags),
        **{f"jev_{k}": match.scores.get(k, {}).get("answer", "") for k in ("priority", "impact", "main_event")},
        **{f"jev_{k}_p": match.scores.get(k, {}).get("p", "") for k in ("priority", "impact", "main_event")},
        "jev_impact_score": match.scores.get("impact_score", {}).get("score", ""),
        "jev_roles": "; ".join(f"{eid}={ev['role']['answer']}({ev['role']['p']:.2f})"
                               for eid, ev in match.scores.get("events", {}).items() if "role" in ev),
    }
    return row


def matrix(rows: list[Row], key: str, labels: list[str]) -> str:
    exp_key = "exp_priority" if key == "priority" else "exp_impact"
    counts = Counter((getattr(r, exp_key), r.pred.get(key) or "(trống)") for r in rows)
    cols = labels + ["(trống)"]
    lines = ["| Expected ↓ / Pipeline → | " + " | ".join(cols) + " | Tổng | Độ chính xác |",
             "|---" * (len(cols) + 3) + "|"]
    for e in labels:
        total = sum(counts[(e, c)] for c in cols)
        acc = f"{counts[(e, e)] / total:.0%}" if total else "-"
        lines.append(f"| {e} | " + " | ".join(str(counts[(e, c)]) for c in cols) + f" | {total} | {acc} |")
    return "\n".join(lines)


def rate(n: int, d: int) -> str:
    return f"{n}/{d} ({n / d:.0%})" if d else "-"


def report(all_rows: list[Row], runs: int = 1) -> str:
    rows = [r for r in all_rows if r.run == 1]
    scored = [r for r in rows if not r.error]
    real = [r for r in scored if r.stt.upper() != "VD"]
    lines = ["# Kết quả eval trên bộ test KB", "",
             f"Tổng số bài: {len(rows)} · Chấm được: {len(scored)} · Lỗi: {len(rows) - len(scored)}",
             "Thống kê dưới đây **không tính dòng VD**, theo quy ước của KB."
             + (f" Mục 1–6 là lần chạy 1; mục 7 so sánh {runs} lần chạy." if runs > 1 else ""), "",
             "## 1. Badge", "",
             "| Hạng mục | Pass |", "|---|---|",
             f"| Priority | {rate(sum(r.pri_pass for r in real), len(real))} |",
             f"| Ảnh hưởng | {rate(sum(r.imp_pass for r in real), len(real))} |",
             f"| Badge (cả hai) | {rate(sum(r.pri_pass and r.imp_pass for r in real), len(real))} |", "",
             "## 2. Ma trận Priority", "", matrix(real, "priority", PRIORITIES), "",
             "## 3. Ma trận Ảnh hưởng", "", matrix(real, "impact", IMPACTS), "",
             "## 4. Theo mã", "", "| Mã | Số bài | Priority Pass | Ảnh hưởng Pass | Badge Pass |", "|---|---|---|---|---|"]
    for t in WATCHLIST:
        rs = [r for r in real if r.ticker == t]
        if rs:
            lines.append(f"| {t} | {len(rs)} | {sum(r.pri_pass for r in rs)} | {sum(r.imp_pass for r in rs)} | "
                         f"{sum(r.pri_pass and r.imp_pass for r in rs)} |")
    lines += ["", "## 5. Các bài Fail", ""]
    for r in scored:
        if r.pri_pass and r.imp_pass:
            continue
        p = r.pred
        lines += [f"### [{r.stt}] {r.ticker} — {r.title}",
                  f"- Expected: {r.exp_priority} / {r.exp_impact} · Pipeline: {p.get('priority') or '-'} / "
                  f"{p.get('impact') or '-'} (Relevance: {p.get('relevance', '-')}, {p.get('event_type', '')})",
                  f"- Quy tắc: {p.get('rule_ids', '')}", f"- Số liệu đã tính: {p.get('computed', '')}",
                  f"- Lý giải Priority: {p.get('priority_reason', '')}",
                  f"- Lý giải Ảnh hưởng: {p.get('impact_reason', '')}",
                  f"- Cờ: {p.get('flags', '')}",
                  f"- Vai trò sự kiện (Jev): {p.get('jev_roles', '') or '-'}",
                  "- Sự kiện đã trích:", *[f"  - {line}" for line in r.events.splitlines()], ""]
    errors = [r for r in rows if r.error]
    if errors:
        lines += ["## 6. Bài lỗi (không tính điểm)", ""]
        lines += [f"- [{r.stt}] {r.ticker} {r.url} — {r.error}" for r in errors]
        lines += ["", "Bài không tải được: đặt nội dung vào `eval/cache/manual/<sha1(url)>.txt` rồi chạy lại."]
    if runs > 1:
        lines += ["", *stability(all_rows, runs)]
    lines += ["", *jev_section(real)]
    lines += ["", "## 8. Thời gian & token mỗi bài", "", "```", *timing_summary(
        [{"seconds": r.seconds, "calls": r.calls} for r in all_rows if not r.error]), "```",
              "", "Tổng:", f"```\n{json.dumps(USAGE, indent=1)}\n```"]
    return "\n".join(lines)


def jev_section(real: list[Row]) -> list[str]:
    """Jev's shadow labels vs Expected and vs the pipeline, plus accuracy by Jev probability."""
    rows = [r for r in real if r.pred.get("jev_priority")]
    if not rows:
        return ["## 9. Jev chấm song song", "", "Không có điểm Jev (DECISION_BACKEND khác `jev` hoặc Jev lỗi)."]
    lines = ["## 9. Jev chấm song song", "",
             "| | Priority | Ảnh hưởng |", "|---|---|---|"]
    exp = {"priority": lambda r: r.exp_priority, "impact": lambda r: r.exp_impact}
    cells = {}
    for k in ("priority", "impact"):
        agree = [r for r in rows if r.pred["jev_" + k] == r.pred.get(k)]
        differ = [r for r in rows if r.pred["jev_" + k] != r.pred.get(k)]
        cells[k] = [
            rate(sum(r.pred["jev_" + k] == exp[k](r) for r in rows), len(rows)),
            rate(sum(r.pred.get(k) == exp[k](r) for r in rows), len(rows)),
            rate(len(agree), len(rows)),
            rate(sum(r.pred.get(k) == exp[k](r) for r in agree), len(agree)),
            rate(sum(r.pred.get(k) == exp[k](r) for r in differ), len(differ)),
        ]
    for i, name in enumerate(["Jev đúng Expected", "Pipeline đúng Expected", "Jev trùng pipeline",
                              "Pipeline đúng khi trùng Jev", "Pipeline đúng khi khác Jev"]):
        lines.append(f"| {name} | {cells['priority'][i]} | {cells['impact'][i]} |")
    lines += ["", "Độ chính xác của Jev theo xác suất đáp án:", "",
              "| Xác suất Jev | Priority: số bài / Jev đúng | Ảnh hưởng: số bài / Jev đúng |", "|---|---|---|"]
    for lo, hi in ((0, 0.5), (0.5, 0.7), (0.7, 1.01)):
        row = []
        for k in ("priority", "impact"):
            b = [r for r in rows if r.pred.get(f"jev_{k}_p") != "" and lo <= float(r.pred[f"jev_{k}_p"]) < hi]
            row.append(f"{len(b)} / {rate(sum(r.pred['jev_' + k] == exp[k](r) for r in b), len(b))}")
        lines.append(f"| {lo:.1f}–{min(hi, 1):.1f} | {row[0]} | {row[1]} |")
    return lines


def stability(all_rows: list[Row], runs: int) -> list[str]:
    """Accuracy per run and the articles whose labels change between runs."""
    lines = [f"## 7. Độ ổn định qua {runs} lần chạy", "",
             "| Lần | Priority Pass | Ảnh hưởng Pass | Badge Pass | Thời gian TB/bài (s) |", "|---|---|---|---|---|"]
    acc = {"pri": [], "imp": [], "badge": []}
    for k in range(1, runs + 1):
        real = [r for r in all_rows if r.run == k and not r.error and r.stt.upper() != "VD"]
        if not real:
            continue
        n = len(real)
        p, i, b = (sum(r.pri_pass for r in real), sum(r.imp_pass for r in real),
                   sum(r.pri_pass and r.imp_pass for r in real))
        for key, v in (("pri", p), ("imp", i), ("badge", b)):
            acc[key].append(v / n)
        lines.append(f"| {k} | {rate(p, n)} | {rate(i, n)} | {rate(b, n)} | "
                     f"{statistics.mean(r.seconds for r in real):.1f} |")
    lines += ["", "Độ chính xác qua các lần (%): " + " · ".join(
        f"{name} {spread([100 * x for x in acc[key]], '{:.0f}')}"
        for key, name in (("pri", "Priority"), ("imp", "Ảnh hưởng"), ("badge", "Badge"))), ""]

    by_case: dict[str, list[Row]] = {}
    for r in all_rows:
        if not r.error:
            by_case.setdefault(r.stt, []).append(r)
    unstable = []
    for stt, rs in by_case.items():
        cells = []
        for key, exp in (("event_type", None), ("priority", rs[0].exp_priority), ("impact", rs[0].exp_impact)):
            vals = [r.pred.get(key, "") for r in rs]
            dist, share = agreement(vals)
            if share < 1:
                hit = f", khớp Expected {sum(v == exp for v in vals)}/{len(vals)}" if exp else ""
                cells.append(f"{key}: {dist}{hit}")
        if cells:
            unstable.append(f"- [{stt}] {rs[0].ticker} {rs[0].title[:70]} — " + "; ".join(cells))
    stable = len(by_case) - len(unstable)
    lines += [f"Bài cho cùng nhãn ở mọi lần: {stable}/{len(by_case)}", ""]
    if unstable:
        lines += ["Bài có nhãn thay đổi giữa các lần:", "", *unstable]
    return lines


def write_csv(rows: list[Row]) -> None:
    cols = ["Lần", "STT", "Mã", "Title", "Priority (pipeline)", "Ảnh hưởng (pipeline)", "Priority Expected",
            "Ảnh hưởng Expected", "Kết quả Priority", "Kết quả Ảnh hưởng", "Relevance", "Loại sự kiện",
            "Mã quy tắc", "Lý giải Relevance", "Lý giải Priority", "Lý giải Ảnh hưởng", "Cờ", "Lỗi",
            "Thời gian (s)", "Claude gọi", "Input", "Cache đọc", "Cache ghi", "Output", "Jev gọi", "Jev input",
            "Jev Priority", "Jev Priority p", "Jev Ảnh hưởng", "Jev Ảnh hưởng p", "Jev sự kiện trọng tâm",
            "Jev mức tác động", "Sự kiện đã trích", "Jev vai trò sự kiện"]
    with open(OUT / "results.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            p, t, j = r.pred, sum_tokens(r.calls), sum_tokens(r.calls, "jev")
            n_jev = sum(c.get("provider") == "jev" for c in r.calls)
            w.writerow([r.run, r.stt, r.ticker, r.title, p.get("priority", ""), p.get("impact", ""), r.exp_priority,
                        r.exp_impact, "" if r.error else ("Pass" if r.pri_pass else "Fail"),
                        "" if r.error else ("Pass" if r.imp_pass else "Fail"), p.get("relevance", ""),
                        p.get("event_type", ""), p.get("rule_ids", ""), p.get("relevance_reason", ""),
                        p.get("priority_reason", ""), p.get("impact_reason", ""), p.get("flags", ""), r.error,
                        r.seconds, len(r.calls) - n_jev, t["input_tokens"], t["cache_read_input_tokens"],
                        t["cache_creation_input_tokens"], t["output_tokens"], n_jev, j["input_tokens"],
                        p.get("jev_priority", ""), p.get("jev_priority_p", ""), p.get("jev_impact", ""),
                        p.get("jev_impact_p", ""), p.get("jev_main_event", ""), p.get("jev_impact_score", ""),
                        r.events, p.get("jev_roles", "")])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--fetch-only", action="store_true", help="chỉ tải bài vào cache, không gọi Claude")
    ap.add_argument("--repeat", type=int, default=1, help="chạy cả bộ N lần để đo độ ổn định")
    ap.add_argument("--phoenix", action="store_true", help="gửi trace sang Phoenix (cần `uv run phoenix serve`)")
    args = ap.parse_args(argv)
    if args.repeat < 1:
        ap.error("--repeat phải ≥ 1")

    rows = read_kb(args.xlsx)
    if args.limit:
        rows = rows[: args.limit]
    OUT.mkdir(parents=True, exist_ok=True)

    if args.fetch_only:
        for r in rows:
            f = fetch(r.url, r.title)
            print(f"[{r.stt}] {'OK ' if f.text else 'ERR'} {r.ticker} {r.url} {f.error}")
        return 0

    if args.phoenix and (why := tracing.setup()):  # before the Anthropic client exists
        print(f"Phoenix tắt: {why}", file=sys.stderr)
    try:
        llm.client()  # fail fast: credentials + model availability
    except (TypeError, RuntimeError, anthropic.AuthenticationError) as exc:
        print(f"Không gọi được Claude: {exc}\n"
              "Đặt ANTHROPIC_API_KEY (hoặc đăng nhập `ant auth login`) rồi chạy lại.", file=sys.stderr)
        return 2

    all_rows: list[Row] = []
    for k in range(1, args.repeat + 1):
        started = time.perf_counter()
        batch = [replace(r, run=k, pred={}, error="", calls=[]) for r in rows]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            batch = list(pool.map(run_row, batch))
        all_rows += batch
        done = [r for r in batch if not r.error and r.stt.upper() != "VD"]
        print(f"Lần {k}/{args.repeat}: {time.perf_counter() - started:.0f}s · Badge "
              f"{rate(sum(r.pri_pass and r.imp_pass for r in done), len(done))}")
    write_csv(all_rows)
    tracing.flush()
    text = report(all_rows, args.repeat)
    (OUT / "report.md").write_text(text, encoding="utf-8")
    print(text.split("## 2.")[0])
    print(f"Chi tiết: {OUT / 'report.md'}, {OUT / 'results.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
