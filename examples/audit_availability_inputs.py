"""Audit injury snapshots for a Wednesday report without inventing historical states."""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def audit(injuries, schedule):
    regular = schedule.loc[schedule.game_type.eq("REG")].copy()
    regular["day"] = pd.to_datetime(regular.gameday)
    starts = regular.groupby(["season", "week"]).day.min()
    data = injuries.loc[injuries.game_type.eq("REG")].copy()
    result = {
        "rows": len(data),
        "has_date_modified": "date_modified" in data,
        "missing_gsis_ids": int(data.gsis_id.isna().sum()),
    }
    if "date_modified" not in data:
        result["eligible_for_wednesday_backtest"] = False
        return result
    cutoffs = []
    for row in data.itertuples():
        day = starts.loc[(row.season, row.week)]
        wednesday = day - pd.Timedelta(days=int((day.weekday() - 2) % 7))
        cutoffs.append(
            (wednesday + pd.Timedelta(hours=10))
            .tz_localize("America/New_York")
            .tz_convert("UTC")
        )
    modified = pd.to_datetime(data.date_modified, utc=True)
    before = modified.notna() & modified.le(pd.Series(cutoffs, index=data.index))
    result.update(
        timestamped_rows=int(modified.notna().sum()),
        modified_by_wednesday_10et=int(before.sum()),
        fraction_by_wednesday=float(before.mean()),
        eligible_for_wednesday_backtest=False,
    )
    # Even an early modified date is not an archived observation of the entire feed.
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--injuries", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    schedule = pd.read_csv(args.schedule)
    reports = []
    for path in args.injuries:
        data = pd.read_csv(path)
        reports.append(
            {
                "file": path.name,
                "seasons": sorted(map(int, data.season.unique())),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                **audit(data, schedule),
            }
        )
    result = {
        "schedule_sha256": hashlib.sha256(args.schedule.read_bytes()).hexdigest(),
        "reports": reports,
        "decision": "No Wednesday injury backtest: archive pregame observations prospectively.",
    }
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
