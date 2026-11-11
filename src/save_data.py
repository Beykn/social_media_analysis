import os
from datetime import datetime

import pandas as pd

from config import TARGET_USERNAME, DATA_DIR, follower_history_path, post_metrics_path


def _append_to_csv(df, filename):
    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
    write_header = not os.path.isfile(filename)
    df.to_csv(filename, mode="a", header=write_header, index=False, encoding="utf-8")


def save_username_to_csv(username_list, target_account=TARGET_USERNAME):
    current_date = datetime.now().strftime("%Y-%m-%d")
    df = pd.DataFrame({
        "date": [current_date] * len(username_list),
        "username": username_list,
    })
    filename = f"{DATA_DIR}/{target_account}_followers_{current_date}.csv"
    df.to_csv(filename, index=False, encoding="utf-8")
    print(f"Data saved to {filename}")


def save_count_to_csv(count, target_account=TARGET_USERNAME):
    current_date = datetime.now().strftime("%Y-%m-%d")
    df = pd.DataFrame({"date": [current_date], "follower_count": [count]})
    filename = follower_history_path(target_account)
    _append_to_csv(df, filename)
    print(f"Follower count saved to {filename}")


def save_post_metrics_to_csv(rows, target_account=TARGET_USERNAME):
    filename = post_metrics_path(target_account)
    _append_to_csv(pd.DataFrame(rows), filename)
    print(f"Metrics of {len(rows)} posts saved to {filename}")
