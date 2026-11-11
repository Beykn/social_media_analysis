# social_media_analysis

Analysis of an Instagram account's performance from the metrics Instagram
itself provides, exported from Meta Business Suite.

## Why CSV exports?

The first version scraped public data (follower count, likes, comments) with
`instaloader` on a daily GitHub Actions schedule. Instagram blocks anonymous
requests from data-center IPs, so the scheduled runs kept failing, and scraping
can only see public numbers anyway.

Exports from Meta Business Suite are the account's own insights: reach, views,
profile visits and follows, which explain *why* numbers move, not just *how
much*. The scraping code is still in the git history.

## Usage

1. In Meta Business Suite open **Insights**, pick a date range and export the
   data as CSV.
2. Put the files in a new folder under `data/raw/`, named after the range, e.g.
   `data/raw/2026-11-04_2026-11-10/`. Keep the exported file names as they are.
3. Run:

```bash
pip install -r requirements.txt
python main.py
```

It prints a daily table with derived rates and writes
`reports/daily_metrics.png`.

## Metrics

| Column | Export | Note |
|---|---|---|
| `reach` | Reach | Accounts reached that day. Daily values can't be summed into unique reach. |
| `views` | Views | |
| `interactions` | Content interactions | Likes, comments, saves, shares |
| `profile_visits` | Instagram profile visits | |
| `follows` | Instagram follows | Days with 0 are omitted in the export and filled in as 0 |
| `link_clicks` | Instagram link clicks | |

Derived rates: `engagement_rate_%` = interactions / reach,
`visit_rate_%` = profile visits / reach, `follow_per_visit_%` = follows /
profile visits.

When export folders overlap, the newest folder (by name) wins.
