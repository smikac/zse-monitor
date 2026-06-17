from __future__ import annotations

import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import azure.functions as func

from notifier import build_alert_message, build_daily_summary, send_telegram_message
from portfolio_service import analyze_portfolio


app = func.FunctionApp()
logger = logging.getLogger(__name__)
ZAGREB_TZ = ZoneInfo("Europe/Zagreb")


@app.timer_trigger(schedule="0 * 7-16 * * 1-5", arg_name="timer", run_on_startup=False, use_monitor=True)
def zse_scheduled_check(timer: func.TimerRequest) -> None:
    check_type = _current_scheduled_check()
    if check_type is None:
        logger.info("Skipping ZSE check outside configured Zagreb market slots.")
        return

    _run_market_check(check_type)


@app.route(route="portfolio", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def get_portfolio(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return func.HttpResponse("", status_code=204, headers=_cors_headers())

    checked_at = datetime.now(timezone.utc)
    analyses = analyze_portfolio(checked_at)
    return func.HttpResponse(
        json.dumps([_to_jsonable(item) for item in analyses], ensure_ascii=False),
        mimetype="application/json",
        status_code=200,
        headers=_cors_headers(),
    )


def _run_market_check(check_type: str) -> None:
    checked_at = datetime.now(ZAGREB_TZ)
    logger.info("Starting ZSE %s check at %s", check_type, checked_at.isoformat())
    analyses = analyze_portfolio(checked_at)

    if check_type in {"morning", "tactical"}:
        for item in analyses:
            if item.wow_event or item.recommendation.urgent:
                send_telegram_message(build_alert_message(item, checked_at))
        return

    send_telegram_message(build_daily_summary(analyses, checked_at))


def _current_scheduled_check() -> str | None:
    now = datetime.now(ZAGREB_TZ)
    schedule_by_time = {
        (9, 30): "morning",
        (15, 30): "tactical",
        (17, 0): "summary",
    }
    return schedule_by_time.get((now.hour, now.minute))


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {key: _to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    return value


def _cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, x-functions-key",
    }
