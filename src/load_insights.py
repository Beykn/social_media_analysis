"""Load daily account metrics exported from Meta Business Suite.

Business Suite exports one CSV per metric. Each file is UTF-16 encoded and
starts with two extra lines before the real header:

    sep=,
    "Reach"
    "Date","Primary"
    "2026-11-04T01:00:00","25"

Put every export in its own folder under data/raw/ (e.g.
data/raw/2026-11-04_2026-11-10/). Newer folders win when exports overlap.
"""
import csv
import io
import re
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# Export titles mapped to short column names. Unknown titles (e.g. a Turkish
# interface) fall back to a slug of the title, so new metrics still load.
METRIC_NAMES = {
    "Reach": "reach",
    "Views": "views",
    "Content interactions": "interactions",
    "Instagram profile visits": "profile_visits",
    "Instagram follows": "follows",
    "Instagram link clicks": "link_clicks",
}

METRIC_ORDER = list(METRIC_NAMES.values())


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _decode(raw):
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def read_export(path):
    """Return (metric_name, Series indexed by date) for one exported CSV."""
    return parse_export(Path(path).read_bytes())


def save_exports(files, raw_dir=RAW_DIR):
    """Store uploaded exports in data/raw/<first-day>_<last-day>/.

    `files` is a list of (file_name, bytes). Every file is parsed first so a
    file that is not a Business Suite export is rejected before anything is
    written. Returns (folder, [metric names]).
    """
    parsed = [(name, raw, parse_export(raw)) for name, raw in files]
    start = min(s.index.min() for _, _, (_, s) in parsed).date()
    end = max(s.index.max() for _, _, (_, s) in parsed).date()
    folder = Path(raw_dir) / f"{start}_{end}"
    folder.mkdir(parents=True, exist_ok=True)
    for name, raw, _ in parsed:
        (folder / Path(name).name).write_bytes(raw)
    return folder, [metric for _, _, (metric, _) in parsed]


def parse_export(raw):
    """Parse the bytes of one exported CSV into (metric_name, Series)."""
    lines = _decode(raw).splitlines()
    if lines and lines[0].lower().startswith("sep="):
        lines = lines[1:]
    title = next(csv.reader([lines[0]]))[0]
    metric = METRIC_NAMES.get(title, _slug(title))

    df = pd.read_csv(io.StringIO("\n".join(lines[1:])))
    # Timestamps carry a timezone-shifted hour (T01:00:00); only the day matters.
    dates = pd.to_datetime(df["Date"].astype(str).str[:10])
    values = pd.to_numeric(df["Primary"], errors="coerce")
    return metric, pd.Series(values.values, index=dates, name=metric)


def load_daily_metrics(raw_dir=RAW_DIR):
    """One row per day, one column per metric.

    Business Suite leaves out days with a value of 0 (e.g. no new follows), so
    days missing inside an export's date range are filled with 0. Days outside
    every export stay missing.
    """
    folders = sorted(p for p in Path(raw_dir).iterdir() if p.is_dir())
    if not folders:
        raise FileNotFoundError(f"No export folders found in {raw_dir}")

    frames = []
    for folder in folders:
        series = [read_export(f) for f in sorted(folder.glob("*.csv"))]
        if not series:
            continue
        start = min(s.index.min() for _, s in series)
        end = max(s.index.max() for _, s in series)
        days = pd.date_range(start, end, freq="D")
        batch = pd.DataFrame({m: s.reindex(days, fill_value=0) for m, s in series})
        frames.append(batch)

    combined = pd.concat(frames)
    # Overlapping days: keep the value from the newest export folder.
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    combined.index.name = "date"

    ordered = [c for c in METRIC_ORDER if c in combined] + \
              [c for c in combined if c not in METRIC_ORDER]
    return combined[ordered].astype("Int64")
