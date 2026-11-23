"""Load Ballon d'Or voting and player-performance tables.

Voting results come from ``data/raw/ballon_dor_voting.csv``. Performance
features default to the labelled SYNTHETIC sample at
``data/sample/synthetic_player_season_stats.csv``. Pass a different
``performance_path`` (or set ``PERFORMANCE_PATH``) when a real FBref /
Transfermarkt extract is available.

A column-mapping step renames incoming performance columns to the
project's canonical names so a real source does not have to match the
sample schema exactly.

Example:
    python src/data_loading.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VOTING_PATH = REPO_ROOT / "data" / "raw" / "ballon_dor_voting.csv"
DEFAULT_PERFORMANCE_PATH = (
    REPO_ROOT / "data" / "sample" / "synthetic_player_season_stats.csv"
)

# Canonical performance columns expected after mapping.
CANONICAL_PERFORMANCE_COLUMNS = [
    "year",
    "player",
    "club",
    "nationality",
    "position",
    "position_source",
    "appearances",
    "minutes",
    "goals",
    "assists",
    "club_trophies",
    "won_domestic_league",
    "won_ucl",
    "won_domestic_cup",
    "won_international_trophy",
    "performance_period",
    "data_label",
    "source",
]

# Map common source-column names (including FBref-style abbreviations)
# onto the canonical names above. Keys are matched case-insensitively.
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
    return " ".join(str(name).strip().lower().replace("-", "_").split())


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


def load_performance(
    path: str | Path | None = None,
    column_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Load player-performance features, mapping columns to the canonical names.

    The default path is the SYNTHETIC sample. Point ``path`` (or the
    ``PERFORMANCE_PATH`` environment variable) at a real extract later.
    A ``data_label`` of SYNTHETIC, if present, is kept so it can be
    propagated into the merged analysis table.
    """
    resolved = _resolve_path(path, DEFAULT_PERFORMANCE_PATH, "PERFORMANCE_PATH")
    if not resolved.exists():
        raise FileNotFoundError(f"Performance file not found: {resolved}")
    data = map_performance_columns(pd.read_csv(resolved), column_map=column_map)
    required = {"year", "player"}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(
            "Performance file is missing required columns after mapping: "
            f"{sorted(missing)}. Pass column_map to adapt a different schema."
        )
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
            "Performance CSV (default: the SYNTHETIC sample, or "
            "$PERFORMANCE_PATH if set)"
        ),
    )
    args = parser.parse_args()
    return _smoke_check(args.voting_path, args.performance_path)


if __name__ == "__main__":
    sys.exit(main())
