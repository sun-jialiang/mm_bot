import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import io
import pdfplumber
from datetime import datetime
from zoneinfo import ZoneInfo
from desy import extract_pdf_text, fetch_menu_pdf, find_daily_menu, clean_menu_text
from cfel import scrape_headlines_and_prices, format_menus  # noqa

MENU_PAGE_URL = "https://www.labcuisine.de/menu/"
DESY_URL = "https://desy.myalsterfood.de/download/en/menu.pdf"
CFEL_URL = "https://www.stwhh.de/gastronomie/mensen-cafes-weiteres/mensa/cafe-cfel"


def get_target_day() -> str | None:
    """Return the weekday name ('monday'...'friday') based on Europe/Berlin time."""
    berlin = ZoneInfo("Europe/Berlin")
    today = datetime.now(berlin)
    weekday = today.weekday()  # 0=Mon, ..., 6=Sun
    mapping = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday"}
    return mapping.get(weekday)  # None on weekend


def get_max_planck_pdf() -> str:
    """Find the first PDF link on the Max Planck menu page."""
    resp = requests.get(MENU_PAGE_URL, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            return urljoin(MENU_PAGE_URL, href)
    raise RuntimeError("Could not find any PDF link on the menu page")


def extract_menu_for_day(pdf_bytes: bytes, target_day: str = "tuesday") -> str:
    """Extract Max Planck menu for a specific day from weekly PDF."""
    WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    target_day = target_day.lower()

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        page = pdf.pages[0]  # this PDF has English menu on page index 2
        text = (page.extract_text() or "").lower()
        if not all(day in text for day in WEEKDAYS):
            raise RuntimeError("This page does not look like the weekly menu page")

        table = page.extract_table()
        if not table:
            raise RuntimeError("Could not extract table from menu page")

    header = table[0]
    header_idx = next(
        (j for j, cell in enumerate(header) if cell and target_day in cell.lower()),
        None,
    )
    if header_idx is None:
        raise RuntimeError(f"Could not find header for {target_day!r}")

    content_col = max(header_idx - 1, 0)
    lines: list[str] = []

    for row in table[1:4]:  # skip header row
        if not row or content_col >= len(row):
            continue
        label = " ".join(row[0].split()) if row[0] else ""
        dish = " ".join(row[content_col].split())
        if not dish:
            continue
        lines.append(f"{label}: {dish}" if label else dish)

    return (
        "\n".join(lines) if lines else f"No menu entries found for {target_day.title()}"
    )


def extract_desy_menu(target_day: str) -> str:
    """Fetch DESY menu PDF and extract today's menu in clean text format."""
    pdf_bytes = fetch_menu_pdf(DESY_URL)
    pdf_tables = extract_pdf_text(pdf_bytes)
    daily_menu_row = find_daily_menu(pdf_tables)
    if not daily_menu_row:
        return f"No DESY menu found for {target_day.title()}"
    header = pdf_tables[0][0]  # first row is header
    return clean_menu_text(header, daily_menu_row)


def send_to_mattermost(text: str):
    """Send a message to Mattermost via webhook."""
    webhook_url = os.environ.get("MM_WEBHOOK_URL")
    if not webhook_url:
        print("GitHub secret not accessed")

    resp = requests.post(webhook_url, json={"text": text}, timeout=10)
    resp.raise_for_status()
    print("Sent successfully:", resp.text)


def main():
    today = get_target_day()
    if not today:
        print("No menu: today is weekend.")
        return

    # Max Planck menu
    mp_pdf_url = get_max_planck_pdf()
    mp_pdf_resp = requests.get(mp_pdf_url, timeout=10)
    mp_pdf_resp.raise_for_status()
    mp_menu = extract_menu_for_day(mp_pdf_resp.content, today)

    # DESY menu
    desy_menu = extract_desy_menu(today)

    # CFEL menu
    cfel_menu = format_menus(scrape_headlines_and_prices(CFEL_URL))

    message = f"""
@channel
[CFEL/UHH]({CFEL_URL})
```text
{cfel_menu}
```

[DESY]({DESY_URL})
```text
{desy_menu}
```
[Max Planck]({mp_pdf_url}) 
```text
{mp_menu}
```
"""

    send_to_mattermost(message)


if __name__ == "__main__":
    main()
