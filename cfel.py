import re
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

CFEL_URL = "https://www.stwhh.de/gastronomie/mensen-cafes-weiteres/mensa/cafe-cfel"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MenuScraper/1.0; +https://example.com/bot)"
}

PRICE_RE = re.compile(r"(\d+[.,]\d{2})\s*€")
paren_re = re.compile(r"\s*\([^)]*\)")
translator = GoogleTranslator(source="auto", target="en")


def clean_text(s: str) -> str:
    # 1) remove parentheses blocks
    no_paren = paren_re.sub("", s)
    # 2) normalize whitespace and commas
    cleaned = re.sub(r"\s+,", ",", no_paren)  # fix stray space before comma
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()  # collapse multiple spaces
    # optional: ensure commas are followed by a single space
    cleaned = re.sub(r",\s*", ", ", cleaned)
    return cleaned


def translate(s: str) -> str:
    cleaned = clean_text(s)
    # translate if there's non-ASCII or if language is not English
    try:
        translated = translator.translate(cleaned)
        return translated
    except Exception as e:
        # fallback: return cleaned text if translation fails
        print("Translation failed, returning cleaned text. Error:", e)
        return cleaned


def parse_price(text):
    """Return float price or None. Handles '4,30 €' -> 4.30"""
    m = PRICE_RE.search(text)
    if not m:
        return None
    s = m.group(1).replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def scrape_headlines_and_prices(url):
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "html.parser")

    results = []
    for meal in soup.select("div.singlemeal"):
        item = {"headline": None, "student_price": None, "employee_price": None}

        # headline
        h = meal.select_one("h5.singlemeal__headline")
        if h:
            cleaned_text = clean_text(" ".join(h.get_text(" ", strip=True).split()))
            item["headline"] = translate(cleaned_text)

        # find price dd elements inside this meal
        # usually there are dd elements with the text and a nested span containing the price
        dd_elements = meal.select("dd.dlist__item, .singlemeal__bottom dd")

        # First try to match by label words (Studierende / Bedienstete / Bedienstete)
        for dd in dd_elements:
            text = dd.get_text(" ", strip=True)
            price = parse_price(text)
            lower = text.lower()
            if price is not None:
                if "stud" in lower or "studierende" in lower or "student" in lower:
                    item["student_price"] = price
                elif (
                    "bedienst" in lower
                    or "bedienstete" in lower
                    or "mitarbeit" in lower
                    or "bedienstete" in lower
                    or "gäste" in lower
                    and False
                ):
                    # we specifically check for employee-like words; 'gäste' is guests so we DON'T map it to employee
                    item["employee_price"] = price
                elif (
                    "bedienstete" in lower
                    or "bedienstete" in lower
                    or "bediensteten" in lower
                    or "bedienst" in lower
                ):
                    item["employee_price"] = price

        # Fallback: if we didn't find by labels, try positional fallback:
        # On this site the order seems to be: Studierende, Bedienstete, Gäste
        if item["student_price"] is None or item["employee_price"] is None:
            # extract all prices in order
            prices_in_order = []
            for dd in dd_elements:
                p = parse_price(dd.get_text(" ", strip=True) or "")
                if p is not None:
                    prices_in_order.append(p)
            if len(prices_in_order) >= 2:
                if item["student_price"] is None:
                    item["student_price"] = prices_in_order[0]
                if item["employee_price"] is None:
                    item["employee_price"] = prices_in_order[1]

        results.append(item)

    return results


def format_menus(
    meals,
    special_first: bool = False,
    start_index: int = 1,
) -> str:
    lines = []
    for idx, item in enumerate(meals, start=start_index):
        headline = item.get("headline", "").strip().rstrip(".")
        student_price = item.get("student_price")
        employee_price = item.get("employee_price")

        # format both prices if available
        if student_price is not None and employee_price is not None:
            price_str = f"{student_price:.2f}/{employee_price:.2f}€"
        elif student_price is not None:
            price_str = f"{student_price:.2f}€"
        elif employee_price is not None:
            price_str = f"{employee_price:.2f}€"
        else:
            price_str = "N/A"

        if special_first and idx == start_index:
            label = "Special Menu"
        else:
            label = f"Menu {idx}"

        line = f"{label} {price_str}: {headline}."
        lines.append(line)

    return "\n".join(lines)


if __name__ == "__main__":
    data = scrape_headlines_and_prices(CFEL_URL)
    print(format_menus(data))
