"""Follower and following counts, entered by hand from the profile.

Business Suite exports only contain new follows per day, not the totals, so
the totals are recorded in data/profile_snapshots.csv as part of the weekly
routine.
"""
from pathlib import Path

import pandas as pd

SNAPSHOTS_PATH = Path(__file__).resolve().parent.parent / "data" / "profile_snapshots.csv"
COLUMNS = ["date", "followers", "following"]


def load_snapshots(path=SNAPSHOTS_PATH):
    if not Path(path).is_file():
        return pd.DataFrame(columns=COLUMNS).astype({"date": "datetime64[ns]", "followers": "Int64",
                                                     "following": "Int64"})
    df = pd.read_csv(path, parse_dates=["date"])
    return df[COLUMNS].astype({"followers": "Int64", "following": "Int64"}).sort_values("date")


def save_snapshot(date, followers, following, path=SNAPSHOTS_PATH):
    """Add a snapshot; a second entry for the same day replaces the first."""
    df = load_snapshots(path)
    df = df[df["date"] != pd.Timestamp(date)]
    row = pd.DataFrame({"date": [pd.Timestamp(date)], "followers": [followers], "following": [following]})
    df = pd.concat([df, row]).sort_values("date") if len(df) else row
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False, encoding="utf-8")


def with_unfollows(snapshots, daily):
    """Add net follower change and estimated unfollows between snapshots.

    Between two snapshots: unfollows ≈ new follows (from Business Suite) − net
    change in followers. Left empty when the exports don't cover every day of
    that interval.
    """
    out = snapshots.copy()
    out["net_change"] = out["followers"].diff()
    out["new_follows"] = pd.NA
    out["unfollows"] = pd.NA
    if daily is None or "follows" not in daily:
        return out
    covered = set(daily.index)
    for i in range(1, len(out)):
        start = out["date"].iloc[i - 1] + pd.Timedelta(days=1)
        end = out["date"].iloc[i]
        days = pd.date_range(start, end, freq="D")
        if len(days) and all(d in covered for d in days):
            follows = int(daily.loc[days, "follows"].sum())
            out.iloc[i, out.columns.get_loc("new_follows")] = follows
            out.iloc[i, out.columns.get_loc("unfollows")] = max(follows - int(out["net_change"].iloc[i]), 0)
    return out
