from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from config import InvestmentHorizon


SentimentValue = Literal["bullish", "bearish", "neutral"]
RecommendationAction = Literal["KUPI", "PRODAJ", "PRODAJ / DJELOMIČNA PRODAJA", "ZADRŽI", "ZADRŽI DUGOROČNO"]


@dataclass(frozen=True)
class MarketQuote:
    ticker: str
    last_price: float
    change_pct: float
    turnover_eur: float


@dataclass(frozen=True)
class TechnicalAnalysis:
    rsi: float
    ma50: float
    trend: Literal["uptrend", "downtrend", "sideways"]
    status: str


@dataclass(frozen=True)
class SentimentResult:
    sentiment: SentimentValue
    summary: str


@dataclass(frozen=True)
class Recommendation:
    action: RecommendationAction
    reason: str
    urgent: bool


@dataclass(frozen=True)
class PortfolioAnalysis:
    ticker: str
    quantity: int
    average_buy_price: float
    target_price: float
    stop_loss: float
    investment_horizon: InvestmentHorizon
    horizon_reason: str
    quote: MarketQuote | None
    technical: TechnicalAnalysis
    sentiment: SentimentResult
    recommendation: Recommendation
    pnl_eur: float | None
    pnl_pct: float | None
    wow_event: bool
    checked_at: datetime
