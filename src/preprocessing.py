"""Clean, merge, and enrich voting and performance tables."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

try:
    from .data_loading import load_performance, load_voting
except ImportError:
    from data_loading import load_performance, load_voting

TEXT_COLUMNS = ("player", "club", "nationality", "position")


def normalise_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalise_unicode(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def fold_key(value: str) -> str:
    """Lower-case, unaccented key used to match player names across sources."""
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    folded = re.sub(r"[^a-z0-9]+", " ", without_marks.lower())
    return normalise_whitespace(folded)


def normalise_text_series(series: pd.Series) -> pd.Series:
    def _one(value: object) -> object:
        if pd.isna(value):
            return pd.NA
        text = normalise_unicode(normalise_whitespace(str(value)))
        return text if text else pd.NA

    return series.map(_one)


def add_match_keys(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["player_key"] = normalise_text_series(out["player"]).map(
        lambda value: fold_key(value) if isinstance(value, str) else pd.NA
    )
    if "club" in out.columns:
        out["primary_club"] = normalise_text_series(out["club"]).map(
            lambda value: value.split(" / ")[-1] if isinstance(value, str) else pd.NA
        )
    return out


def clean_voting(voting: pd.DataFrame) -> pd.DataFrame:
    """Normalise identifiers and types in the voting table."""
    out = voting.copy()
    for column in TEXT_COLUMNS:
        if column in out.columns:
            out[column] = normalise_text_series(out[column])
    out["year"] = out["year"].astype(int)
    out["rank"] = out["rank"].astype(int)
    out["points"] = out["points"].astype(int)
    return add_match_keys(out)


def clean_performance(performance: pd.DataFrame) -> pd.DataFrame:
    """Normalise identifiers and keep any synthetic/source flags."""
    out = performance.copy()
    for column in TEXT_COLUMNS:
        if column in out.columns:
            out[column] = normalise_text_series(out[column])
    out["year"] = out["year"].astype(int)
    if "data_label" in out.columns:
        out["data_label"] = normalise_text_series(out["data_label"])
    return add_match_keys(out)


def mark_synthetic(frame: pd.DataFrame) -> pd.Series:
    """Boolean flag that travels with the merged output."""
    label = (
        frame["data_label"].astype("string").str.upper()
        if "data_label" in frame.columns
        else pd.Series(pd.NA, index=frame.index, dtype="string")
    )
    source = (
        frame["source"].astype("string")
        if "source" in frame.columns
        else pd.Series(pd.NA, index=frame.index, dtype="string")
    )
    from_label = label.eq("SYNTHETIC")
    from_source = source.str.contains("SYNTHETIC", case=False, na=False)
    return from_label.fillna(False) | from_source.fillna(False)


def handle_missing_positions(frame: pd.DataFrame) -> pd.DataFrame:
    """Record missing positions without inventing a playing position."""
    out = frame.copy()
    position = (
        out["position"]
        if "position" in out.columns
        else pd.Series(pd.NA, index=out.index)
    )
    out["position"] = position
    out["position_missing"] = out["position"].isna()
    out["position_group"] = out["position"].fillna("Unknown")
    return out


def merge_voting_and_performance(
    voting: pd.DataFrame,
    performance: pd.DataFrame,
) -> pd.DataFrame:
    """Left-join performance features onto voting rows by year and player key."""
    identifier_from_voting = {
        "player",
        "club",
        "nationality",
        "primary_club",
        "source",
        "source_url",
    }
    perf = performance.drop(columns=identifier_from_voting, errors="ignore")
    merged = voting.merge(
        perf,
        on=["year", "player_key"],
        how="left",
        suffixes=("", "_performance"),
        indicator="performance_match",
    )
    if "position_performance" in merged.columns:
        merged["position"] = merged["position"].fillna(merged["position_performance"])
        merged = merged.drop(columns=["position_performance"])
    merged["performance_matched"] = merged["performance_match"].eq("both")
    merged = merged.drop(columns=["performance_match"])
    return merged


def add_derived_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Add rank- and scale-aware columns used in later analysis."""
    out = frame.copy()
    year_points = out.groupby("year")["points"].transform("sum")
    out["points_share"] = out["points"] / year_points
    year_mean = out.groupby("year")["points"].transform("mean")
    year_std = out.groupby("year")["points"].transform("std")
    out["points_year_z"] = (out["points"] - year_mean) / year_std.replace(0, pd.NA)
    year_min = out.groupby("year")["points"].transform("min")
    year_max = out.groupby("year")["points"].transform("max")
    span = (year_max - year_min).replace(0, pd.NA)
    out["points_year_minmax"] = (out["points"] - year_min) / span
    out["is_top3"] = out["rank"] <= 3
    out["is_winner"] = out["rank"] == 1
    out["is_synthetic"] = mark_synthetic(out)
    if "goals" in out.columns and "minutes" in out.columns:
        minutes = pd.to_numeric(out["minutes"], errors="coerce")
        goals = pd.to_numeric(out["goals"], errors="coerce")
        out["goals_per_90"] = (goals * 90) / minutes.replace(0, pd.NA)
    return out


def build_analysis_dataset(
    voting_path: str | Path | None = None,
    performance_path: str | Path | None = None,
    column_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Load, clean, merge, and enrich the analysis table.

    ``performance_path`` is configurable so a real extract can replace
    the SYNTHETIC sample without changing this function's callers.
    """
    voting = clean_voting(load_voting(voting_path))
    performance = clean_performance(
        load_performance(performance_path, column_map=column_map)
    )
    merged = merge_voting_and_performance(voting, performance)
    merged = handle_missing_positions(merged)
    return add_derived_columns(merged)


def summarise_dataset(dataset: pd.DataFrame) -> str:
    """Short human-readable summary for the smoke check."""
    matched = int(dataset["performance_matched"].sum()) if "performance_matched" in dataset.columns else 0
    synthetic = int(dataset["is_synthetic"].sum()) if "is_synthetic" in dataset.columns else 0
    missing_pos = int(dataset["position_missing"].sum()) if "position_missing" in dataset.columns else 0
    years = ", ".join(str(year) for year in sorted(dataset["year"].unique()))
    share_min = dataset["points_share"].min()
    share_max = dataset["points_share"].max()
    share_by_year = dataset.groupby("year")["points_share"].sum()
    share_ok = bool((share_by_year - 1).abs().max() < 1e-9)
    lines = [
        "Analysis dataset smoke check",
        f"  rows: {len(dataset)}  years: {years}",
        f"  performance rows matched: {matched} / {len(dataset)}",
        f"  synthetic rows: {synthetic} / {len(dataset)}",
        f"  missing positions: {missing_pos}",
        f"  points_share range: {share_min:.4f} – {share_max:.4f}"
        f"  (sums to 1 each year: {share_ok})",
        f"  top-3 flag: {int(dataset['is_top3'].sum())} rows",
        f"  winners: {int(dataset['is_winner'].sum())} rows",
    ]
    if "data_label" in dataset.columns:
        labels = dataset["data_label"].fillna("(none)").value_counts().to_dict()
        lines.append(f"  data_label counts: {labels}")
    return "\n".join(lines)
