import os

import pandas as pd


def remove_duplicates(file_path, subset=("date",)):
    """Keep one row per key when the script runs more than once a day.

    The last row wins, so a re-run replaces the day's earlier value with the
    fresher one.
    """
    if not os.path.isfile(file_path):
        return
    # convert_dtypes keeps counts as integers even when a column has blanks
    # (otherwise pandas rewrites 3400 as 3400.0).
    df = pd.read_csv(file_path).convert_dtypes()
    df_cleaned = df.drop_duplicates(subset=list(subset), keep="last")
    df_cleaned.to_csv(file_path, index=False)
