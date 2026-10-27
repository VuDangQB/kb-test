"""Timing, token and run-to-run consistency helpers shared by run_one and run_eval."""

import statistics
from collections import Counter

TOKEN_KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens")


def sum_tokens(calls: list[dict]) -> dict:
    return {k: sum(c[k] for c in calls) for k in TOKEN_KEYS}


def by_stage(calls: list[dict]) -> dict[str, tuple[int, float]]:
    out: dict[str, tuple[int, float]] = {}
    for c in calls:
        n, s = out.get(c["stage"], (0, 0.0))
        out[c["stage"]] = (n + 1, s + c["seconds"])
    return out


def fmt_run(seconds: float, calls: list[dict]) -> str:
    stages = ", ".join(f"{st} {n}×{s:.1f}s" if n > 1 else f"{st} {s:.1f}s" for st, (n, s) in by_stage(calls).items())
    t = sum_tokens(calls)
    return (f"{seconds:.1f}s ({stages}) · {len(calls)} lần gọi · input {t['input_tokens']:,} "
            f"+ cache đọc {t['cache_read_input_tokens']:,} / ghi {t['cache_creation_input_tokens']:,} "
            f"· output {t['output_tokens']:,}")


def spread(values: list[float], fmt: str = "{:.1f}") -> str:
    if not values:
        return "-"
    if len(values) == 1:
        return fmt.format(values[0])
    f = fmt.format
    return (f"TB {f(statistics.mean(values))} · min {f(min(values))} · max {f(max(values))} "
            f"· độ lệch chuẩn {f(statistics.stdev(values))}")


def agreement(values: list[str]) -> tuple[str, float]:
    """Distribution like 'A24×4, A23×1' and the share of the most common value."""
    counts = Counter(v or "—" for v in values)
    dist = ", ".join(f"{v}×{n}" for v, n in counts.most_common())
    return dist, counts.most_common(1)[0][1] / len(values)


def timing_summary(runs: list[dict]) -> list[str]:
    """Lines describing time and tokens across runs; each run has 'seconds' and 'calls'."""
    ok = [r for r in runs if not r.get("error")]
    if not ok:
        return []
    lines = [f"Thời gian mỗi lần (s): {spread([r['seconds'] for r in ok])}"]
    stages = sorted({c["stage"] for r in ok for c in r["calls"]})
    for st in stages:
        per_run = [sum(c["seconds"] for c in r["calls"] if c["stage"] == st) for r in ok]
        lines.append(f"  {st:<9}: {spread(per_run)}")
    for k, label in zip(TOKEN_KEYS, ("input", "cache đọc", "cache ghi", "output")):
        lines.append(f"Token {label:<9}: {spread([sum_tokens(r['calls'])[k] for r in ok], "{:,.0f}")}")
    return lines
