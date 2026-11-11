# social_media_analysis

Daily tracking of a public Instagram account (`beyhankandemir_`) to understand
which posts and events drive engagement.

## What it collects

Every run (daily via GitHub Actions, or `python main.py`) appends one snapshot:

| File | One row per | Columns |
|---|---|---|
| `data/<user>_follower_history.csv` | day | `date`, `follower_count` |
| `data/<user>_post_metrics.csv` | day × post (latest `RECENT_POST_LIMIT` posts) | `collected_date`, `shortcode`, `posted_at`, `type`, `is_pinned`, `likes`, `comments`, `video_views`, `video_plays`, `caption` |

Post metrics are snapshotted daily, so the same post appears on several days and
its likes/views can be followed over time. Running twice on the same day keeps
the latest values. Metrics Instagram withholds are left empty.

Only public data is collected, without logging in. No follower lists or other
personal data are stored.

## Setup

```bash
pip install -r requirements.txt
python main.py
```

Settings live in `config.py` (`TARGET_USERNAME`, `RECENT_POST_LIMIT`).

If Instagram blocks the anonymous request, `main.py` exits with code 1 so the
GitHub Actions run shows as failed instead of silently producing no data.
