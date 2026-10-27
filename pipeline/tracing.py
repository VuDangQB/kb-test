"""Optional Arize Phoenix tracing (OpenInference). Off unless `setup()` is called.

Spans: one trace per `evaluate()` (LangGraph nodes via the LangChain instrumentor),
with one LLM span per Claude call (model, prompt/completion/cache tokens, latency).
Call `setup()` before the first Anthropic client is created: it turns off the SDK's own
OpenTelemetry spans, which would otherwise duplicate every LLM span and double the token totals.

    uv run phoenix serve            # UI + collector at http://localhost:6006
    PHOENIX_COLLECTOR_ENDPOINT=...  # optional, defaults to http://localhost:6006
"""

import atexit
import os
from contextlib import contextmanager

DEFAULT_ENDPOINT = "http://localhost:6006"
_provider = None


def setup(project: str | None = None) -> str:
    """Start exporting spans to Phoenix. Returns "" on success, otherwise why tracing stays off."""
    global _provider
    if _provider is not None:
        return ""
    try:
        import httpx
        from openinference.instrumentation.anthropic import AnthropicInstrumentor
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from phoenix.otel import register
    except ImportError:
        return "thiếu gói Phoenix: chạy `uv sync --group phoenix`"

    os.environ.setdefault("ANTHROPIC_OPEN_TELEMETRY", "false")  # keep only the OpenInference LLM span
    base = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", DEFAULT_ENDPOINT).rstrip("/")
    try:
        httpx.get(base, timeout=2)
    except httpx.HTTPError:
        return f"không kết nối được Phoenix tại {base}: chạy `uv run phoenix serve` ở terminal khác"

    _provider = register(project_name=project or os.environ.get("PHOENIX_PROJECT_NAME", "kb-news-eval"),
                         endpoint=f"{base}/v1/traces", batch=True, verbose=False)
    AnthropicInstrumentor().instrument(tracer_provider=_provider)
    LangChainInstrumentor().instrument(tracer_provider=_provider)
    atexit.register(flush)
    return ""


def enabled() -> bool:
    return _provider is not None


def flush() -> None:
    if _provider is not None:
        _provider.force_flush()


@contextmanager
def run_attributes(session_id: str, metadata: dict, tags: list[str]):
    """Tag every span of one run, so Phoenix can group repeats of the same article (Sessions tab)."""
    if _provider is None:
        yield
        return
    from openinference.instrumentation import using_attributes
    with using_attributes(session_id=session_id, metadata=metadata, tags=tags):
        yield
