from __future__ import annotations

import logging
import re
from datetime import date
from typing import Iterable

import requests
from bs4 import BeautifulSoup, Tag

from config import get_settings
from models import MarketQuote


MOJE_DIONICE_URL = "https://www.mojedionice.com/start/Start.aspx"
DIONICE_FORUM_SEARCH_URL = "https://dionice.net/forum/search.php"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

logger = logging.getLogger(__name__)


def _headers() -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "hr-HR,hr;q=0.9,en-US;q=0.8,en;q=0.7",
    }


def parse_croatian_float(value: str) -> float:
    cleaned = (
        value.replace("\xa0", " ")
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


def scrape_mojedionice() -> dict[str, MarketQuote]:
    settings = get_settings()
    response = requests.get(MOJE_DIONICE_URL, headers=_headers(), timeout=settings.request_timeout_seconds)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    quotes: dict[str, MarketQuote] = {}

    for row in _candidate_rows(soup):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
        quote = _parse_quote_row(cells)
        if quote is not None:
            quotes[quote.ticker] = quote

    if not quotes:
        logger.warning("No ZSE quotes parsed from mojediendionice response; page structure may have changed.")

    return quotes


def scrape_dionice_forum(ticker: str) -> list[str]:
    settings = get_settings()
    session = requests.Session()
    session.headers.update(_headers())

    params = {"keywords": ticker, "terms": "all", "author": "", "fid[]": "0", "sc": "1", "sf": "all", "sk": "t", "sd": "d", "sr": "posts", "st": "1"}
    try:
        response = session.get(DIONICE_FORUM_SEARCH_URL, params=params, timeout=settings.request_timeout_seconds)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Forum search failed for %s: %s", ticker, exc)
        return []

    soup = BeautifulSoup(response.text, "lxml")
    today = date.today()
    comments: list[str] = []

    for post in soup.select(".postbody, .content, .post, article"):
        text = post.get_text(" ", strip=True)
        if not text or ticker.lower() not in text.lower():
            continue
        if _looks_like_today(post, today):
            comments.append(_normalize_whitespace(text))
        if len(comments) >= 15:
            break

    return comments


def _candidate_rows(soup: BeautifulSoup) -> Iterable[Tag]:
    for table in soup.find_all("table"):
        table_text = table.get_text(" ", strip=True).lower()
        if any(keyword in table_text for keyword in ("zadnja", "promjena", "promet", "ticker", "oznaka")):
            yield from table.find_all("tr")


def _parse_quote_row(cells: list[str]) -> MarketQuote | None:
    if len(cells) < 4:
        return None

    ticker = _extract_ticker(cells)
    if not ticker:
        return None

    numbers = [parse_croatian_float(cell) for cell in cells if re.search(r"\d", cell)]
    if len(numbers) < 3:
        return None

    last_price = numbers[0]
    change_pct = _find_percent_value(cells, fallback=numbers[1])
    turnover_eur = numbers[-1]

    if last_price <= 0:
        return None

    return MarketQuote(
        ticker=ticker,
        last_price=last_price,
        change_pct=change_pct,
        turnover_eur=turnover_eur,
    )


def _extract_ticker(cells: list[str]) -> str | None:
    for cell in cells[:3]:
        match = re.search(r"\b[A-ZČĆŽŠĐ]{2,6}(?:-R-[A-Z])?\b", cell)
        if match:
            return match.group(0).split("-")[0]
    return None


def _find_percent_value(cells: list[str], fallback: float) -> float:
    for cell in cells:
        if "%" in cell:
            return parse_croatian_float(cell)
    return fallback


def _looks_like_today(post: Tag, today: date) -> bool:
    text = post.get_text(" ", strip=True).lower()
    iso_date = today.strftime("%Y-%m-%d")
    hr_date = today.strftime("%d.%m.%Y")
    short_hr_date = today.strftime("%d.%m.")
    return any(marker in text for marker in ("danas", iso_date, hr_date, short_hr_date))


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
