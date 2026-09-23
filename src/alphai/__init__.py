"""alphai — Python SDK for the AlphAI financial-news REST API.

Quickstart::

    from alphai import Client

    with Client(api_key="ak_live_…") as client:   # or $ALPHAI_API_KEY
        for article in client.news.iter(symbol="NVDA", max_items=20):
            print(article.title, article.relevance_score)
"""

from __future__ import annotations

from ._config import API_KEY_ENV_VAR, DEFAULT_BASE_URL, ClientConfig
from ._core import RateLimit
from ._snapshot_params import TickersArg
from ._version import __version__
from .async_client import AsyncClient, AsyncNewsResource, AsyncSymbolsResource
from .client import Client, NewsResource, SymbolsResource
from .errors import (
    AlphaAIError,
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
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
    NewsSearchPage,
    NewsSearchQueryInfo,
    NewsTradingValue,
    OriginalArticle,
    Quote,
    RichNewsArticle,
    SearchMatch,
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
from .models.brief import (
    BriefEarningsDate,
    BriefEvent,
    BriefSignal,
    NewsBrief,
)
from .models.radar import (
    RadarAccess,
    RadarCalculationParams,
    RadarCollection,
    RadarEvidence,
    RadarFreshness,
    RadarMarket,
    RadarOrder,
    RadarReading,
    RadarScope,
    RadarSentiment,
    RadarSentimentFilter,
    RadarSnapshot,
    RadarSort,
    RadarSummary,
    RadarTier,
    RadarWatchlistCoverage,
    RadarWindow,
)
from .radar import AsyncRadarResource, RadarResource

__all__ = [
    "TickersArg",
    "RadarResource",
    "AsyncRadarResource",
    "RadarWindow",
    "RadarScope",
    "RadarTier",
    "RadarMarket",
    "RadarSort",
    "RadarOrder",
    "RadarSentimentFilter",
    "RadarCollection",
    "RadarSentiment",
    "RadarCalculationParams",
    "RadarAccess",
    "RadarEvidence",
    "RadarReading",
    "RadarSummary",
    "RadarFreshness",
    "RadarWatchlistCoverage",
    "RadarSnapshot",
    "BriefSignal",
    "BriefEvent",
    "BriefEarningsDate",
    "NewsBrief",
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
    "ConflictError",
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
    "NewsSearchPage",
    "NewsSearchQueryInfo",
    "SearchMatch",
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
