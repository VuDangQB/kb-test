from .schemas import Article, Impact, Priority, Relevance, TickerResult


def evaluate(article: Article) -> list[TickerResult]:
    from .graph import evaluate as _evaluate  # lazy: keeps imports light for tests/tools
    return _evaluate(article)


__all__ = ["Article", "Impact", "Priority", "Relevance", "TickerResult", "evaluate"]
