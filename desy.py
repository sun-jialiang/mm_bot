import io
import re
import requests
import pdfplumber
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Optional

# --- Constants ---
PRICE_RE = re.compile(r"€\s*([\d\.,]+)")
NUTRITION_KEYWORDS = ("kcal", "P:", "F:", "C:")
ALLERGENS_RE = re.compile(r"^[\d\)\(\s\.\-\,/]+$")


# --- Core Functions ---
def clean_menu_text(header: List[str], daily_menu: List[str]) -> str:
    """
    Converts a PDF row into clean menu text.
    header: list of column headers (e.g., ['', 'Main meal', 'Menu 2', ...])
    daily_menu: row with menu items
    """
    lines_out = []

    for hdr, cell in zip(header, daily_menu):
        if not hdr or not hdr.strip() or not cell:
            continue

        label = "Menu 1" if hdr.lower().startswith("main") else hdr.strip()
        lines = [ln.strip() for ln in cell.splitlines() if ln.strip()]

        # Extract price
        price = None
        for i, ln in enumerate(lines):
            match = PRICE_RE.search(ln)
            if match:
                price = f"{float(match.group(1).replace(',', '.')):.2f}€"
                title_lines = lines[:i]
                break
        else:
            # Drop nutrition/allergen lines if no price found
            title_lines = [
                ln
                for ln in lines
                if not any(k in ln for k in NUTRITION_KEYWORDS)
                and not ALLERGENS_RE.match(ln)
            ]
            if not title_lines and lines:
                title_lines = [lines[0]]

        title = " ".join(" ".join(ln.split()).strip(" /") for ln in title_lines)
        if title:
            lines_out.append(
                f"{label} {price}: {title}" if price else f"{label}: {title}"
            )

    return "\n".join(lines_out)


def fetch_menu_pdf(url: str, session: Optional[requests.Session] = None) -> bytes:
    """Download a PDF from a URL and return the raw bytes."""
    session = session or requests.Session()
    r = session.get(url)
    r.raise_for_status()
    return r.content


def extract_pdf_text(pdf_bytes: bytes) -> List[List[List[str]]]:
    """Extract tables from all pages of a PDF as nested lists."""
    tables = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            tables.append(page.extract_table() or [])
    return tables


def find_daily_menu(
    tables: List[List[List[str]]], date: Optional[datetime] = None
) -> List[str]:
    """Search the PDF tables for today's menu row."""
    date_str = (date or datetime.now(ZoneInfo("Europe/Berlin"))).strftime("%d.%m.%Y")
    for page in tables:
        for row in page:
            if any(date_str in col for col in row if col):
                return row
    return []


# --- Main ---
if __name__ == "__main__":
    url = "https://desy.myalsterfood.de/download/en/menu.pdf"

    pdf_tables = extract_pdf_text(fetch_menu_pdf(url))
    daily_menu = find_daily_menu(pdf_tables)

    if daily_menu:
        header = pdf_tables[0][0]  # first row is header
        print(clean_menu_text(header, daily_menu))
    else:
        print("Today's menu not found.")
