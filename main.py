import sys

from config import TARGET_USERNAME, follower_history_path, post_metrics_path
from src.collect_data import get_profile, get_recent_posts
from src.save_data import save_count_to_csv, save_post_metrics_to_csv
from src.data_cleaning import remove_duplicates
from src.report_generator import generate_weekly_report


def start(username=TARGET_USERNAME):
    """Collect today's snapshot. Returns False if any part failed."""
    profile = get_profile(username)
    if profile is None:
        print("Failed to retrieve the profile.")
        return False

    save_count_to_csv(profile.followers, username)
    remove_duplicates(follower_history_path(username), subset=["date"])

    posts = get_recent_posts(profile)
    if not posts:
        print("Failed to retrieve post metrics.")
        return False

    save_post_metrics_to_csv(posts, username)
    remove_duplicates(post_metrics_path(username), subset=["collected_date", "shortcode"])
    return True


def report():
    report = generate_weekly_report()
    if report:
        print(report)
    else:
        print("Failed to generate the weekly report.")


if __name__ == "__main__":
    ok = start()
    report()
    # A non-zero exit makes the GitHub Actions run show as failed instead of
    # silently succeeding without new data.
    sys.exit(0 if ok else 1)
