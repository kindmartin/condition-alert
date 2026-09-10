"""Orchestrator: load config -> load state -> fetch -> evaluate -> notify -> save state.

Run hourly by .github/workflows/wind-check.yml. Sends at most one digest email
per subscriber per local calendar day, only when at least one forecast hour that
day satisfies every wind layer that subscriber configured for that site.

Sites (coordinates) live in the public config/sites.yaml. Subscribers (email +
their own layer thresholds) live in the SUBSCRIBERS_JSON secret, since the repo
is public and subscriber emails shouldn't be — see MANUAL.md.
"""
import argparse
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from fetch_forecast import collect_points, fetch_forecast
from notify import build_email_body, build_telegram_text, send_email, send_telegram, subject_line
from rules import evaluate_layers
from state import load_state, prune_old, save_state, site_date_key

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "sites.yaml"
STATE_PATH = ROOT / "state" / "sent_log.json"


def local_today(site):
    tz = ZoneInfo(site["timezone"])
    return datetime.now(tz).date().isoformat()


def load_subscribers():
    raw = os.environ.get("SUBSCRIBERS_JSON")
    if not raw:
        return {}
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Evaluate and print, but never send email or write state")
    args = parser.parse_args()

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    sites = config["sites"]
    subscribers_by_site = load_subscribers()

    state = load_state(STATE_PATH)
    original_state = dict(state)

    points = collect_points(sites)
    try:
        forecast = fetch_forecast(points)
    except Exception as exc:  # noqa: BLE001 - single free API, fail loudly, no retry logic needed for v1
        print(f"ERROR fetching Open-Meteo forecast: {exc}", file=sys.stderr)
        sys.exit(1)

    smtp_user = os.environ.get("GMAIL_USER")
    smtp_password = os.environ.get("GMAIL_APP_PASSWORD")
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")

    for site in sites:
        site_id = site["id"]
        subscribers = subscribers_by_site.get(site_id, [])
        if not subscribers:
            print(f"[{site_id}] no subscribers, skipping")
            continue

        today_str = local_today(site)
        points_hourly = {
            point_name: forecast[(site_id, point_name)]["hourly"]
            for point_name in site["points"]
        }

        for subscriber in subscribers:
            email = subscriber.get("email")
            chat_id = subscriber.get("telegram_chat_id")
            alert_name = subscriber.get("alert_name")
            identity = email or (f"telegram:{chat_id}" if chat_id else None)
            if not identity:
                print(f"[{site_id}] subscriber {subscriber.get('name', '?')!r} has neither email nor telegram_chat_id, skipping", file=sys.stderr)
                continue
            # Someone can have several independent named alerts on the same
            # site (each with its own layers) — the state key must include
            # the alert name so they're deduped/sent independently.
            label = f"{identity}#{alert_name}" if alert_name else identity

            key = site_date_key(site_id, label, today_str)
            if key in state:
                print(f"[{site_id}] already sent to {label} for {today_str}, skipping")
                continue

            hourly_results = evaluate_layers(subscriber["layers"], site, points_hourly)
            qualifying = [h for h in hourly_results if h["time"].startswith(today_str) and h["passed"]]

            if not qualifying:
                print(f"[{site_id}] no qualifying hours for {label} on {today_str}")
                continue

            subject = subject_line(site, today_str, len(qualifying), alert_name)
            body = build_email_body(site, today_str, qualifying, subscriber["layers"], subscriber.get("name"), alert_name)

            if args.dry_run:
                print(f"[{site_id}] WOULD SEND to {label}:\nSubject: {subject}\n{body}\n")
                continue

            sent = False
            if email:
                if smtp_user and smtp_password:
                    send_email(subject, body, smtp_user, smtp_password, email)
                    sent = True
                else:
                    print(f"[{site_id}] {label}: GMAIL_USER/GMAIL_APP_PASSWORD not set, skipping email", file=sys.stderr)
            if chat_id:
                if telegram_token:
                    send_telegram(telegram_token, chat_id, build_telegram_text(subject, body))
                    sent = True
                else:
                    print(f"[{site_id}] {label}: TELEGRAM_BOT_TOKEN not set, skipping Telegram", file=sys.stderr)

            if not sent:
                continue

            print(f"[{site_id}] sent digest to {label} for {today_str} ({len(qualifying)} hour(s))")
            state[key] = {
                "sent_at": datetime.now(ZoneInfo(site["timezone"])).isoformat(),
                "qualifying_hours": [h["time"] for h in qualifying],
            }

    if not args.dry_run:
        state = prune_old(state)
        if state != original_state:
            save_state(STATE_PATH, state)


if __name__ == "__main__":
    main()
