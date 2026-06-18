from __future__ import annotations

from datetime import datetime

from analyzer import analyze_forum_sentiment, build_recommendation, calculate_technical_analysis, infer_investment_horizon
from config import get_portfolio, get_settings
from models import MarketOpportunity, MarketQuote, PortfolioAnalysis
from scrapers import scrape_zse_market_data


def analyze_portfolio(checked_at: datetime) -> list[PortfolioAnalysis]:
    quotes = scrape_zse_market_data()
    analyses: list[PortfolioAnalysis] = []

    for position in get_portfolio():
        ticker = position["ticker"]
        quote = quotes.get(ticker) or _broker_snapshot_quote(position)
        technical = calculate_technical_analysis(quote)
        sentiment = analyze_forum_sentiment(ticker, [])
        pnl_eur, pnl_pct = _calculate_pnl(position["kolicina"], position["prosjecna_kupovna_cijena"], quote)
        investment_horizon, horizon_reason = infer_investment_horizon(position, quote, technical, sentiment, pnl_pct)
        decision_position = dict(position)
        decision_position["investment_horizon"] = investment_horizon
        recommendation = build_recommendation(decision_position, quote, technical, sentiment)
        analyses.append(
            PortfolioAnalysis(
                ticker=ticker,
                quantity=position["kolicina"],
                average_buy_price=position["prosjecna_kupovna_cijena"],
                target_price=position["target_price"],
                stop_loss=position["stop_loss"],
                investment_horizon=investment_horizon,
                horizon_reason=horizon_reason,
                quote=quote,
                technical=technical,
                sentiment=sentiment,
                recommendation=recommendation,
                pnl_eur=pnl_eur,
                pnl_pct=pnl_pct,
                wow_event=_is_wow_event(quote),
                checked_at=checked_at,
            )
        )

    return analyses


def analyze_market_opportunities(owned_tickers: set[str], limit: int = 12) -> list[MarketOpportunity]:
    quotes = scrape_zse_market_data(only_traded=True)
    opportunities: list[MarketOpportunity] = []

    for ticker, quote in quotes.items():
        if ticker in owned_tickers or quote.turnover_eur < 2_000:
            continue

        technical = calculate_technical_analysis(quote)
        action, reason, score = _score_market_opportunity(quote, technical)
        opportunities.append(
            MarketOpportunity(
                ticker=ticker,
                quote=quote,
                technical=technical,
                action=action,
                reason=reason,
                score=score,
            )
        )

    return sorted(opportunities, key=lambda item: item.score, reverse=True)[:limit]


def _calculate_pnl(quantity: int, average_buy_price: float, quote: MarketQuote | None) -> tuple[float | None, float | None]:
    if quote is None:
        return None, None
    pnl_eur = (quote.last_price - average_buy_price) * quantity
    pnl_pct = ((quote.last_price - average_buy_price) / average_buy_price) * 100
    return pnl_eur, pnl_pct


def _is_wow_event(quote: MarketQuote | None) -> bool:
    if quote is None:
        return False
    settings = get_settings()
    return (
        quote.turnover_eur >= settings.wow_turnover_threshold_eur
        or abs(quote.change_pct) >= settings.wow_price_change_threshold_pct
    )


def _broker_snapshot_quote(position: dict) -> MarketQuote | None:
    current_price = position.get("broker_current_price")
    if current_price is None:
        return None
    return MarketQuote(
        ticker=position["ticker"],
        last_price=float(current_price),
        change_pct=0.0,
        turnover_eur=0.0,
        is_traded=False,
    )


def _score_market_opportunity(quote: MarketQuote, technical) -> tuple[str, str, float]:
    liquidity_score = min(quote.turnover_eur / 50_000, 3.0)
    momentum_score = max(min(quote.change_pct, 6.0), -6.0)
    trend_bonus = 1.5 if technical.trend == "uptrend" else -1.0 if technical.trend == "downtrend" else 0.0
    score = liquidity_score + momentum_score + trend_bonus

    if quote.change_pct >= 1.0 and quote.turnover_eur >= 10_000 and technical.trend == "uptrend":
        return "KUPI", "Likvidnost, dnevni momentum i tehnički trend su pozitivni.", score
    if quote.change_pct <= -2.5 or technical.trend == "downtrend":
        return "IZBJEGNI", "Dnevni pad ili slab tehnički trend sugerira oprez.", score
    return "PRATI", "Signal nije dovoljno jak za kupnju, ali vrijedi pratiti.", score
