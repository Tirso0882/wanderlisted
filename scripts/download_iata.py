"""Rebuild src/data/iata_codes.csv from the CURRENT OurAirports dataset.

WHY: the committed snapshot was stale and lossy. It was missing BER (Berlin
Brandenburg, opened 2020), still listed closed airports like THF (Tempelhof,
closed 2008) as active, collapsed every `type` to the string "airport", and
dropped `scheduled_service`. Because the closed/size signals were gone, the
lookup tool resolved "Berlin" to a defunct airport (Tempelhof — its historic
name literally contains "International", which the old heuristic preferred).

WHAT THIS DOES: pulls the live OurAirports `airports.csv` + `countries.csv`,
drops `type == "closed"` rows (closed airports also have their IATA cleared
upstream, so this is belt-and-suspenders), and writes the local file WITH the
`type` and `scheduled_service` columns preserved so `lookup_iata_code` can
exclude closed airports and prefer real, scheduled, commercial ones.

Source (official, daily-updated mirror): https://ourairports.com/data/

Run: .venv/bin/python scripts/download_iata.py
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import httpx

# Trust the OS certificate store (public CAs + corporate proxy) the secure way —
# same pattern the rest of the repo uses; never disable verification.
import truststore

truststore.inject_into_ssl()

_AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
_COUNTRIES_URL = "https://davidmegginson.github.io/ourairports-data/countries.csv"
_OUT_PATH = Path(__file__).resolve().parent.parent / "src" / "data" / "iata_codes.csv"
_COUNTRIES_OUT_PATH = (
    Path(__file__).resolve().parent.parent / "src" / "data" / "iata" / "countries.csv"
)

# The columns the lookup tool + downstream code rely on, plus the two signals the
# old snapshot threw away (`type`, `scheduled_service`).
_FIELDNAMES = [
    "id",
    "airport_name",
    "city_name",
    "country",
    "iata_code",
    "icao_code",
    "latitude",
    "longitude",
    "type",
    "scheduled_service",
    "source",
]


def _download(url: str) -> str:
    """GET a CSV as text, following redirects, with a generous timeout."""
    resp = httpx.get(url, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def main() -> int:
    print("Downloading OurAirports countries.csv ...")
    countries = {
        row["code"]: row["name"]
        for row in csv.DictReader(io.StringIO(_download(_COUNTRIES_URL)))
    }
    print(f"  {len(countries)} countries")

    print("Downloading OurAirports airports.csv ...")
    airports = list(csv.DictReader(io.StringIO(_download(_AIRPORTS_URL))))
    print(f"  {len(airports)} raw rows")

    out_rows: list[dict[str, str]] = []
    skipped_closed = 0
    for r in airports:
        code = (r.get("iata_code") or "").strip().upper()
        if len(code) != 3 or not code.isalpha():
            continue  # only real 3-letter IATA codes
        airport_type = (r.get("type") or "").strip()
        if airport_type == "closed":
            skipped_closed += 1
            continue  # THE FIX: a closed airport must never be resolvable
        out_rows.append(
            {
                "id": r.get("id", ""),
                "airport_name": r.get("name", ""),
                "city_name": r.get("municipality", ""),
                "country": countries.get(
                    r.get("iso_country", ""), r.get("iso_country", "")
                ),
                "iata_code": code,
                "icao_code": r.get("icao_code", ""),
                "latitude": r.get("latitude_deg", ""),
                "longitude": r.get("longitude_deg", ""),
                "type": airport_type,
                "scheduled_service": (r.get("scheduled_service") or "").strip(),
                "source": "OurAirports",
            }
        )

    with open(_OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)

    _COUNTRIES_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_COUNTRIES_OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["country_name", "iso_code"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(
            {"country_name": name, "iso_code": code}
            for code, name in sorted(countries.items(), key=lambda item: item[1])
        )

    scheduled = sum(1 for r in out_rows if r["scheduled_service"] == "yes")
    print(
        f"\nWrote {len(out_rows)} airports to {_OUT_PATH}\n"
        f"  (skipped {skipped_closed} closed airports; "
        f"{scheduled} have scheduled commercial service)\n"
        f"Wrote {len(countries)} country codes to {_COUNTRIES_OUT_PATH}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
