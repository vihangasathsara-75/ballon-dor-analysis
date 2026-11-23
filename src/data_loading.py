"""Load Ballon d'Or voting and player-performance tables.

Voting results come from ``data/raw/ballon_dor_voting.csv``. Performance
features default to the downloaded extract at
``data/external/player_performance.csv`` (from
https://github.com/kxnoun/ballondor-predictor). If that file is missing,
it is downloaded at runtime and is not committed.

The labelled SYNTHETIC sample in ``data/sample/`` remains available for
tests only; pass ``--performance-path`` to use it.

A column-mapping step renames incoming performance columns to the
project's canonical names so a different real source does not have to
match this schema exactly.

Example:
    python src/data_loading.py
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VOTING_PATH = REPO_ROOT / "data" / "raw" / "ballon_dor_voting.csv"
DEFAULT_PERFORMANCE_PATH = REPO_ROOT / "data" / "external" / "player_performance.csv"
SYNTHETIC_PERFORMANCE_PATH = (
    REPO_ROOT / "data" / "sample" / "synthetic_player_season_stats.csv"
)
PERFORMANCE_SOURCE_URL = (
    "https://raw.githubusercontent.com/kxnoun/ballondor-predictor/"
    "main/data/final_combined_stats.csv"
)
PERFORMANCE_SOURCE_REPO = "https://github.com/kxnoun/ballondor-predictor"
AWARD_YEARS = [2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024]
DEFAULT_TOP_N = 15

# Metrics that appear as 0.0 in early years because they were not published,
# not because every nominee recorded a true zero. If every value in a year
# is 0 or missing, the whole year is treated as missing.
UNAVAILABLE_IF_ALL_ZERO = ("xg", "xag", "sca", "gca")

# Map common source-column names (including FBref-style abbreviations)
# onto canonical names. Keys are matched case-insensitively.
DEFAULT_PERFORMANCE_COLUMN_MAP: dict[str, str] = {
    "year": "year",
    "award_year": "year",
    "player": "player",
    "player_name": "player",
    "club": "club",
    "squad": "club",
    "team": "club",
    "nationality": "nationality",
    "nation": "nationality",
    "position": "position",
    "pos": "position",
    "position_source": "position_source",
    "appearances": "appearances",
    "apps": "appearances",
    "mp": "appearances",
    "minutes": "minutes",
    "min": "minutes",
    "mins": "minutes",
    "goals": "goals",
    "gls": "goals",
    "assists": "assists",
    "ast": "assists",
    "pk": "penalty_goals",
    "sh": "shots",
    "sot": "shots_on_target",
    "crdy": "yellow_cards",
    "crdr": "red_cards",
    "int": "interceptions",
    "tkl": "tackles",
    "xg": "xg",
    "xag": "xag",
    "sca": "sca",
    "gca": "gca",
    "sota": "shots_on_target_against",
    "ga": "goals_against",
    "saves": "saves",
    "save_pct": "save_percentage",
    "cs": "clean_sheets",
    "is_goalkeeper": "is_goalkeeper",
    "result": "result",
    "club_trophies": "club_trophies",
    "trophies": "club_trophies",
    "won_domestic_league": "won_domestic_league",
    "won_ucl": "won_ucl",
    "won_domestic_cup": "won_domestic_cup",
    "won_international_trophy": "won_international_trophy",
    "performance_period": "performance_period",
    "season": "performance_period",
    "data_label": "data_label",
    "source": "source",
    "source_url": "source_url",
}


def _resolve_path(path: str | Path | None, default: Path, env_var: str) -> Path:
    if path is not None:
        return Path(path)
    env_value = os.environ.get(env_var)
    if env_value:
        return Path(env_value)
    return default


def _normalise_column_name(name: str) -> str:
    cleaned = str(name).strip().lower().replace("%", "_pct").replace("-", "_")
    return " ".join(cleaned.split())


def map_performance_columns(
    frame: pd.DataFrame,
    column_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Rename performance columns to the canonical analysis schema.

    ``column_map`` maps source column names to canonical names. Names are
    matched case-insensitively. Unknown columns are left unchanged so
    extra fields from a real extract are preserved.
    """
    mapping = DEFAULT_PERFORMANCE_COLUMN_MAP if column_map is None else column_map
    lookup = {_normalise_column_name(source): target for source, target in mapping.items()}
    rename: dict[str, str] = {}
    used_targets: set[str] = set()
    for column in frame.columns:
        target = lookup.get(_normalise_column_name(column))
        if target and target not in used_targets:
            rename[column] = target
            used_targets.add(target)
    return frame.rename(columns=rename)


def parse_minutes(value: object) -> object:
    """Parse a minutes value that may use comma thousands separators."""
    if pd.isna(value):
        return pd.NA
    if isinstance(value, bool):
        return pd.NA
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).replace(",", "").strip()
    if text == "":
        return pd.NA
    return int(float(text))


def parse_match_result(value: object) -> tuple[object, object, object]:
    """Parse an FBref-style ``W-D-L`` result string into wins, draws, losses."""
    if pd.isna(value):
        return pd.NA, pd.NA, pd.NA
    match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*$", str(value))
    if not match:
        return pd.NA, pd.NA, pd.NA
    return tuple(int(part) for part in match.groups())


def recode_unavailable_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Replace placeholder zeros with NA when a metric is missing for a whole year.

    In this extract, ``xG``, ``xAG``, ``SCA``, and ``GCA`` are 0.0 for every
    player in 2016 and 2017. Those figures were not published, so they are
    treated as missing rather than true zeros. Later years keep genuine zeros
    (for example a goalkeeper with no expected goals).
    """
    out = frame.copy()
    if "year" not in out.columns:
        return out
    for year, index in out.groupby("year").groups.items():
        for column in UNAVAILABLE_IF_ALL_ZERO:
            if column not in out.columns:
                continue
            values = pd.to_numeric(out.loc[index, column], errors="coerce")
            if values.isna().all():
                continue
            if values.fillna(0).eq(0).all():
                out.loc[index, column] = pd.NA
    return out


def prepare_performance_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Parse minutes and results, recode unavailable metrics, and tag the source."""
    out = frame.copy()
    if "minutes" in out.columns:
        out["minutes"] = out["minutes"].map(parse_minutes)
    if "result" in out.columns:
        parsed = out["result"].map(parse_match_result)
        out["wins"] = parsed.map(lambda parts: parts[0])
        out["draws"] = parsed.map(lambda parts: parts[1])
        out["losses"] = parsed.map(lambda parts: parts[2])
        if "appearances" not in out.columns:
            out["appearances"] = pd.to_numeric(out["wins"], errors="coerce") + pd.to_numeric(
                out["draws"], errors="coerce"
            ) + pd.to_numeric(out["losses"], errors="coerce")
    out = recode_unavailable_metrics(out)
    if "data_label" not in out.columns:
        out["data_label"] = "real"
    if "source" not in out.columns:
        out["source"] = (
            "Compiled extract from "
            f"{PERFORMANCE_SOURCE_REPO} (no license stated; original "
            "stats source unstated, columns resemble FBref)."
        )
    if "source_url" not in out.columns:
        out["source_url"] = PERFORMANCE_SOURCE_URL
    return out


def load_voting(path: str | Path | None = None) -> pd.DataFrame:
    """Load the Ballon d'Or voting table."""
    resolved = _resolve_path(path, DEFAULT_VOTING_PATH, "VOTING_PATH")
    if not resolved.exists():
        raise FileNotFoundError(f"Voting file not found: {resolved}")
    data = pd.read_csv(resolved)
    required = {"year", "rank", "player", "points"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"Voting file is missing columns: {sorted(missing)}")
    data.attrs["source_path"] = str(resolved)
    return data


def _ensure_default_performance_file(path: Path) -> None:
    if path.exists():
        return
    if path.resolve() != DEFAULT_PERFORMANCE_PATH.resolve():
        return
    try:
        from .download_performance_data import download_performance_data
    except ImportError:
        from download_performance_data import download_performance_data

    print(f"{path} not found; downloading the performance extract…")
    download_performance_data(output_path=path)


def load_performance(
    path: str | Path | None = None,
    column_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Load player-performance features, mapping columns to canonical names.

    The default path is the downloaded real extract. If it is not present,
    it is fetched into ``data/external/`` (gitignored). Pass ``path`` or
    set ``PERFORMANCE_PATH`` to use a different file, including the
    SYNTHETIC sample reserved for tests.

    A ``data_label`` of SYNTHETIC, if present, is kept so it can be
    propagated into the merged analysis table.
    """
    resolved = _resolve_path(path, DEFAULT_PERFORMANCE_PATH, "PERFORMANCE_PATH")
    _ensure_default_performance_file(resolved)
    if not resolved.exists():
        raise FileNotFoundError(
            f"Performance file not found: {resolved}. "
            "Run python src/download_performance_data.py"
        )
    data = map_performance_columns(pd.read_csv(resolved), column_map=column_map)
    required = {"year", "player"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(
            "Performance file is missing required columns after mapping: "
            f"{sorted(missing)}. Pass column_map to adapt a different schema."
        )
    data = prepare_performance_frame(data)
    data.attrs["source_path"] = str(resolved)
    return data


def _smoke_check(voting_path: str | Path | None, performance_path: str | Path | None) -> int:
    # Imported here so this module can be loaded without a circular import
    # when preprocessing imports load_voting / load_performance.
    try:
        from .preprocessing import build_analysis_dataset, summarise_dataset
    except ImportError:
        from preprocessing import build_analysis_dataset, summarise_dataset

    dataset = build_analysis_dataset(
        voting_path=voting_path,
        performance_path=performance_path,
    )
    print(summarise_dataset(dataset))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Load, clean, and merge voting and performance tables."
    )
    parser.add_argument(
        "--voting-path",
        default=None,
        help=f"Voting CSV (default: {DEFAULT_VOTING_PATH})",
    )
    parser.add_argument(
        "--performance-path",
        default=None,
        help=(
            "Performance CSV (default: the downloaded extract at "
            f"{DEFAULT_PERFORMANCE_PATH}, or $PERFORMANCE_PATH if set). "
            f"Use {SYNTHETIC_PERFORMANCE_PATH} only for tests."
        ),
    )
    args = parser.parse_args()
    return _smoke_check(args.voting_path, args.performance_path)


if __name__ == "__main__":
    sys.exit(main())
