from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import get_expert_feed_urls, get_expert_posts, get_settings
from models import MarketQuote


ZSE_TRADING_PRICE_LIST_URL = "https://zse.hr/json/TradingPriceList"
ZSE_MARKET_SEGMENTS = "RP,RO,RR,TJDD,UT,TZIF,RGHT,DMTF,FMTF,SS,MF,MA,MX,TEST"
DIONICE_BOARD_URL = "https://dionice.net/forum/board/2-dionice/"
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
    ticker_upper = ticker.upper()
    return [
        post["text"]
        for post in scrape_dionice_board_posts()
        if ticker_upper in post["text"].upper()
    ][:15]


def scrape_dionice_board_posts(limit: int = 12) -> list[dict[str, str]]:
    settings = get_settings()
    try:
        response = requests.get(
            DIONICE_BOARD_URL,
            headers={**_headers(), "Accept": "text/html,application/xhtml+xml"},
            timeout=settings.request_timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Dionice.net board scraping failed: %s", exc)
        return []

    soup = BeautifulSoup(response.text, "lxml")
    posts: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for link in soup.select("a[href]"):
        href = str(link.get("href", ""))
        title = link.get_text(" ", strip=True)
        if not title or len(title) < 3:
            continue
        if not any(pattern in href for pattern in ("/forum/tema/", "/forum/thread/", "/forum/post/", "/forum/topic/")):
            continue
        url = urljoin(DIONICE_BOARD_URL, href)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        surrounding_text = _fetch_forum_topic_excerpt(url) or (link.find_parent().get_text(" ", strip=True) if link.find_parent() else title)
        posts.append(
            {
                "title": title[:180],
                "text": _normalize_space(f"{title}. {surrounding_text}")[:1200],
                "url": url,
            }
        )
        if len(posts) >= limit:
            break

    return posts


def scrape_expert_commentary_posts(limit_per_feed: int = 8) -> list[dict[str, str]]:
    posts = get_expert_posts()
    settings = get_settings()

    for feed_url in get_expert_feed_urls():
        try:
            response = requests.get(
                feed_url,
                headers=_headers(),
                timeout=settings.request_timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Expert feed fetch failed for %s: %s", feed_url, exc)
            continue

        soup = BeautifulSoup(response.text, "xml")
        feed_items = soup.find_all(["item", "entry"])[:limit_per_feed]
        if feed_items:
            posts.extend(_parse_feed_items(feed_items, feed_url))
            continue

        html_soup = BeautifulSoup(response.text, "lxml")
        posts.extend(_parse_html_expert_page(html_soup, feed_url, limit_per_feed))

    return posts[:30]


def _fetch_forum_topic_excerpt(url: str) -> str:
    settings = get_settings()
    try:
        response = requests.get(
            url,
            headers={**_headers(), "Accept": "text/html,application/xhtml+xml"},
            timeout=settings.request_timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException:
        return ""

    soup = BeautifulSoup(response.text, "lxml")
    candidates = soup.select(".messageText, .messageBody, .message, article, .htmlContent")
    texts = [_normalize_space(item.get_text(" ", strip=True)) for item in candidates]
    texts = [text for text in texts if len(text) > 40]
    return " ".join(texts[-3:])[:1400]


def _parse_feed_items(feed_items: list, feed_url: str) -> list[dict[str, str]]:
    posts: list[dict[str, str]] = []
    for item in feed_items:
        title = _tag_text(item, "title") or "Expert commentary"
        link = _tag_text(item, "link")
        if not link:
            link_tag = item.find("link")
            link = str(link_tag.get("href", "")) if link_tag and link_tag.has_attr("href") else feed_url
        summary = _tag_text(item, "description") or _tag_text(item, "summary") or _tag_text(item, "content") or title
        posts.append(
            {
                "title": _normalize_space(title)[:180],
                "text": _normalize_space(f"{title}. {BeautifulSoup(summary, 'lxml').get_text(' ', strip=True)}")[:1800],
                "url": link.strip(),
                "source": feed_url,
            }
        )
    return posts


def _parse_html_expert_page(soup: BeautifulSoup, source_url: str, limit: int) -> list[dict[str, str]]:
    posts: list[dict[str, str]] = []
    for item in soup.select("article, .post, .entry, [role='article']")[:limit]:
        text = _normalize_space(item.get_text(" ", strip=True))
        if len(text) < 60:
            continue
        link = item.find("a", href=True)
        posts.append(
            {
                "title": text[:120],
                "text": text[:1800],
                "url": urljoin(source_url, str(link["href"])) if link else source_url,
                "source": source_url,
            }
        )
    return posts


def _tag_text(item, tag_name: str) -> str:
    tag = item.find(tag_name)
    return tag.get_text(" ", strip=True) if tag else ""


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


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
