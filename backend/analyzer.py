from __future__ import annotations

import json
import logging
import math
from typing import Any

import pandas as pd
from openai import OpenAI

from config import InvestmentHorizon, PortfolioPosition, get_settings
from models import MarketQuote, Recommendation, SentimentResult, TechnicalAnalysis


logger = logging.getLogger(__name__)


def calculate_technical_analysis(quote: MarketQuote | None, historical_prices: list[float] | None = None) -> TechnicalAnalysis:
    if quote is None:
        return TechnicalAnalysis(rsi=50.0, ma50=0.0, trend="sideways", status="Nema tržišnih podataka")

    prices = historical_prices or _simulate_price_history(quote.last_price, quote.change_pct)
    series = pd.Series(prices, dtype="float64")
    ma50 = float(series.tail(50).mean())
    rsi = _calculate_rsi(series)

    if quote.last_price > ma50 * 1.015:
        trend = "uptrend"
        status = f"RSI {rsi:.1f}, cijena iznad MA50"
    elif quote.last_price < ma50 * 0.985:
        trend = "downtrend"
        status = f"RSI {rsi:.1f}, cijena ispod MA50"
    else:
        trend = "sideways"
        status = f"RSI {rsi:.1f}, blizu MA50"

    return TechnicalAnalysis(rsi=rsi, ma50=ma50, trend=trend, status=status)


def analyze_forum_sentiment(ticker: str, comments: list[str]) -> SentimentResult:
    if not comments:
        return SentimentResult(sentiment="neutral", summary="Sentiment nije korišten; analiza se temelji na ZSE tržišnim podacima.")

    settings = get_settings()
    if not settings.openai_api_key:
        logger.info("OPENAI_API_KEY is not configured; returning neutral sentiment for %s.", ticker)
        return SentimentResult(sentiment="neutral", summary="AI analiza nije dostupna jer OpenAI ključ nije konfiguriran.")

    client = OpenAI(api_key=settings.openai_api_key)
    comments_payload = "\n".join(f"- {comment[:1000]}" for comment in comments[:15])
    prompt = (
        "Analiziraj sentiment forumskih komentara o dionici na Zagrebačkoj burzi. "
        "Vrati isključivo strogi JSON objekt s ključevima sentiment i summary. "
        "sentiment mora biti bullish, bearish ili neutral. summary neka bude jedna kratka rečenica na hrvatskom.\n\n"
        f"Ticker: {ticker}\nKomentari:\n{comments_payload}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ti si konzervativni analitičar tržišnog sentimenta. Odgovaraš samo valjanim JSON-om."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        raw_content = response.choices[0].message.content or "{}"
        parsed: dict[str, Any] = json.loads(raw_content)
        sentiment = parsed.get("sentiment", "neutral")
        if sentiment not in {"bullish", "bearish", "neutral"}:
            sentiment = "neutral"
        summary = str(parsed.get("summary", "Sentiment nije moguće pouzdano odrediti.")).strip()
        return SentimentResult(sentiment=sentiment, summary=summary)
    except Exception as exc:
        logger.exception("OpenAI sentiment analysis failed for %s: %s", ticker, exc)
        return SentimentResult(sentiment="neutral", summary="AI analiza sentimenta trenutno nije dostupna.")


def build_recommendation(
    position: PortfolioPosition,
    quote: MarketQuote | None,
    technical: TechnicalAnalysis,
    sentiment: SentimentResult,
) -> Recommendation:
    if quote is None:
        return Recommendation(action="ZADRŽI", reason="Nedostaje aktualna tržišna cijena.", urgent=False)

    price = quote.last_price
    target = position["target_price"]
    stop_loss = position["stop_loss"]
    horizon = position["investment_horizon"]

    if horizon == "short_term":
        if price >= target:
            return Recommendation(action="PRODAJ", reason="Cijena je probila kratkoročni target.", urgent=True)
        if price <= stop_loss:
            return Recommendation(action="PRODAJ", reason="Aktiviran je stop-loss prag.", urgent=True)
        if technical.rsi >= 70 and sentiment.sentiment == "bearish":
            return Recommendation(action="PRODAJ", reason="RSI je prekupljen, a forum je bearish.", urgent=True)
        if technical.trend == "uptrend" and sentiment.sentiment == "bullish":
            return Recommendation(action="KUPI", reason="Kratkoročni momentum i sentiment su pozitivni.", urgent=False)
        return Recommendation(action="ZADRŽI", reason="Nema dovoljno jakog signala za transakciju.", urgent=False)

    panic_detected = sentiment.sentiment == "bearish" and any(
        word in sentiment.summary.lower()
        for word in ("panika", "fundamental", "stečaj", "revizija", "istraga", "gubitak", "kolaps")
    )
    extreme_target_break = price >= target * 1.2

    if panic_detected:
        return Recommendation(action="PRODAJ / DJELOMIČNA PRODAJA", reason="AI detektira moguću fundamentalnu paniku.", urgent=True)
    if extreme_target_break:
        return Recommendation(action="PRODAJ / DJELOMIČNA PRODAJA", reason="Cijena je ekstremno odskočila iznad targeta.", urgent=True)
    return Recommendation(action="ZADRŽI DUGOROČNO", reason="Dugoročni horizont ignorira kratkoročni šum.", urgent=False)


def infer_investment_horizon(
    position: PortfolioPosition,
    quote: MarketQuote | None,
    technical: TechnicalAnalysis,
    sentiment: SentimentResult,
    pnl_pct: float | None,
) -> tuple[InvestmentHorizon, str]:
    configured_horizon = position.get("investment_horizon")
    if configured_horizon in {"short_term", "long_term"}:
        return configured_horizon, "Ručno zadano u portfelju."

    return_pct = pnl_pct if pnl_pct is not None else position.get("broker_return_pct")
    portfolio_weight_pct = position.get("portfolio_weight_pct", 0.0)
    change_pct = abs(quote.change_pct) if quote is not None else 0.0

    if sentiment.sentiment == "bearish" and technical.trend == "downtrend":
        return "short_term", "Bearish sentiment i slab tehnički trend traže aktivnije praćenje."
    if return_pct is not None and return_pct >= 60:
        return "short_term", "Vrlo visok prinos sugerira taktičko upravljanje profitom."
    if technical.rsi >= 70 or change_pct >= 4:
        return "short_term", "Povišen momentum ili volatilnost sugerira kratkoročni režim praćenja."
    if portfolio_weight_pct >= 10 and sentiment.sentiment in {"bullish", "neutral"} and technical.trend != "downtrend":
        return "long_term", "Veći udio u portfelju i miran sentiment podržavaju dugoročno držanje."
    if return_pct is not None and return_pct < -5 and technical.trend == "downtrend":
        return "short_term", "Gubitak uz slab trend traži disciplinu oko rizika."
    return "long_term", "Nema izraženog kratkoročnog rizika, pa se pozicija tretira kao dugoročna."


def _simulate_price_history(last_price: float, change_pct: float) -> list[float]:
    drift = max(min(change_pct / 100, 0.04), -0.04)
    prices: list[float] = []
    for index in range(60):
        wave = math.sin(index / 5) * 0.012
        trend_component = (index - 59) * drift / 20
        prices.append(round(last_price * (1 + trend_component + wave), 4))
    prices[-1] = last_price
    return prices


def _calculate_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff().dropna()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    average_gain = gains.tail(period).mean()
    average_loss = losses.tail(period).mean()

    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return float(100 - (100 / (1 + relative_strength)))
