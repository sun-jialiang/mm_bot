from __future__ import annotations

import json
import os
import random
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

from cfel import CFEL_URL, get_daily_menu as get_cfel_menu
from desy import DESY_MENU_PDF_URL, get_daily_menu as get_desy_menu
from max_planck import get_daily_menu as get_max_planck_menu

# Feature toggles
TOPIC_OF_THE_DAY = True  # When True, the menu is wrapped in a themed daily style


def get_daily_style() -> dict:
    """Load a style from styles.json, selected deterministically by today's date.

    The same style is returned for the entire day.  The style name is never
    included in the returned dict so that the theme remains undisclosed to
    channel members — making it an implicit guessing game.
    """
    styles_path = os.path.join(os.path.dirname(__file__), "styles.json")
    try:
        with open(styles_path) as f:
            styles = json.load(f)
    except FileNotFoundError:
        raise RuntimeError(
            f"styles.json not found at {styles_path}. "
            "This file is required when TOPIC_OF_THE_DAY is enabled."
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"styles.json contains invalid JSON (required for TOPIC_OF_THE_DAY): {exc}"
        )
    if not styles:
        raise RuntimeError(
            "styles.json must contain at least one style entry "
            "(required for TOPIC_OF_THE_DAY)."
        )
    berlin = ZoneInfo("Europe/Berlin")
    today = datetime.now(berlin)
    seed = today.year * 10000 + today.month * 100 + today.day
    rng = random.Random(seed)
    return rng.choice(styles)


def get_target_day() -> str | None:
    """Return the weekday name ('monday'...'friday') based on Europe/Berlin time."""
    berlin = ZoneInfo("Europe/Berlin")
    today = datetime.now(berlin)
    weekday = today.weekday()  # 0=Mon, ..., 6=Sun
    mapping = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday"}
    return mapping.get(weekday)  # None on weekend


def send_to_mattermost(text: str):
    """Send a message to Mattermost via webhook."""
    webhook_url = os.environ.get("MM_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError("MM_WEBHOOK_URL environment variable is not set")

    resp = requests.post(webhook_url, json={"text": text}, timeout=10)
    resp.raise_for_status()
    print("Sent successfully:", resp.text)


def format_section(title: str, url: str, text: str) -> str:
    return f"[{title}]({url})\n```text\n{text}\n```"


def build_message(target_day: str) -> str:
    cfel_menu = get_cfel_menu()
    desy_menu = get_desy_menu(target_day)
    max_planck_menu = get_max_planck_menu(target_day)

    sections = [
        format_section("CFEL/UHH", CFEL_URL, cfel_menu),
        format_section("DESY", DESY_MENU_PDF_URL, desy_menu),
        format_section("Max Planck", max_planck_menu.pdf_url, max_planck_menu.text),
    ]

    message = "@channel\n\n" + "\n\n".join(sections)

    if TOPIC_OF_THE_DAY:
        style = get_daily_style()
        message = f"{style['intro']}\n{message}\n{style['outro']}"

    return message


def main():
    today = get_target_day()
    if not today:
        print("No menu: today is weekend.")
        return

    message = build_message(today)
    send_to_mattermost(message)


if __name__ == "__main__":
    main()
