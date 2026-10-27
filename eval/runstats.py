"""Timing, token and run-to-run consistency helpers shared by run_one and run_eval."""

import statistics
from collections import Counter

TOKEN_KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens")


def sum_tokens(calls: list[dict], provider: str = "claude") -> dict:
    return {k: sum(c[k] for c in calls if c.get("provider", "claude") == provider) for k in TOKEN_KEYS}


def stage_name(c: dict) -> str:
    return c["stage"] if c.get("provider", "claude") == "claude" else f"{c['stage']}({c['provider']})"


def by_stage(calls: list[dict]) -> dict[str, tuple[int, float]]:
    out: dict[str, tuple[int, float]] = {}
    for c in calls:
        n, s = out.get(stage_name(c), (0, 0.0))
        out[stage_name(c)] = (n + 1, s + c["seconds"])
    return out


def fmt_run(seconds: float, calls: list[dict]) -> str:
    stages = ", ".join(f"{st} {n}×{s:.1f}s" if n > 1 else f"{st} {s:.1f}s" for st, (n, s) in by_stage(calls).items())
    t, n_claude = sum_tokens(calls), sum(c.get("provider", "claude") == "claude" for c in calls)
    line = (f"{seconds:.1f}s ({stages}) · Claude {n_claude} lần gọi · input {t['input_tokens']:,} "
            f"+ cache đọc {t['cache_read_input_tokens']:,} / ghi {t['cache_creation_input_tokens']:,} "
            f"· output {t['output_tokens']:,}")
    if n_jev := sum(c.get("provider") == "jev" for c in calls):
        j = sum_tokens(calls, "jev")
        line += f" · Jev {n_jev} lần gọi · input {j['input_tokens']:,} / output {j['output_tokens']:,}"
    return line


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
    stages = sorted({stage_name(c) for r in ok for c in r["calls"]})
    for st in stages:
        per_run = [sum(c["seconds"] for c in r["calls"] if stage_name(c) == st) for r in ok]
        lines.append(f"  {st:<15}: {spread(per_run)}")
    for k, label in zip(TOKEN_KEYS, ("input", "cache đọc", "cache ghi", "output")):
        lines.append(f"Token Claude {label:<9}: {spread([sum_tokens(r['calls'])[k] for r in ok], '{:,.0f}')}")
    if any(c.get("provider") == "jev" for r in ok for c in r["calls"]):
        for k, label in (("input_tokens", "input"), ("output_tokens", "output")):
            lines.append(f"Token Jev {label:<12}: {spread([sum_tokens(r['calls'], 'jev')[k] for r in ok], '{:,.0f}')}")
    return lines
