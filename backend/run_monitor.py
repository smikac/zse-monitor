from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from json_utils import to_jsonable
from notifier import build_scheduled_report, build_signal_digest, send_telegram_message
from portfolio_service import analyze_expert_signals, analyze_forum_signals, analyze_market_opportunities, analyze_portfolio


ZAGREB_TZ = ZoneInfo("Europe/Zagreb")
REPO_ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_JSON = REPO_ROOT / "frontend" / "public" / "data" / "portfolio.json"
SCHEDULE = {
    "morning": time(10, 0),
    "tactical": time(15, 0),
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
        _write_github_output(False)
        return 0

    previous_payload = _load_previous_payload()
    is_manual_force = args.force != "auto"
    if not is_manual_force and _already_completed_today(previous_payload, check_type, checked_at):
        logger.info("%s check already completed today; exiting cleanly.", check_type)
        _write_github_output(False)
        return 0

    analyses = analyze_portfolio(checked_at)
    owned_tickers = {item.ticker for item in analyses}
    opportunities = analyze_market_opportunities(owned_tickers)
    known_tickers = owned_tickers | {item.ticker for item in opportunities}
    forum_signals = analyze_forum_signals(known_tickers)
    expert_signals = analyze_expert_signals(known_tickers)
    _send_notifications(analyses, opportunities, forum_signals, expert_signals, checked_at, check_type)
    _write_dashboard_payload(previous_payload, check_type, analyses, opportunities, forum_signals, expert_signals, checked_at)
    _write_github_output(True)
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


def _send_notifications(analyses: list, opportunities: list, forum_signals: list, expert_signals: list, checked_at: datetime, check_type: str) -> None:
    if check_type in {"morning", "tactical"}:
        message = build_scheduled_report(analyses, opportunities, forum_signals, expert_signals, checked_at, check_type)
        send_telegram_message(message)
        return

    message = build_signal_digest(analyses, opportunities, forum_signals, expert_signals, checked_at)
    if message is None:
        logger.info("No urgent sell, buy opportunity, or forum signal found; Telegram skipped.")
        return
    send_telegram_message(message)


def _write_dashboard_payload(
    previous_payload: dict,
    check_type: str,
    analyses: list,
    opportunities: list,
    forum_signals: list,
    expert_signals: list,
    checked_at: datetime,
) -> None:
    last_runs = previous_payload.get("meta", {}).get("last_runs", {})
    last_runs[check_type] = checked_at.date().isoformat()

    payload = {
        "meta": {
            "generated_at": checked_at.isoformat(),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "check_type": check_type,
            "last_runs": last_runs,
        },
        "positions": _sanitize_public_positions(to_jsonable(analyses)),
        "opportunities": to_jsonable(opportunities),
        "forum_signals": to_jsonable(forum_signals),
        "expert_signals": to_jsonable(expert_signals),
    }

    PORTFOLIO_JSON.parent.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sanitize_public_positions(positions: list[dict]) -> list[dict]:
    sanitized_positions: list[dict] = []
    for item in positions:
        sanitized = dict(item)
        sanitized["quantity"] = None
        sanitized["average_buy_price"] = None
        sanitized["target_price"] = None
        sanitized["stop_loss"] = None
        sanitized["pnl_eur"] = None
        sanitized["pnl_pct"] = None
        sanitized.pop("broker_current_price", None)
        sanitized.pop("broker_acquisition_value", None)
        sanitized.pop("broker_market_value", None)
        sanitized.pop("broker_profit_eur", None)
        sanitized.pop("broker_return_pct", None)
        sanitized.pop("portfolio_weight_pct", None)
        sanitized_positions.append(sanitized)
    return sanitized_positions


def _write_github_output(did_run: bool) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as output_file:
        output_file.write(f"did_run={'true' if did_run else 'false'}\n")


if __name__ == "__main__":
    raise SystemExit(main())
