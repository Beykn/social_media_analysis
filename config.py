TARGET_USERNAME = "beyhankandemir_"

DATA_DIR = "data"

# How many of the most recent posts to snapshot on every run.
RECENT_POST_LIMIT = 12


def follower_history_path(username=TARGET_USERNAME):
    return f"{DATA_DIR}/{username}_follower_history.csv"


def post_metrics_path(username=TARGET_USERNAME):
    return f"{DATA_DIR}/{username}_post_metrics.csv"
