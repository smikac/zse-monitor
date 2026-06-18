from __future__ import annotations

import logging
import re
from typing import Any

import requests

from config import get_settings
from models import MarketQuote


ZSE_TRADING_PRICE_LIST_URL = "https://zse.hr/json/TradingPriceList"
ZSE_MARKET_SEGMENTS = "RP,RO,RR,TJDD,UT,TZIF,RGHT,DMTF,FMTF,SS,MF,MA,MX,TEST"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

logger = logging.getLogger(__name__)


def _headers() -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "hr-HR,hr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://zse.hr/hr/cijene-vrijednosnih-papira/36",
    }


def scrape_zse_market_data(only_traded: bool = False) -> dict[str, MarketQuote]:
    settings = get_settings()
    params = {
        "lng": "hr",
        "market_segment_ids": ZSE_MARKET_SEGMENTS,
        "type": "",
        "model": "",
        "date": "",
        "only_traded": "1" if only_traded else "0",
    }
    response = requests.get(
        ZSE_TRADING_PRICE_LIST_URL,
        params=params,
        headers=_headers(),
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()

    quotes: dict[str, MarketQuote] = {}
    for market in payload.get("priceList", []):
        market_segment = str(market.get("market_segment_id", ""))
        rows = market.get("tradingPriceList", {}).get("rows", [])
        for raw_row in rows:
            row = _normalize_zse_row(raw_row)
            quote = _row_to_quote(row, market_segment)
            if quote is not None:
                quotes[quote.ticker] = quote

    if not quotes:
        logger.warning("No quotes parsed from official ZSE TradingPriceList feed.")
    return quotes


def scrape_mojedionice() -> dict[str, MarketQuote]:
    return scrape_zse_market_data()


def scrape_dionice_forum(ticker: str) -> list[str]:
    return []


def parse_croatian_float(value: str) -> float:
    cleaned = (
        str(value)
        .replace("\xa0", " ")
        .replace("&nbsp;", " ")
        .replace("EUR", "")
        .replace("%", "")
        .replace("+", "")
        .strip()
    )
    cleaned = re.sub(r"[^\d,.\-]", "", cleaned)
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    if cleaned in {"", "-", ".", ","}:
        return 0.0
    return float(cleaned)


def _normalize_zse_row(raw_row: Any) -> dict[str, Any]:
    if isinstance(raw_row, dict):
        return raw_row

    text = str(raw_row).strip()
    if text.startswith("@{") and text.endswith("}"):
        text = text[2:-1]

    row: dict[str, str] = {}
    for key in _known_zse_keys():
        match = re.search(rf"(?:^|;\s*){re.escape(key)}=(.*?)(?=;\s*[A-Za-z_][A-Za-z0-9_]*=|$)", text)
        if match:
            row[key] = match.group(1).strip()
    return row


def _row_to_quote(row: dict[str, Any], market_segment: str) -> MarketQuote | None:
    if row.get("security_class_id") != "EQTY":
        return None

    ticker = str(row.get("symbol", "")).upper().strip()
    if not ticker:
        return None

    last_price = _field_float(row, "last_price_n", "last_price")
    if last_price <= 0:
        return None

    return MarketQuote(
        ticker=ticker,
        last_price=last_price,
        change_pct=_field_float(row, "change_prev_close_percentage"),
        turnover_eur=_field_float(row, "turnover_n", "turnover"),
        volume=_field_float(row, "volume_n", "volume"),
        vwap_price=_field_float(row, "vwap_price_n", "vwap_price"),
        market_segment=market_segment,
        isin=str(row.get("isin", "")).strip(),
        is_traded=str(row.get("IsTraded", "")).lower() == "true",
    )


def _field_float(row: dict[str, Any], *keys: str) -> float:
    for key in keys:
        value = row.get(key)
        if value in (None, "", "-"):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            try:
                return parse_croatian_float(str(value))
            except ValueError:
                continue
    return 0.0


def _known_zse_keys() -> tuple[str, ...]:
    return (
        "price_currency_id",
        "maturity_date",
        "interest_rate_percentage",
        "security_id",
        "security_class_id",
        "symbol",
        "trading_model_id",
        "isin",
        "trading_phase_code",
        "_data",
        "open_price",
        "open_price_n",
        "high_price",
        "high_price_n",
        "low_price",
        "low_price_n",
        "last_price",
        "last_price_n",
        "change_prev_close_percentage",
        "prev_traded_date",
        "vwap_price",
        "vwap_price_n",
        "volume",
        "volume_n",
        "turnover",
        "turnover_n",
        "sector_id",
        "IsTraded",
        "date",
    )
