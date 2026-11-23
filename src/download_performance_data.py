"""Download the compiled player-performance extract used in this analysis.

The file comes from the public GitHub project
https://github.com/kxnoun/ballondor-predictor
(``data/final_combined_stats.csv``). That repository states no license and
does not name its underlying stats source. Column names resemble FBref,
but that origin is not confirmed here.

The CSV is saved under ``data/external/``, which is gitignored. Run this
script (or let ``load_performance`` download it on first use) rather than
committing the file.

Example:
    python src/download_performance_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_REPO = "https://github.com/kxnoun/ballondor-predictor"
SOURCE_URL = (
    "https://raw.githubusercontent.com/kxnoun/ballondor-predictor/"
    "main/data/final_combined_stats.csv"
)
OUTPUT_PATH = REPO_ROOT / "data" / "external" / "player_performance.csv"
AWARD_YEARS = [2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024]
USER_AGENT = (
    "ballon-dor-analysis/0.1 "
    "(https://github.com/vihangasathsara-75/ballon-dor-analysis; "
    "educational research project)"
)


def download_performance_data(
    url: str = SOURCE_URL,
    output_path: Path = OUTPUT_PATH,
    years: list[int] | None = None,
) -> Path:
    """Download the extract, keep the analysis years, and write a local CSV."""
    years = years if years is not None else AWARD_YEARS
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()

    from io import StringIO

    raw = pd.read_csv(StringIO(response.text))
    if "Year" not in raw.columns:
        raise ValueError(f"Unexpected columns in {url}: {list(raw.columns)}")
    filtered = raw[raw["Year"].isin(years)].copy()
    if filtered.empty:
        raise ValueError(f"No rows found for years {years} in {url}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    filtered.to_csv(output_path, index=False)
    counts = filtered.groupby("Year").size().to_dict()
    print(f"Downloaded {len(raw)} rows from {url}")
    print(f"Wrote {len(filtered)} rows for years {years} to {output_path}")
    print(f"Rows per year: {counts}")
    return output_path


def main() -> int:
    download_performance_data()
    return 0


if __name__ == "__main__":
    sys.exit(main())
