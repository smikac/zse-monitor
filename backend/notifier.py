from __future__ import annotations

import html
import logging
from datetime import datetime

import requests

from config import get_settings
from models import ForumSignal, MarketOpportunity, PortfolioAnalysis


logger = logging.getLogger(__name__)


def send_telegram_message(message: str) -> bool:
    settings = get_settings()
    if not settings.telegram_token or not settings.telegram_chat_id:
        logger.info("Telegram credentials are not configured; message skipped.")
        return False

    url = f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=settings.request_timeout_seconds)
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.exception("Telegram notification failed: %s", exc)
        return False


def build_alert_message(analysis: PortfolioAnalysis, checked_at: datetime) -> str:
    quote = analysis.quote
    price = f"{quote.last_price:.2f} EUR" if quote else "N/A"
    change = f"{quote.change_pct:+.2f}%" if quote else "N/A"
    turnover = f"{quote.turnover_eur:,.0f} EUR" if quote else "N/A"

    return (
        f"*HITNI ZSE ALERT* `{checked_at.strftime('%H:%M')}`\n"
        f"*{_escape_md(analysis.ticker)}* - *{_escape_md(analysis.recommendation.action)}*\n"
        f"Cijena: `{price}` | Promjena: `{change}` | Promet: `{turnover}`\n"
        f"Razlog: {_escape_md(analysis.recommendation.reason)}\n"
        f"AI: {_escape_md(analysis.sentiment.sentiment)} - {_escape_md(analysis.sentiment.summary)}"
    )


def build_daily_summary(analyses: list[PortfolioAnalysis], checked_at: datetime) -> str:
    lines = [f"*ZSE Daily Summary* `{checked_at.strftime('%d.%m.%Y %H:%M')}`", ""]
    for item in analyses:
        quote = item.quote
        price = f"{quote.last_price:.2f} EUR" if quote else "N/A"
        pnl = f"{item.pnl_eur:+.2f} EUR ({item.pnl_pct:+.2f}%)" if item.pnl_eur is not None and item.pnl_pct is not None else "N/A"
        wow = " | WOOW" if item.wow_event else ""
        lines.append(
            f"*{_escape_md(item.ticker)}* `{price}` P&L `{pnl}` "
            f"- *{_escape_md(item.recommendation.action)}*{wow}\n"
            f"Tech: {_escape_md(item.technical.status)}\n"
            f"AI: {_escape_md(item.sentiment.summary)}"
        )
        lines.append("")
    return "\n".join(lines).strip()


def build_scheduled_report(
    analyses: list[PortfolioAnalysis],
    opportunities: list[MarketOpportunity],
    forum_signals: list[ForumSignal],
    expert_signals: list[ForumSignal],
    checked_at: datetime,
    check_type: str,
) -> str:
    report_name = "Jutarnji izvještaj" if check_type == "morning" else "Popodnevni izvještaj"
    lines = [f"*ZSE {report_name}* `{checked_at.strftime('%d.%m.%Y %H:%M')}`", ""]

    lines.append("*Portfelj*")
    if analyses:
        for item in analyses:
            quote = item.quote
            price = f"{quote.last_price:.2f} EUR" if quote else "N/A"
            change = f"{quote.change_pct:+.2f}%" if quote else "N/A"
            lines.append(
                f"- *{_escape_md(item.ticker)}* `{price}` `{change}` - "
                f"{_escape_md(item.recommendation.action)}"
            )
    else:
        lines.append("- Nema pozicija za prikaz.")
    lines.append("")

    lines.append("*Dnevni ZSE kandidati*")
    if opportunities:
        for item in opportunities[:6]:
            lines.append(
                f"- *{_escape_md(item.ticker)}* {_escape_md(item.action)} "
                f"`{item.quote.last_price:.2f} EUR` `{item.quote.change_pct:+.2f}%` - "
                f"{_escape_md(item.reason)}"
            )
    else:
        lines.append("- Nema dovoljno jakih kandidata izvan portfelja.")
    lines.append("")

    relevant_forum = [item for item in forum_signals if item.action in {"KUPI", "PRODAJ"}]
    relevant_expert = [item for item in expert_signals if item.action in {"KUPI", "PRODAJ"}]
    lines.append("*Forum / expert signali*")
    if not relevant_forum and not relevant_expert:
        lines.append("- Nema novih bitnih signala.")
    for item in relevant_forum[:4]:
        lines.append(f"- Forum: *{_escape_md(item.ticker)}* {_escape_md(item.action)} - {_escape_md(item.summary)}")
    for item in relevant_expert[:4]:
        lines.append(f"- Expert: *{_escape_md(item.ticker)}* {_escape_md(item.action)} - {_escape_md(item.summary)}")

    return "\n".join(lines).strip()


def build_signal_digest(
    analyses: list[PortfolioAnalysis],
    opportunities: list[MarketOpportunity],
    forum_signals: list[ForumSignal],
    expert_signals: list[ForumSignal],
    checked_at: datetime,
) -> str | None:
    urgent_sells = [item for item in analyses if item.recommendation.urgent or "PRODAJ" in item.recommendation.action]
    buy_opportunities = [item for item in opportunities if item.action == "KUPI"]
    relevant_forum = [item for item in forum_signals if item.action in {"KUPI", "PRODAJ"}]
    relevant_expert = [item for item in expert_signals if item.action in {"KUPI", "PRODAJ"}]

    if not urgent_sells and not buy_opportunities and not relevant_forum and not relevant_expert:
        return None

    lines = [f"*ZSE signal* `{checked_at.strftime('%d.%m.%Y %H:%M')}`", ""]

    if urgent_sells:
        lines.append("*Hitno u portfelju*")
        for item in urgent_sells[:6]:
            quote = item.quote
            price = f"{quote.last_price:.2f} EUR" if quote else "N/A"
            lines.append(f"- *{_escape_md(item.ticker)}* {_escape_md(item.recommendation.action)} `{price}` - {_escape_md(item.recommendation.reason)}")
        lines.append("")

    if buy_opportunities:
        lines.append("*Zanimljivo za kupnju / praćenje*")
        for item in buy_opportunities[:6]:
            lines.append(
                f"- *{_escape_md(item.ticker)}* `{item.quote.last_price:.2f} EUR` "
                f"`{item.quote.change_pct:+.2f}%` promet `{item.quote.turnover_eur:,.0f} EUR` - {_escape_md(item.reason)}"
            )
        lines.append("")

    if relevant_forum:
        lines.append("*Forum signali*")
        for item in relevant_forum[:6]:
            lines.append(f"- *{_escape_md(item.ticker)}* {_escape_md(item.action)} - {_escape_md(item.summary)}")
        lines.append("")

    if relevant_expert:
        lines.append("*Expert komentari*")
        for item in relevant_expert[:6]:
            lines.append(f"- *{_escape_md(item.ticker)}* {_escape_md(item.action)} - {_escape_md(item.summary)}")
        lines.append("")

    return "\n".join(lines).strip()


def _escape_md(value: str) -> str:
    return html.escape(value).replace("_", "\\_").replace("*", "\\*").replace("`", "'")
