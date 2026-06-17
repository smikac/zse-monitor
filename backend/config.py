from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final, Literal, TypedDict


InvestmentHorizon = Literal["short_term", "long_term"]


class PortfolioPosition(TypedDict):
    ticker: str
    kolicina: int
    prosjecna_kupovna_cijena: float
    target_price: float
    stop_loss: float
    investment_horizon: InvestmentHorizon


@dataclass(frozen=True)
class AppSettings:
    telegram_token: str
    telegram_chat_id: str
    openai_api_key: str
    wow_turnover_threshold_eur: float = 40_000.0
    wow_price_change_threshold_pct: float = 4.0
    request_timeout_seconds: int = 20


PORTFOLIO: Final[list[PortfolioPosition]] = [
    {
        "ticker": "KODT",
        "kolicina": 10,
        "prosjecna_kupovna_cijena": 1550.0,
        "target_price": 1900.0,
        "stop_loss": 1350.0,
        "investment_horizon": "long_term",
    },
    {
        "ticker": "SPAN",
        "kolicina": 35,
        "prosjecna_kupovna_cijena": 48.0,
        "target_price": 62.0,
        "stop_loss": 41.0,
        "investment_horizon": "short_term",
    },
    {
        "ticker": "HT",
        "kolicina": 120,
        "prosjecna_kupovna_cijena": 27.5,
        "target_price": 34.0,
        "stop_loss": 23.5,
        "investment_horizon": "long_term",
    },
]


def get_settings() -> AppSettings:
    return AppSettings(
        telegram_token=os.getenv("TELEGRAM_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        wow_turnover_threshold_eur=float(os.getenv("WOW_TURNOVER_THRESHOLD_EUR", "40000")),
        wow_price_change_threshold_pct=float(os.getenv("WOW_PRICE_CHANGE_THRESHOLD_PCT", "4")),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")),
    )
