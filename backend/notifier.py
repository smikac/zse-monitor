from __future__ import annotations

import html
import logging
from datetime import datetime

import requests

from config import get_settings
from models import PortfolioAnalysis


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


def _escape_md(value: str) -> str:
    return html.escape(value).replace("_", "\\_").replace("*", "\\*").replace("`", "'")
