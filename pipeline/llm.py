"""Thin wrapper over the official Anthropic SDK: structured output + cached system prompt."""

import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from . import config, tracing

T = TypeVar("T", bound=BaseModel)

USAGE = {"calls": 0, "input_tokens": 0, "output_tokens": 0,
         "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
# One record per call, in call order: stage, seconds, token counts. Callers slice it per run.
CALLS: list[dict] = []
_usage_lock = threading.Lock()
_collector: ContextVar[list[dict] | None] = ContextVar("llm_calls", default=None)


def record(stage: str, seconds: float, provider: str, *, input_tokens: int = 0, output_tokens: int = 0,
           cache_read_input_tokens: int = 0, cache_creation_input_tokens: int = 0) -> None:
    """Log one model call (Claude or Jev) for timing/token reports."""
    entry = {"stage": stage, "provider": provider, "seconds": round(seconds, 2), "input_tokens": input_tokens,
             "output_tokens": output_tokens, "cache_read_input_tokens": cache_read_input_tokens,
             "cache_creation_input_tokens": cache_creation_input_tokens}
    with _usage_lock:
        CALLS.append(entry)
        if (calls := _collector.get()) is not None:
            calls.append(entry)


@contextmanager
def collect():
    """Collect the call records made inside this block (LangGraph worker threads copy the context)."""
    calls: list[dict] = []
    token = _collector.set(calls)
    try:
        yield calls
    finally:
        _collector.reset(token)


class LLMStopError(RuntimeError):
    """Claude stopped without a usable answer (refusal, max_tokens, context exceeded)."""

    def __init__(self, stop_reason: str, category: str | None = None):
        self.stop_reason, self.category = stop_reason, category
        super().__init__(f"stop_reason={stop_reason}" + (f" category={category}" if category else ""))


@lru_cache
def client() -> anthropic.Anthropic:
    c = anthropic.Anthropic(max_retries=3)
    _check_model(c)
    return c


def _check_model(c: anthropic.Anthropic) -> None:
    try:
        c.models.retrieve(config.CLAUDE_MODEL)
    except anthropic.NotFoundError as exc:
        available = ", ".join(m.id for m in c.models.list())
        raise RuntimeError(
            f"Model '{config.CLAUDE_MODEL}' không khả dụng với API key này. Model hiện có: {available}") from exc


def _thinking(effort: str) -> dict:
    if config.THINKING == "between_tools" and effort in ("low", "medium", "high"):
        return {"type": "between_tools"}
    return {"type": "adaptive"}


def parse(system_blocks: list[str], user: str, schema: type[T], *, effort: str,
          max_tokens: int = config.MAX_TOKENS, stage: str = "llm") -> T:
    """One structured-output call. Stable system blocks first; the last one carries the cache breakpoint."""
    system = [{"type": "text", "text": text} for text in system_blocks]
    system[-1]["cache_control"] = {"type": "ephemeral"}
    started = time.perf_counter()
    with tracing.under_current_node():
        resp = client().messages.parse(
            model=config.CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
            thinking=_thinking(effort),
            output_config={"effort": effort},
        )
    tokens = {key: getattr(resp.usage, key, 0) or 0 for key in
              ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}
    with _usage_lock:
        USAGE["calls"] += 1
        for key, n in tokens.items():
            USAGE[key] += n
    record(stage, time.perf_counter() - started, "claude", **tokens)

    if resp.stop_reason in ("refusal", "max_tokens", "model_context_window_exceeded"):
        category = getattr(resp.stop_details, "category", None) if resp.stop_details else None
        raise LLMStopError(resp.stop_reason, category)
    if resp.parsed_output is None:
        raise LLMStopError("no_parsed_output")
    return resp.parsed_output
