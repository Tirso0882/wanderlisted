"""Download travel guides from Wikivoyage and save as markdown.

Usage:
    python scripts/download_guides.py                     # Download missing cities (default list)
    python scripts/download_guides.py Tokyo Paris Rome    # Download specific cities (skip existing)
    python scripts/download_guides.py --force             # Re-download all, overwriting existing files

The guides are saved to knowledge_base/destination_guides/ as .md files.
Wikivoyage content is licensed under CC BY-SA 3.0.
"""

import re
import sys
from pathlib import Path

import mwparserfromhell
import requests

GUIDES_DIR = Path(__file__).resolve().parents[1] / "knowledge_base" / "destination_guides"

API_URL = "https://en.wikivoyage.org/w/api.php"

# Wikivoyage blocks requests without a descriptive User-Agent
HEADERS = {
    "User-Agent": "WanderListed/1.0 (travel itinerary assistant; https://github.com/wanderlisted) python-requests"
}

DEFAULT_CITIES = [
    "Tokyo",
    "Paris",
    "Barcelona",
    "Bangkok",
    "Rome",
    "Istanbul",
    "London",
    "New York City",
    "Mexico City",
    "Marrakech",
    "Bogota",
    "Barranquilla",
    "Medellin",
    "Cartagena",
    "Quito",
    "Lima",
    "Santiago",
    "Buenos Aires",
    "Rio de Janeiro",
    "Cape Town",
    "Cairo",
    "Moscow",
    "Warsaw",
    "Wroclaw",
    "poznan",
    "Gdansk",
    "Krakow",
    "Tallinn",
]


def fetch_wikivoyage(page_title: str) -> str | None:
    """Fetch a Wikivoyage article's wikitext via the MediaWiki API."""
    resp = requests.get(
        API_URL,
        params={
            "action": "parse",
            "page": page_title,
            "prop": "wikitext",
            "format": "json",
            "redirects": "true",
        },
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        return None

    return data["parse"]["wikitext"]["*"]


def wikitext_to_markdown(wikitext: str, title: str) -> str:
    """Convert Wikivoyage wikitext to clean markdown."""
    parsed = mwparserfromhell.parse(wikitext)

    # Strip templates, tags, and wiki markup → plain text
    text = parsed.strip_code(collapse=True)

    # Clean up common artifacts
    text = re.sub(r"\n{3,}", "\n\n", text)        # Collapse excess blank lines
    text = re.sub(r"^\s+$", "", text, flags=re.M)  # Remove whitespace-only lines
    text = text.strip()

    # Add title header
    return f"# {title} Travel Guide\n\n{text}\n"


def city_to_filename(city: str) -> str:
    """Convert a city name to its expected .md filename."""
    return city.lower().replace(" ", "_") + ".md"


def download_guide(city: str) -> Path | None:
    """Download a single city guide and save as markdown."""
    # Wikivoyage uses underscores in page titles
    page_title = city.replace(" ", "_")

    print(f"  Downloading: {city} … ", end="", flush=True)
    try:
        wikitext = fetch_wikivoyage(page_title)
    except requests.exceptions.HTTPError as e:
        print(f"HTTP {e.response.status_code} (skipped)")
        return None
    except requests.exceptions.RequestException as e:
        print(f"ERROR: {e} (skipped)")
        return None
    if wikitext is None:
        print("NOT FOUND (skipped)")
        return None

    markdown = wikitext_to_markdown(wikitext, city)

    filename = city_to_filename(city)
    filepath = GUIDES_DIR / filename
    filepath.write_text(markdown, encoding="utf-8")

    word_count = len(markdown.split())
    print(f"OK ({word_count:,} words → {filename})")
    return filepath


def main():
    args = sys.argv[1:]
    force = "--force" in args
    cities = [a for a in args if not a.startswith("-")] or DEFAULT_CITIES

    GUIDES_DIR.mkdir(parents=True, exist_ok=True)

    # Split into already-present vs missing
    if force:
        to_download = cities
        skipped = []
    else:
        to_download = [c for c in cities if not (GUIDES_DIR / city_to_filename(c)).exists()]
        skipped = [c for c in cities if (GUIDES_DIR / city_to_filename(c)).exists()]

    if skipped:
        print(f"Skipping {len(skipped)} already downloaded: {', '.join(skipped)}")

    if not to_download:
        print("All guides already downloaded. Use --force to re-download.")
        return

    print(f"\nDownloading {len(to_download)} Wikivoyage travel guides …\n")

    downloaded = []
    failed = []
    for city in to_download:
        result = download_guide(city)
        if result:
            downloaded.append(city)
        else:
            failed.append(city)

    print(f"\n{'=' * 50}")
    print(f"  Downloaded: {len(downloaded)}/{len(to_download)}")
    if failed:
        print(f"  Failed:     {', '.join(failed)}")
    if skipped:
        print(f"  Skipped:    {len(skipped)} already present")
    print(f"  Output dir: {GUIDES_DIR}")
    print(f"{'=' * 50}")
    print("\n  Content is licensed under CC BY-SA 3.0 (Wikivoyage)")


if __name__ == "__main__":
    main()
