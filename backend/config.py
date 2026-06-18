from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Literal, TypedDict


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


EXAMPLE_PORTFOLIO: list[PortfolioPosition] = [
    {
        "ticker": "KODT",
        "kolicina": 1,
        "prosjecna_kupovna_cijena": 1000.0,
        "target_price": 1200.0,
        "stop_loss": 900.0,
        "investment_horizon": "long_term",
    }
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


def get_portfolio() -> list[PortfolioPosition]:
    raw_portfolio = os.getenv("PORTFOLIO_JSON", "").strip()
    if not raw_portfolio:
        return EXAMPLE_PORTFOLIO

    parsed = json.loads(raw_portfolio)
    if not isinstance(parsed, list):
        raise ValueError("PORTFOLIO_JSON must be a JSON array.")

    portfolio: list[PortfolioPosition] = []
    for item in parsed:
        if not isinstance(item, dict):
            raise ValueError("Each PORTFOLIO_JSON item must be an object.")
        portfolio.append(_validate_position(item))
    return portfolio


def _validate_position(item: dict) -> PortfolioPosition:
    horizon = item.get("investment_horizon")
    if horizon not in {"short_term", "long_term"}:
        raise ValueError("investment_horizon must be 'short_term' or 'long_term'.")

    return {
        "ticker": str(item["ticker"]).upper().strip(),
        "kolicina": int(item["kolicina"]),
        "prosjecna_kupovna_cijena": float(item["prosjecna_kupovna_cijena"]),
        "target_price": float(item["target_price"]),
        "stop_loss": float(item["stop_loss"]),
        "investment_horizon": horizon,
    }
