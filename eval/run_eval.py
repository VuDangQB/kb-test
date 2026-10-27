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
from datetime import date
from pathlib import Path

import anthropic
import openpyxl

from eval.fetch import fetch
from eval.runstats import agreement, spread, sum_tokens, timing_summary
from pipeline import Article, config, evaluate, tracing
from pipeline import llm
from pipeline.llm import USAGE, LLMStopError

OUT = Path(__file__).resolve().parent / "out"
PRIORITIES = ["Cao", "Trung bình", "Thấp"]
IMPACTS = ["Tích cực", "Tiêu cực", "Trung lập"]
WATCHLIST = ["NVL", "MSN", "FPT", "HPG", "MWG"]


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


def run_row(row: Row) -> Row:
    fetched = fetch(row.url, row.title)
    if fetched.text is None:
        row.error = fetched.error
        return row
    article = Article(title=row.title, url=row.url, published_at=fetched.published_at or date.today(),
                      content=fetched.text, watchlist=WATCHLIST)
    started = time.perf_counter()
    meta = {"case": f"KB-{row.stt}", "run": row.run, "model": config.CLAUDE_MODEL}
    try:
        with tracing.run_attributes(session_id=f"KB-{row.stt}-{SESSION}", metadata=meta,
                                    tags=[f"KB-{row.stt}", "run_eval"]), llm.collect() as calls:
            results = evaluate(article)
    except LLMStopError as exc:
        row.error = f"llm_stopped: {exc}"
        return row
    finally:
        row.seconds = round(time.perf_counter() - started, 2)
        row.calls = calls
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


def report(rows: list[Row]) -> str:
    scored = [r for r in rows if not r.error]
    real = [r for r in scored if r.stt.upper() != "VD"]
    lines = ["# Kết quả eval trên bộ test KB", "",
             f"Tổng số bài: {len(rows)} · Chấm được: {len(scored)} · Lỗi: {len(rows) - len(scored)}",
             "Thống kê dưới đây **không tính dòng VD**, theo quy ước của KB.", "",
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
                  f"- Cờ: {p.get('flags', '')}", ""]
    errors = [r for r in rows if r.error]
    if errors:
        lines += ["## 6. Bài lỗi (không tính điểm)", ""]
        lines += [f"- [{r.stt}] {r.ticker} {r.url} — {r.error}" for r in errors]
        lines += ["", "Bài không tải được: đặt nội dung vào `eval/cache/manual/<sha1(url)>.txt` rồi chạy lại."]
    lines += ["", "## 7. Chi phí", "", f"```\n{json.dumps(USAGE, indent=1)}\n```"]
    return "\n".join(lines)


def write_csv(rows: list[Row]) -> None:
    cols = ["STT", "Mã", "Title", "Priority (pipeline)", "Ảnh hưởng (pipeline)", "Priority Expected",
            "Ảnh hưởng Expected", "Kết quả Priority", "Kết quả Ảnh hưởng", "Relevance", "Loại sự kiện",
            "Mã quy tắc", "Lý giải Relevance", "Lý giải Priority", "Lý giải Ảnh hưởng", "Cờ", "Lỗi"]
    with open(OUT / "results.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            p = r.pred
            w.writerow([r.stt, r.ticker, r.title, p.get("priority", ""), p.get("impact", ""), r.exp_priority,
                        r.exp_impact, "" if r.error else ("Pass" if r.pri_pass else "Fail"),
                        "" if r.error else ("Pass" if r.imp_pass else "Fail"), p.get("relevance", ""),
                        p.get("event_type", ""), p.get("rule_ids", ""), p.get("relevance_reason", ""),
                        p.get("priority_reason", ""), p.get("impact_reason", ""), p.get("flags", ""), r.error])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--fetch-only", action="store_true", help="chỉ tải bài vào cache, không gọi Claude")
    args = ap.parse_args(argv)

    rows = read_kb(args.xlsx)
    if args.limit:
        rows = rows[: args.limit]
    OUT.mkdir(parents=True, exist_ok=True)

    if args.fetch_only:
        for r in rows:
            f = fetch(r.url, r.title)
            print(f"[{r.stt}] {'OK ' if f.text else 'ERR'} {r.ticker} {r.url} {f.error}")
        return 0

    try:
        llm.client()  # fail fast: credentials + model availability
    except (TypeError, RuntimeError, anthropic.AuthenticationError) as exc:
        print(f"Không gọi được Claude: {exc}\n"
              "Đặt ANTHROPIC_API_KEY (hoặc đăng nhập `ant auth login`) rồi chạy lại.", file=sys.stderr)
        return 2

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(run_row, rows))
    write_csv(rows)
    text = report(rows)
    (OUT / "report.md").write_text(text, encoding="utf-8")
    print(text.split("## 2.")[0])
    print(f"Chi tiết: {OUT / 'report.md'}, {OUT / 'results.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
