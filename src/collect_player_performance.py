"""Attempt to collect official player-season stats from FBref (Opta).

This is not the default performance source. The analysis pipeline uses the
compiled extract from kxnoun/ballondor-predictor (see
``src/download_performance_data.py``). This script remains the planned
collector for a first-party official extract if FBref becomes reachable.

France Football voting records are collected separately. This script is the
planned collector for official individual performance features:

- FBref (Opta) for goals, assists, minutes, appearances, position, and club
- Transfermarkt for team trophies (not scraped here; see the notes below)

FBref does not offer a public API. The script requests the public "Big 5
European Leagues" standard player-stats tables with a polite user agent.
Those pages do not cover every nominee (for example Inter Miami in 2023, or
cup and international matches), and FBref often blocks automated requests.

If a request is blocked or a table cannot be parsed, the script reports the
failure and does **not** write invented numbers. It never labels synthetic
values as FBref or Transfermarkt data.

Example:
    python src/collect_player_performance.py
"""

from __future__ import annotations

import sys
import time
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "data" / "raw" / "player_performance.csv"
USER_AGENT = (
    "ballon-dor-analysis/0.1 "
    "(https://github.com/vihangasathsara-75/ballon-dor-analysis; "
    "educational research project)"
)
REQUEST_PAUSE_SECONDS = 1.5

# Award-year to FBref season pages that overlap the relevant period.
# 2016-2021 awards used a calendar year; from 2022 the award uses the season.
FBREF_SEASONS = [
    "2015-2016",
    "2016-2017",
    "2017-2018",
    "2018-2019",
    "2019-2020",
    "2020-2021",
    "2021-2022",
    "2022-2023",
    "2023-2024",
]


def fbref_url(season: str) -> str:
    return (
        "https://fbref.com/en/comps/Big5/"
        f"{season}/stats/players/{season}-Big-5-European-Leagues-Stats"
    )


def fetch_season(season: str, session: requests.Session) -> tuple[str, pd.DataFrame | None, str]:
    url = fbref_url(season)
    try:
        response = session.get(url, timeout=30)
    except requests.RequestException as exc:
        return url, None, f"request_error:{exc.__class__.__name__}"
    if response.status_code != 200:
        return url, None, f"http_{response.status_code}"
    try:
        tables = pd.read_html(StringIO(response.text))
    except ValueError:
        return url, None, "no_tables_parsed"
    if not tables:
        return url, None, "no_tables_parsed"
    # Prefer the largest table; FBref pages include several stats tables.
    table = max(tables, key=lambda frame: frame.shape[0] * max(frame.shape[1], 1))
    table = table.copy()
    table["fbref_season"] = season
    table["source_url"] = url
    table["source"] = "FBref (Opta)"
    return url, table, "ok"


def main() -> int:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html"})

    print("Attempting FBref Big 5 European Leagues standard player-stats tables.")
    print("Transfermarkt trophy pages are not requested in this run.\n")

    frames: list[pd.DataFrame] = []
    failures: list[tuple[str, str, str]] = []
    for index, season in enumerate(FBREF_SEASONS):
        url, table, status = fetch_season(season, session)
        if table is None:
            print(f"  {season}: FAILED ({status})  {url}")
            failures.append((season, status, url))
        else:
            print(f"  {season}: OK ({table.shape[0]} rows)  {url}")
            frames.append(table)
        if index < len(FBREF_SEASONS) - 1:
            time.sleep(REQUEST_PAUSE_SECONDS)

    if not frames:
        print(
            "\nNo FBref tables were collected. Not writing "
            f"{OUTPUT_PATH.relative_to(REPO_ROOT)}."
        )
        print(
            "Do not invent replacement numbers. For pipeline demos, use the "
            "clearly labelled SYNTHETIC sample:\n"
            "  python src/generate_sample_data.py"
        )
        return 1

    combined = pd.concat(frames, ignore_index=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUTPUT_PATH, index=False)
    print(f"\nWrote {len(combined)} rows to {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    if failures:
        print(f"{len(failures)} season page(s) failed and were omitted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
