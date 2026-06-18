from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Literal, TypedDict


InvestmentHorizon = Literal["short_term", "long_term"]


class PortfolioPosition(TypedDict, total=False):
    ticker: str
    kolicina: int
    prosjecna_kupovna_cijena: float
    target_price: float
    stop_loss: float
    investment_horizon: InvestmentHorizon
    broker_current_price: float
    broker_acquisition_value: float
    broker_market_value: float
    broker_profit_eur: float
    broker_return_pct: float
    portfolio_weight_pct: float


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


def get_expert_posts() -> list[dict[str, str]]:
    raw_posts = os.getenv("EXPERT_POSTS_JSON", "").strip()
    if not raw_posts:
        return []

    parsed = json.loads(raw_posts)
    if not isinstance(parsed, list):
        raise ValueError("EXPERT_POSTS_JSON must be a JSON array.")

    posts: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        posts.append(
            {
                "title": str(item.get("title", "Expert commentary")).strip(),
                "text": text[:1800],
                "url": str(item.get("url", "")).strip(),
                "source": str(item.get("source", "expert")).strip(),
            }
        )
    return posts


def get_expert_feed_urls() -> list[str]:
    raw_urls = os.getenv("EXPERT_FEED_URLS", "").strip()
    if not raw_urls:
        return []
    return [url.strip() for url in raw_urls.replace("\n", ",").split(",") if url.strip()]


def _validate_position(item: dict) -> PortfolioPosition:
    horizon = item.get("investment_horizon")
    if horizon is not None and horizon not in {"short_term", "long_term"}:
        raise ValueError("investment_horizon must be 'short_term' or 'long_term'.")

    average_buy_price = float(item["prosjecna_kupovna_cijena"])
    broker_current_price = _optional_float(item, "broker_current_price")
    position: PortfolioPosition = {
        "ticker": str(item["ticker"]).upper().strip(),
        "kolicina": int(item["kolicina"]),
        "prosjecna_kupovna_cijena": average_buy_price,
        "target_price": _optional_float(item, "target_price") or _default_target_price(average_buy_price, broker_current_price),
        "stop_loss": _optional_float(item, "stop_loss") or _default_stop_loss(average_buy_price, broker_current_price),
    }

    if horizon is not None:
        position["investment_horizon"] = horizon

    for key in (
        "broker_current_price",
        "broker_acquisition_value",
        "broker_market_value",
        "broker_profit_eur",
        "broker_return_pct",
        "portfolio_weight_pct",
    ):
        value = _optional_float(item, key)
        if value is not None:
            position[key] = value

    return position


def _optional_float(item: dict, key: str) -> float | None:
    value = item.get(key)
    if value is None or value == "":
        return None
    return float(value)


def _default_target_price(average_buy_price: float, current_price: float | None) -> float:
    reference_price = current_price or average_buy_price
    return round(reference_price * 1.15, 4)


def _default_stop_loss(average_buy_price: float, current_price: float | None) -> float:
    if current_price is None:
        return round(average_buy_price * 0.85, 4)
    if current_price > average_buy_price:
        return round(max(average_buy_price * 0.95, current_price * 0.85), 4)
    return round(current_price * 0.9, 4)
