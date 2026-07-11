"""Pydantic v2 response models for the AlphaAI API."""

from __future__ import annotations

from .enums import (
    Actionability,
    ActionabilityLike,
    CategoryLike,
    Confidence,
    ConfidenceLike,
    NewsCategory,
    Sentiment,
    SentimentLike,
)
from .news import (
    AITradingInsights,
    AlternativePerspectives,
    EnrichedArticle,
    ImpactAnalysis,
    IndirectMarketEffects,
    InsiderEvent,
    KeyEntity,
    NewsContextEnhancement,
    NewsPagination,
    NewsTradingValue,
    OriginalArticle,
    RichNewsArticle,
    TickerAnalysis,
    Topic,
)
from .symbols import (
    DailySentimentBucket,
    Symbol,
    TickerInsiderSummary,
    TickerSentimentSummary,
    TopInsider,
)

# Friendlier alias for the news page returned by list/insider endpoints.
NewsPage = NewsPagination

__all__ = [
    "AITradingInsights",
    "Actionability",
    "ActionabilityLike",
    "AlternativePerspectives",
    "CategoryLike",
    "Confidence",
    "ConfidenceLike",
    "DailySentimentBucket",
    "EnrichedArticle",
    "ImpactAnalysis",
    "IndirectMarketEffects",
    "KeyEntity",
    "NewsCategory",
    "NewsContextEnhancement",
    "NewsPage",
    "NewsPagination",
    "NewsTradingValue",
    "OriginalArticle",
    "InsiderEvent",
    "RichNewsArticle",
    "Sentiment",
    "SentimentLike",
    "Symbol",
    "TickerAnalysis",
    "TickerInsiderSummary",
    "TickerSentimentSummary",
    "TopInsider",
    "Topic",
]
