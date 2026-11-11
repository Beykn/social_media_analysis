"""The list of changes made to the account, stored in data/changes.csv."""
from pathlib import Path

import pandas as pd

CHANGES_PATH = Path(__file__).resolve().parent.parent / "data" / "changes.csv"

COLUMNS = ["start_date", "end_date", "category", "description",
           "target_metric", "hypothesis", "result_note"]

CATEGORIES = ["Profil", "İçerik konusu", "Format", "Paylaşım zamanı",
              "Açıklama / hashtag", "Paylaşım sıklığı", "Diğer"]


def load_changes(path=CHANGES_PATH):
    if not Path(path).is_file():
        return pd.DataFrame({c: pd.Series(dtype="datetime64[ns]" if c.endswith("_date") else "object")
                             for c in COLUMNS})
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    for col in COLUMNS:
        if col not in df:
            df[col] = ""
    df = df[COLUMNS]
    for col in ("start_date", "end_date"):
        # datetime64 (not Python dates) so empty cells show as blank, not "None".
        df[col] = pd.to_datetime(df[col].replace("", None), errors="coerce")
    return df


def save_changes(df, path=CHANGES_PATH):
    out = df.copy()
    out = out[out["start_date"].notna() & (out["description"].fillna("").str.strip() != "")]
    for col in ("start_date", "end_date"):
        out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime("%Y-%m-%d")
    out = out.sort_values("start_date")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    out[COLUMNS].to_csv(path, index=False, encoding="utf-8")
    return len(out)
