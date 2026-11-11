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

## Web app

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at http://localhost:8501 with three tabs:

- **Funnel (Huni):** the last 7 days against the average of the previous
  4 weeks, the reach → profile visit → follow funnel, and a weekly or daily
  trend for any metric. Changes from the list are drawn as dashed lines.
- **Changes (Değişiklikler):** an editable list of what was changed on the
  account (start/end date, category, target metric, expectation). Each change
  is evaluated by comparing the period after it with the same-length period
  before it, with warnings when there is too little data to trust the result.
  Stored in `data/changes.csv`.
- **Upload (Veri yükle):** drop the CSVs of one Business Suite export; they are
  saved to `data/raw/<first-day>_<last-day>/`.

Weeks are 7-day blocks counted back from the latest day of data, so they line
up with "last 7 days" exports.

### Weekly routine

1. In Meta Business Suite open **Insights**, export the last 7 days as CSV and
   upload the files in the app.
2. Add any change you made to the account to the change list.
3. Judge a change only after it has run for 2–4 weeks; follows are rare on a
   small account, so a single week says little.

A text summary and a static chart are also available with `python main.py`
(writes `reports/daily_metrics.png`).

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
