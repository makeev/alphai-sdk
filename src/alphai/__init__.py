"""alphai — Python SDK for the AlphaAI financial-news REST API.

Quickstart::

    from alphai import Client

    with Client(api_key="ak_live_…") as client:   # or $ALPHAI_API_KEY
        for article in client.news.iter(symbol="NVDA", max_items=20):
            print(article.title, article.relevance_score)
"""

from __future__ import annotations

from ._config import API_KEY_ENV_VAR, DEFAULT_BASE_URL, ClientConfig
from ._core import RateLimit
from ._version import __version__
from .async_client import AsyncClient, AsyncNewsResource, AsyncSymbolsResource
from .client import Client, NewsResource, SymbolsResource
from .errors import (
    AlphaAIError,
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    InvalidResponseError,
    MissingAPIKeyError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
)
from .models import (
    Actionability,
    AITradingInsights,
    AlternativePerspectives,
    Confidence,
    DailySentimentBucket,
    EarningsRead,
    EarningsReport,
    EnrichedArticle,
    Guidance,
    ImpactAnalysis,
    IndirectMarketEffects,
    InsiderEvent,
    KeyEntity,
    KeyMetric,
    LatestEarningsPointer,
    NewsCategory,
    NewsContextEnhancement,
    NewsPage,
    NewsPagination,
    NewsTradingValue,
    OriginalArticle,
    Quote,
    RichNewsArticle,
    Segment,
    Sentiment,
    Symbol,
    TickerAnalysis,
    TickerEarningsHistory,
    TickerInsiderSummary,
    TickerSentimentSummary,
    Topic,
    TopInsider,
    VsPriorGuidance,
)

__all__ = [
    "__version__",
    # clients
    "Client",
    "AsyncClient",
    "NewsResource",
    "SymbolsResource",
    "AsyncNewsResource",
    "AsyncSymbolsResource",
    # config / misc
    "ClientConfig",
    "RateLimit",
    "DEFAULT_BASE_URL",
    "API_KEY_ENV_VAR",
    # errors
    "AlphaAIError",
    "MissingAPIKeyError",
    "InvalidResponseError",
    "APIConnectionError",
    "APIStatusError",
    "BadRequestError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    # enums
    "NewsCategory",
    "Sentiment",
    "Confidence",
    "Actionability",
    # news models
    "Topic",
    "ImpactAnalysis",
    "TickerAnalysis",
    "NewsTradingValue",
    "IndirectMarketEffects",
    "AlternativePerspectives",
    "KeyEntity",
    "AITradingInsights",
    "NewsContextEnhancement",
    "OriginalArticle",
    "EnrichedArticle",
    "InsiderEvent",
    "RichNewsArticle",
    "NewsPagination",
    "NewsPage",
    # symbol models
    "Symbol",
    "DailySentimentBucket",
    "TickerSentimentSummary",
    "TopInsider",
    "TickerInsiderSummary",
    # earnings models
    "EarningsReport",
    "EarningsRead",
    "TickerEarningsHistory",
    "LatestEarningsPointer",
    "KeyMetric",
    "Segment",
    "Guidance",
    "VsPriorGuidance",
    "Quote",
]
