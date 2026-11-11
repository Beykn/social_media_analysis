from datetime import datetime
from itertools import islice

import instaloader

from config import TARGET_USERNAME, RECENT_POST_LIMIT

bot = instaloader.Instaloader(quiet=True)

POST_TYPES = {
    "GraphImage": "photo",
    "GraphVideo": "video",
    "GraphSidecar": "carousel",
}


def get_profile(username=TARGET_USERNAME):
    """Fetch the public profile once so follower count and posts share one request."""
    try:
        return instaloader.Profile.from_username(bot.context, username)
    except Exception as e:
        print(f"Error fetching profile for {username}: {e}")
        return None


def get_followers(username=TARGET_USERNAME):
    follower_list = []
    profile = instaloader.Profile.from_username(bot.context, username)
    for f in profile.get_followers():
        follower_list.append(f.username)
    return follower_list


def get_follower_count(username=TARGET_USERNAME):
    profile = get_profile(username)
    return profile.followers if profile else None


def _safe(post, attr):
    # Some metrics (e.g. video views) are missing for some post types or get
    # withheld by Instagram; record them as empty instead of failing the run.
    try:
        return getattr(post, attr)
    except Exception:
        return None


def post_to_row(post, collected_date):
    is_video = bool(_safe(post, "is_video"))
    return {
        "collected_date": collected_date,
        "shortcode": post.shortcode,
        "posted_at": post.date_utc.strftime("%Y-%m-%d %H:%M:%S"),
        "type": POST_TYPES.get(post.typename, post.typename),
        "is_pinned": bool(_safe(post, "is_pinned")),
        "likes": _safe(post, "likes"),
        "comments": _safe(post, "comments"),
        "video_views": _safe(post, "video_view_count") if is_video else None,
        "video_plays": _safe(post, "video_play_count") if is_video else None,
        "caption": (_safe(post, "caption") or "").replace("\n", " ").strip(),
    }


def get_recent_posts(profile, limit=RECENT_POST_LIMIT):
    """Snapshot likes, comments and views of the latest posts.

    Pinned posts are listed first by Instagram; they are kept and flagged with
    is_pinned so they can be filtered out during analysis.
    """
    collected_date = datetime.now().strftime("%Y-%m-%d")
    try:
        return [post_to_row(p, collected_date) for p in islice(profile.get_posts(), limit)]
    except Exception as e:
        print(f"Error fetching posts for {profile.username}: {e}")
        return None
