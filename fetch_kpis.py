#!/usr/bin/env python3
"""
Kumo Engine KPI — daily PyPI download tracker.
Fetches cumulative downloads from pypistats.org, appends to CSV,
regenerates an HTML dashboard with a Downloads Over Time chart.
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).parent
CSV_PATH = SCRIPT_DIR / "kumo_engine_kpis.csv"
HTML_PATH = SCRIPT_DIR / "dashboard.html"

PYPI_PACKAGE = "kumo-engine"
FIELDS = ["date", "pypi_daily", "pypi_cumulative"]


def _get_json(url: str) -> dict:
    headers = {"Accept": "application/json", "User-Agent": "NVIDIA-KPI-Tracker/1.0"}
    req = Request(url, headers=headers)
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def fetch_pypi_downloads() -> int:
    """Fetch cumulative PyPI downloads for kumo-engine."""
    try:
        data = _get_json(
            f"https://pypistats.org/api/packages/{PYPI_PACKAGE}/overall?mirrors=true"
        )
        return sum(row.get("downloads", 0) for row in data.get("data", []))
    except Exception as e:
        print(f"  [warn] PyPI fetch failed: {e}", file=sys.stderr)
        return 0


def load_csv() -> list[dict]:
    if not CSV_PATH.exists():
        return []
    with open(CSV_PATH, newline="") as f:
        return list(csv.DictReader(f))


def save_csv(rows: list[dict]):
    with open(CSV_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def embed_csv_into_html():
    """Replace CSV_RAW block inside dashboard.html with latest CSV data."""
    import re
    if not HTML_PATH.exists():
        print("  [warn] dashboard.html not found, skipping embed")
        return
    csv_text = CSV_PATH.read_text().strip()
    html = HTML_PATH.read_text()
    html = re.sub(
        r"(const CSV_RAW = `).*?(`)",
        lambda m: m.group(1) + csv_text + m.group(2),
        html,
        flags=re.DOTALL,
    )
    HTML_PATH.write_text(html)
    print(f"✅ Embedded {len(csv_text.splitlines())-1} data rows into dashboard.html")


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = load_csv()

    if rows:
        print(f"Loaded {len(rows)} rows from {CSV_PATH}")

    # Upsert: replace today's row if it exists
    existing_dates = {r["date"] for r in rows}

    print(f"📊 Fetching KPIs for {today} ...")
    print("  → PyPI downloads ...")
    pypi_cumulative = fetch_pypi_downloads()

    # Compute daily delta
    prev_cumulative = int(rows[-1]["pypi_cumulative"]) if rows else 0
    if today in existing_dates:
        # Re-fetch: use the row before today for delta
        non_today = [r for r in rows if r["date"] != today]
        prev_cumulative = int(non_today[-1]["pypi_cumulative"]) if non_today else 0

    pypi_daily = max(0, pypi_cumulative - prev_cumulative)

    new_row = {
        "date": today,
        "pypi_daily": pypi_daily,
        "pypi_cumulative": pypi_cumulative,
    }

    if today in existing_dates:
        rows = [new_row if r["date"] == today else r for r in rows]
        print(f"✅ Updated row for {today} in {CSV_PATH}")
    else:
        rows.append(new_row)
        print(f"✅ Appended row to {CSV_PATH}")

    print(f"   PyPI cumulative={pypi_cumulative}  daily={pypi_daily}")

    save_csv(rows)

    # Re-embed CSV into HTML dashboard
    print("🌐 Updating HTML dashboard ...")
    embed_csv_into_html()


if __name__ == "__main__":
    main()
