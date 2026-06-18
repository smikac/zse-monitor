from __future__ import annotations

from datetime import datetime

from analyzer import analyze_forum_sentiment, build_recommendation, calculate_technical_analysis
from config import get_portfolio, get_settings
from models import MarketQuote, PortfolioAnalysis
from scrapers import scrape_dionice_forum, scrape_mojedionice


def analyze_portfolio(checked_at: datetime) -> list[PortfolioAnalysis]:
    quotes = scrape_mojedionice()
    analyses: list[PortfolioAnalysis] = []

    for position in get_portfolio():
        ticker = position["ticker"]
        quote = quotes.get(ticker)
        forum_comments = scrape_dionice_forum(ticker)
        technical = calculate_technical_analysis(quote)
        sentiment = analyze_forum_sentiment(ticker, forum_comments)
        recommendation = build_recommendation(position, quote, technical, sentiment)
        pnl_eur, pnl_pct = _calculate_pnl(position["kolicina"], position["prosjecna_kupovna_cijena"], quote)
        analyses.append(
            PortfolioAnalysis(
                ticker=ticker,
                quantity=position["kolicina"],
                average_buy_price=position["prosjecna_kupovna_cijena"],
                target_price=position["target_price"],
                stop_loss=position["stop_loss"],
                investment_horizon=position["investment_horizon"],
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
