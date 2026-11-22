"""Collect men's Ballon d'Or voting tables from Wikipedia year pages.

France Football (the organiser) is the primary source of record. Wikipedia
year pages are used here only as a convenient structured copy of those
published rankings, with their own citations.

This script downloads the English Wikipedia page for each award year,
parses the first ranking table (the men's Ballon d'Or), and writes
``data/raw/ballon_dor_voting.csv``.

The 2020 award was not given (COVID-19 pandemic) and is therefore omitted.

Example:
    python src/collect_voting_data.py
"""

from __future__ import annotations

import re
import sys
import time
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag

YEARS = [2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024]
USER_AGENT = (
    "ballon-dor-analysis/0.1 "
    "(https://github.com/vihangasathsara-75/ballon-dor-analysis; "
    "educational research project)"
)
REQUEST_PAUSE_SECONDS = 1.0
REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "data" / "raw" / "ballon_dor_voting.csv"


def wikipedia_url(year: int) -> str:
    return f"https://en.wikipedia.org/wiki/{year}_Ballon_d%27Or"


def clean_text(value: str) -> str:
    value = re.sub(r"\[[^\]]*\]", "", value)  # footnote markers such as [a]
    return re.sub(r"\s+", " ", value).strip()


def first_link_text(cell: Tag) -> str:
    for anchor in cell.find_all("a"):
        text = clean_text(anchor.get_text(" ", strip=True))
        if text and not text.startswith("["):
            return text
    return clean_text(cell.get_text(" ", strip=True))


def nationality_from_cell(cell: Tag) -> str | None:
    for image in cell.find_all("img"):
        alt = (image.get("alt") or "").strip()
        if alt and alt.lower() not in {"flag", ""}:
            return alt
    text = clean_text(cell.get_text(" ", strip=True))
    return text or None


def expand_rowspan(table: Tag) -> list[list[Tag]]:
    """Expand rowspans/colspans so each logical row has a cell per column."""
    occupancy: dict[tuple[int, int], Tag] = {}
    grid: list[list[Tag]] = []

    for row_index, row in enumerate(table.find_all("tr")):
        cells = row.find_all(["th", "td"], recursive=False)
        grid_row: list[Tag] = []
        col_index = 0
        cell_iter = iter(cells)
        while True:
            if (row_index, col_index) in occupancy:
                grid_row.append(occupancy[(row_index, col_index)])
                col_index += 1
                continue
            try:
                cell = next(cell_iter)
            except StopIteration:
                break
            rowspan = int(cell.get("rowspan", 1) or 1)
            colspan = int(cell.get("colspan", 1) or 1)
            for offset in range(colspan):
                grid_row.append(cell)
                for down in range(1, rowspan):
                    occupancy[(row_index + down, col_index + offset)] = cell
            col_index += colspan
        if grid_row:
            grid.append(grid_row)
    return grid


def header_index(headers: list[str], *names: str) -> int | None:
    lowered = [header.lower() for header in headers]
    for name in names:
        for index, header in enumerate(lowered):
            if name == header or name in header:
                return index
    return None


def parse_mens_ranking(html: str, year: int) -> list[dict]:
    """Parse the first wikitable, which is the men's Ballon d'Or ranking."""
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table", class_="wikitable")
    if not tables:
        raise RuntimeError(f"No wikitables found for {year}")

    # Cross-check with pandas.read_html that a 30-row ranking table is present.
    html_tables = pd.read_html(StringIO(html))
    ranking_shapes = [
        table.shape
        for table in html_tables
        if any("rank" in str(col).lower() for col in table.columns)
        and any("player" in str(col).lower() for col in table.columns)
        and any("point" in str(col).lower() for col in table.columns)
    ]
    if not ranking_shapes:
        raise RuntimeError(f"pandas.read_html found no ranking table for {year}")

    grid = expand_rowspan(tables[0])
    headers = [clean_text(cell.get_text(" ", strip=True)).lower() for cell in grid[0]]
    if sum(1 for header in headers if header) <= 1 and len(grid) > 1:
        headers = [clean_text(cell.get_text(" ", strip=True)).lower() for cell in grid[1]]
        data_rows = grid[2:]
    else:
        data_rows = grid[1:]

    i_rank = header_index(headers, "rank")
    i_player = header_index(headers, "player")
    i_nationality = header_index(headers, "nationality")
    i_position = header_index(headers, "position")
    i_club = header_index(headers, "club(s)", "club")
    i_points = header_index(headers, "points")
    if i_player is None or i_points is None:
        raise RuntimeError(f"Missing expected columns for {year}: {headers}")

    source_url = wikipedia_url(year)
    records: list[dict] = []
    for row in data_rows:
        if i_player >= len(row) or i_points >= len(row):
            continue
        player = first_link_text(row[i_player])
        if not player or player.lower() in {"rank", "player"}:
            continue

        points_digits = re.sub(r"[^\d]", "", clean_text(row[i_points].get_text(" ", strip=True)))
        points = int(points_digits) if points_digits else None

        rank = None
        if i_rank is not None and i_rank < len(row):
            rank_digits = re.sub(r"[^\d]", "", clean_text(row[i_rank].get_text(" ", strip=True)))
            rank = int(rank_digits) if rank_digits else None

        if i_nationality is not None and i_nationality < len(row):
            nationality = nationality_from_cell(row[i_nationality])
        else:
            nationality = nationality_from_cell(row[i_player])

        position = None
        if i_position is not None and i_position < len(row):
            position = clean_text(row[i_position].get_text(" ", strip=True)) or None

        club = None
        if i_club is not None and i_club < len(row):
            club_cell = row[i_club]
            flag_alts = {
                (image.get("alt") or "").strip()
                for image in club_cell.find_all("img")
                if (image.get("alt") or "").strip()
            }
            club_links = []
            for anchor in club_cell.find_all("a"):
                text = clean_text(anchor.get_text(" ", strip=True))
                if not text or text.startswith("[") or text in flag_alts:
                    continue
                if text not in club_links:
                    club_links.append(text)
            club = " / ".join(club_links) if club_links else (
                clean_text(club_cell.get_text(" ", strip=True)) or None
            )

        if not player and points is None:
            continue

        records.append(
            {
                "year": year,
                "rank": rank,
                "player": player,
                "nationality": nationality,
                "club": club,
                "points": points,
                "position": position,
                "source_url": source_url,
                "source": "Wikipedia (structured copy of France Football rankings)",
            }
        )

    if len(records) < 25:
        raise RuntimeError(f"Expected about 30 nominees for {year}, found {len(records)}")
    return records


def fetch_year(year: int, session: requests.Session) -> list[dict]:
    url = wikipedia_url(year)
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return parse_mens_ranking(response.text, year)


def collect(years: list[int] = YEARS) -> pd.DataFrame:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    frames: list[dict] = []
    for index, year in enumerate(years):
        print(f"Fetching {year}…", flush=True)
        frames.extend(fetch_year(year, session))
        if index < len(years) - 1:
            time.sleep(REQUEST_PAUSE_SECONDS)
    data = pd.DataFrame(frames)
    data["rank"] = data.groupby("year")["rank"].ffill()
    data["points"] = data.groupby("year")["points"].ffill()
    data["rank"] = data["rank"].astype(int)
    data["points"] = data["points"].astype(int)
    column_order = [
        "year",
        "rank",
        "player",
        "nationality",
        "club",
        "points",
        "position",
        "source_url",
        "source",
    ]
    return data[column_order]


def main() -> int:
    data = collect()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {len(data)} rows to {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(data.groupby("year").size().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
