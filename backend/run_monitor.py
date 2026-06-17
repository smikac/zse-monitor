from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from json_utils import to_jsonable
from notifier import build_alert_message, build_daily_summary, send_telegram_message
from portfolio_service import analyze_portfolio


ZAGREB_TZ = ZoneInfo("Europe/Zagreb")
REPO_ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_JSON = REPO_ROOT / "frontend" / "public" / "data" / "portfolio.json"
SCHEDULE = {
    "morning": time(9, 30),
    "tactical": time(15, 30),
    "summary": time(17, 0),
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ZSE portfolio monitor for GitHub Actions.")
    parser.add_argument("--force", choices=[*SCHEDULE.keys(), "auto"], default="auto")
    args = parser.parse_args()

    checked_at = datetime.now(ZAGREB_TZ)
    check_type = args.force if args.force != "auto" else _current_check_type(checked_at)
    if check_type is None:
        logger.info("No scheduled ZSE slot for %s; exiting cleanly.", checked_at.isoformat())
        return 0

    previous_payload = _load_previous_payload()
    if _already_completed_today(previous_payload, check_type, checked_at):
        logger.info("%s check already completed today; exiting cleanly.", check_type)
        return 0

    analyses = analyze_portfolio(checked_at)
    _send_notifications(check_type, analyses, checked_at)
    _write_dashboard_payload(previous_payload, check_type, analyses, checked_at)
    logger.info("Completed %s check with %d analyzed positions.", check_type, len(analyses))
    return 0


def _current_check_type(now: datetime) -> str | None:
    if now.weekday() >= 5:
        return None

    for check_type, scheduled_time in SCHEDULE.items():
        scheduled_at = now.replace(
            hour=scheduled_time.hour,
            minute=scheduled_time.minute,
            second=0,
            microsecond=0,
        )
        delay_minutes = (now - scheduled_at).total_seconds() / 60
        if 0 <= delay_minutes <= 20:
            return check_type
    return None


def _load_previous_payload() -> dict:
    if not PORTFOLIO_JSON.exists():
        return {}
    try:
        return json.loads(PORTFOLIO_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Existing portfolio JSON is invalid; replacing it.")
        return {}


def _already_completed_today(payload: dict, check_type: str, checked_at: datetime) -> bool:
    last_runs = payload.get("meta", {}).get("last_runs", {})
    return last_runs.get(check_type) == checked_at.date().isoformat()


def _send_notifications(check_type: str, analyses: list, checked_at: datetime) -> None:
    if check_type in {"morning", "tactical"}:
        for item in analyses:
            if item.wow_event or item.recommendation.urgent:
                send_telegram_message(build_alert_message(item, checked_at))
        return

    send_telegram_message(build_daily_summary(analyses, checked_at))


def _write_dashboard_payload(previous_payload: dict, check_type: str, analyses: list, checked_at: datetime) -> None:
    last_runs = previous_payload.get("meta", {}).get("last_runs", {})
    last_runs[check_type] = checked_at.date().isoformat()

    payload = {
        "meta": {
            "generated_at": checked_at.isoformat(),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "check_type": check_type,
            "last_runs": last_runs,
        },
        "positions": to_jsonable(analyses),
    }

    PORTFOLIO_JSON.parent.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
