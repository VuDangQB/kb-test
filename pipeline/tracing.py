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
        return "thiếu gói Phoenix: chạy `uv sync`"

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


@contextmanager
def under_current_node():
    """Parent the next spans (the Claude call) on the running LangGraph node's span.

    The LangChain instrumentor records node spans but does not make them the current
    OpenTelemetry context, so without this every LLM span would start its own trace.
    """
    if _provider is None:
        yield
        return
    from openinference.instrumentation.langchain import get_current_span
    from opentelemetry import trace
    if (span := get_current_span()) is None:
        yield
        return
    with trace.use_span(span, end_on_exit=False):
        yield


@contextmanager
def llm_span(name: str, provider: str, model: str, input_value: str):
    """Manual OpenInference LLM span for calls no instrumentor covers (Jev). Yields a setter for results."""
    def set_result(output_value: str, prompt_tokens: int, completion_tokens: int, model_name: str = "") -> None:
        if span is None:
            return
        span.set_attribute("output.value", output_value)
        span.set_attribute("output.mime_type", "application/json")
        span.set_attribute("llm.model_name", model_name or model)
        span.set_attribute("llm.token_count.prompt", prompt_tokens)
        span.set_attribute("llm.token_count.completion", completion_tokens)
        span.set_attribute("llm.token_count.total", prompt_tokens + completion_tokens)

    if _provider is None:
        span = None
        yield set_result
        return
    from opentelemetry import trace
    with under_current_node(), trace.get_tracer("pipeline").start_as_current_span(name) as span:
        span.set_attribute("openinference.span.kind", "LLM")
        span.set_attribute("llm.provider", provider)
        span.set_attribute("llm.model_name", model)
        span.set_attribute("input.value", input_value)
        yield set_result
