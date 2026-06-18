from __future__ import annotations

from datetime import datetime

from analyzer import analyze_forum_board_signals, analyze_forum_sentiment, build_annual_forecast, build_recommendation, calculate_technical_analysis, infer_investment_horizon
from config import get_dividend_tickers, get_portfolio, get_settings
from models import DividendInfo, ForumSignal, MarketOpportunity, MarketQuote, PortfolioAnalysis
from scrapers import scrape_dionice_board_posts, scrape_expert_commentary_posts, scrape_zse_dividends, scrape_zse_market_data


def analyze_portfolio(checked_at: datetime) -> list[PortfolioAnalysis]:
    quotes = scrape_zse_market_data()
    analyses: list[PortfolioAnalysis] = []
    dividend_tickers = get_dividend_tickers()
    dividends = scrape_zse_dividends()

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
        dividend = dividends.get(ticker)
        has_dividend = bool(position.get("has_dividend", ticker in dividend_tickers or dividend is not None))
        dividend_yield_pct = _dividend_yield_pct(dividend, quote, position.get("dividend_yield_pct"))
        annual_forecast = build_annual_forecast(quote, technical, recommendation, has_dividend, sentiment, dividend)
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
                has_dividend=has_dividend,
                dividend_per_share=dividend.amount_per_share if dividend else None,
                dividend_currency=dividend.currency if dividend else None,
                dividend_ex_date=dividend.ex_date if dividend else None,
                dividend_payment_date=dividend.payment_date if dividend else None,
                dividend_status=dividend.status if dividend else None,
                dividend_yield_pct=dividend_yield_pct,
                annual_forecast=annual_forecast,
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
    dividend_tickers = get_dividend_tickers()
    dividends = scrape_zse_dividends()

    for ticker, quote in quotes.items():
        if ticker in owned_tickers or quote.turnover_eur < 2_000:
            continue

        technical = calculate_technical_analysis(quote)
        action, reason, score = _score_market_opportunity(quote, technical)
        dividend = dividends.get(ticker)
        has_dividend = ticker in dividend_tickers or dividend is not None
        dividend_yield_pct = _dividend_yield_pct(dividend, quote, None)
        annual_forecast = build_annual_forecast(quote, technical, None, has_dividend, dividend_info=dividend)
        opportunities.append(
            MarketOpportunity(
                ticker=ticker,
                quote=quote,
                technical=technical,
                action=action,
                reason=reason,
                score=score,
                has_dividend=has_dividend,
                dividend_per_share=dividend.amount_per_share if dividend else None,
                dividend_currency=dividend.currency if dividend else None,
                dividend_ex_date=dividend.ex_date if dividend else None,
                dividend_payment_date=dividend.payment_date if dividend else None,
                dividend_status=dividend.status if dividend else None,
                dividend_yield_pct=dividend_yield_pct,
                annual_forecast=annual_forecast,
            )
        )

    return sorted(opportunities, key=lambda item: item.score, reverse=True)[:limit]


def analyze_forum_signals(known_tickers: set[str]) -> list[ForumSignal]:
    posts = scrape_dionice_board_posts()
    return analyze_forum_board_signals(posts, known_tickers)


def analyze_expert_signals(known_tickers: set[str]) -> list[ForumSignal]:
    posts = scrape_expert_commentary_posts()
    return analyze_forum_board_signals(posts, known_tickers)


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


def _dividend_yield_pct(dividend: DividendInfo | None, quote: MarketQuote | None, fallback: float | None) -> float | None:
    if fallback is not None:
        return float(fallback)
    if dividend is None or quote is None or quote.last_price <= 0:
        return None
    return round((dividend.amount_per_share / quote.last_price) * 100, 2)


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
