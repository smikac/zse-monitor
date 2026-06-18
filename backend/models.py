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
    volume: float = 0.0
    vwap_price: float = 0.0
    market_segment: str = ""
    isin: str = ""
    is_traded: bool = False


@dataclass(frozen=True)
class DividendInfo:
    ticker: str
    amount_per_share: float
    currency: str
    ex_date: str
    record_date: str
    payment_date: str
    status: str


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
class AnnualForecast:
    direction: Literal["RAST", "PAD", "NEUTRALNO"]
    confidence: float
    summary: str
    drivers: list[str]


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
    has_dividend: bool
    dividend_per_share: float | None
    dividend_currency: str | None
    dividend_ex_date: str | None
    dividend_payment_date: str | None
    dividend_status: str | None
    dividend_yield_pct: float | None
    annual_forecast: AnnualForecast
    pnl_eur: float | None
    pnl_pct: float | None
    wow_event: bool
    checked_at: datetime


@dataclass(frozen=True)
class MarketOpportunity:
    ticker: str
    quote: MarketQuote
    technical: TechnicalAnalysis
    action: Literal["KUPI", "PRATI", "IZBJEGNI"]
    reason: str
    score: float
    has_dividend: bool
    dividend_per_share: float | None
    dividend_currency: str | None
    dividend_ex_date: str | None
    dividend_payment_date: str | None
    dividend_status: str | None
    dividend_yield_pct: float | None
    annual_forecast: AnnualForecast


@dataclass(frozen=True)
class ForumSignal:
    ticker: str
    action: Literal["KUPI", "PRODAJ", "PRATI"]
    summary: str
    source_url: str
    confidence: float
