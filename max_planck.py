from __future__ import annotations

import io
from dataclasses import dataclass
from urllib.parse import urljoin

import pdfplumber
import requests
from bs4 import BeautifulSoup

MAX_PLANCK_MENU_PAGE_URL = "https://www.labcuisine.de/menu/"
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday")


@dataclass(frozen=True)
class MaxPlanckMenu:
    pdf_url: str
    text: str


def find_pdf_url(
    menu_page_url: str = MAX_PLANCK_MENU_PAGE_URL,
    session: requests.Session | None = None,
) -> str:
    """Find the first PDF link on the Max Planck menu page."""
    session = session or requests.Session()
    resp = session.get(menu_page_url, timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    for link in soup.find_all("a", href=True):
        href = link["href"]
        clean_href = href.lower().split("?", 1)[0].split("#", 1)[0]
        if clean_href.endswith(".pdf"):
            return urljoin(menu_page_url, href)

    raise RuntimeError("Could not find any PDF link on the Max Planck menu page")


def fetch_pdf(
    pdf_url: str,
    session: requests.Session | None = None,
) -> bytes:
    """Download a Max Planck menu PDF."""
    session = session or requests.Session()
    resp = session.get(pdf_url, timeout=10)
    resp.raise_for_status()
    return resp.content


def extract_menu_for_day(pdf_bytes: bytes, target_day: str) -> str:
    """Extract Max Planck menu text for a specific weekday from the weekly PDF."""
    target_day = target_day.lower()

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        table = None
        for page in pdf.pages:
            text = (page.extract_text() or "").lower()
            if all(day in text for day in WEEKDAYS):
                table = page.extract_table()
                break

    if table is None:
        raise RuntimeError("Could not find the weekly menu page in the PDF")
    if not table:
        raise RuntimeError("Could not extract a table from the weekly menu page")

    header = table[0]
    header_idx = next(
        (idx for idx, cell in enumerate(header) if cell and target_day in cell.lower()),
        None,
    )
    if header_idx is None:
        raise RuntimeError(f"Could not find header for {target_day!r}")

    content_col = max(header_idx - 1, 0)
    lines: list[str] = []

    for row in table[1:4]:
        if not row or content_col >= len(row):
            continue

        label = " ".join(row[0].split()) if row[0] else ""
        dish = " ".join(row[content_col].split()) if row[content_col] else ""
        if not dish:
            continue

        lines.append(f"{label}: {dish}" if label else dish)

    return (
        "\n".join(lines) if lines else f"No menu entries found for {target_day.title()}"
    )


def get_daily_menu(
    target_day: str,
    session: requests.Session | None = None,
) -> MaxPlanckMenu:
    """Return the Max Planck PDF URL and menu text.

    A broken or missing PDF should not block the daily post. If the PDF URL can
    be discovered, it is returned even when the PDF cannot be downloaded or read.
    """
    session = session or requests.Session()

    try:
        pdf_url = find_pdf_url(session=session)
    except Exception as exc:
        return MaxPlanckMenu(
            pdf_url=MAX_PLANCK_MENU_PAGE_URL,
            text=f"No Max Planck PDF link found: {exc}",
        )

    try:
        menu_text = extract_menu_for_day(fetch_pdf(pdf_url, session=session), target_day)
    except Exception as exc:
        menu_text = (
            f"Could not read the Max Planck PDF for {target_day.title()}: {exc}"
        )

    return MaxPlanckMenu(pdf_url=pdf_url, text=menu_text)


if __name__ == "__main__":
    print(get_daily_menu("monday").text)
