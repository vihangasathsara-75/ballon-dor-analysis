"""Check collected Ballon d'Or podium points against official references.

France Football (and the official Ballon d'Or site) is the source of record.
``data/raw/podium_reference.csv`` stores podium values that were actually
read from those pages, plus a status for each place:

- verified: the official page published this player's point total
- unverified: the official page was missing, empty, blocked, or did not
  publish points; no reference value is invented

Run after collecting or updating the voting file:

    python src/validate_voting_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
VOTING_PATH = REPO_ROOT / "data" / "raw" / "ballon_dor_voting.csv"
REFERENCE_PATH = REPO_ROOT / "data" / "raw" / "podium_reference.csv"


def load_podium(voting: pd.DataFrame) -> pd.DataFrame:
    podium = voting.sort_values(["year", "rank"]).groupby("year", as_index=False).head(3)
    return podium[["year", "rank", "player", "points"]].rename(columns={"points": "collected_points"})


def compare(voting: pd.DataFrame, reference: pd.DataFrame) -> pd.DataFrame:
    podium = load_podium(voting)
    merged = reference.merge(podium, on=["year", "rank"], how="outer", suffixes=("_ref", "_data"))
    results = []
    for row in merged.itertuples(index=False):
        status = getattr(row, "status", None)
        ref_points = row.reference_points
        collected = row.collected_points
        player_ref = row.player_ref
        player_data = row.player_data

        if pd.isna(status):
            outcome = "missing_reference"
            ok = False
            note = "No official reference row for this collected podium place."
        elif status == "unverified":
            outcome = "unverified"
            ok = True
            note = row.notes if isinstance(row.notes, str) else "Official points were not available."
        elif status == "verified":
            if pd.isna(collected):
                outcome = "missing_collected"
                ok = False
                note = "Reference exists but this place is missing from the collected file."
            elif int(collected) == int(ref_points):
                outcome = "match"
                ok = True
                note = "Collected points match the official reference."
            else:
                outcome = "mismatch"
                ok = False
                note = f"Collected {int(collected)} != official {int(ref_points)}."
        else:
            outcome = f"unknown_status:{status}"
            ok = False
            note = "Unexpected status in the reference file."

        results.append(
            {
                "year": int(row.year) if pd.notna(row.year) else None,
                "rank": int(row.rank) if pd.notna(row.rank) else None,
                "player_collected": player_data if isinstance(player_data, str) else "",
                "player_reference": player_ref if isinstance(player_ref, str) else "",
                "collected_points": None if pd.isna(collected) else int(collected),
                "reference_points": None if pd.isna(ref_points) else int(ref_points),
                "reference_url": row.reference_url if isinstance(row.reference_url, str) else "",
                "publisher": row.publisher if isinstance(row.publisher, str) else "",
                "status": status if isinstance(status, str) else "",
                "outcome": outcome,
                "ok": ok,
                "note": note,
            }
        )
    return pd.DataFrame(results)


def report(results: pd.DataFrame) -> int:
    print("Podium validation (collected Wikipedia tables vs official references)\n")
    failures = 0
    for year, group in results.groupby("year", dropna=False):
        print(f"== {year} ==")
        for row in group.itertuples(index=False):
            flag = "OK" if row.ok else "FAIL"
            official = "n/a" if pd.isna(row.reference_points) else int(row.reference_points)
            collected = "n/a" if pd.isna(row.collected_points) else int(row.collected_points)
            points_bit = f"collected={collected} official={official}"
            player = row.player_collected or row.player_reference or "?"
            print(f"  [{flag}] {row.rank}. {player}  {points_bit}  ({row.outcome})")
            if row.reference_url:
                print(f"         {row.publisher}: {row.reference_url}")
            if row.note:
                print(f"         {row.note}")
            if not row.ok:
                failures += 1
        print()

    n_match = int((results["outcome"] == "match").sum())
    n_unverified = int((results["outcome"] == "unverified").sum())
    n_fail = int((~results["ok"]).sum())
    print(
        f"Summary: {n_match} official point totals matched, "
        f"{n_unverified} places unverified, {n_fail} failures."
    )
    return 1 if failures else 0


def main() -> int:
    if not VOTING_PATH.exists():
        print(f"Missing {VOTING_PATH}. Run src/collect_voting_data.py first.", file=sys.stderr)
        return 2
    if not REFERENCE_PATH.exists():
        print(f"Missing {REFERENCE_PATH}.", file=sys.stderr)
        return 2

    voting = pd.read_csv(VOTING_PATH)
    reference = pd.read_csv(REFERENCE_PATH)
    results = compare(voting, reference)
    return report(results)


if __name__ == "__main__":
    sys.exit(main())
