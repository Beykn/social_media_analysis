"""Growth funnel calculations shared by the CLI report and the web app.

Funnel: reach (discovery) -> profile visits (interest) -> follows (conversion).
Rates are always computed from summed counts of a period, never by averaging
daily rates, so quiet days don't distort them.
"""
import pandas as pd

LABELS = {
    "reach": "Erişim",
    "views": "Görüntülenme",
    "interactions": "Etkileşim",
    "profile_visits": "Profil ziyareti",
    "follows": "Yeni takip",
    "link_clicks": "Link tıklaması",
    "engagement_rate": "Etkileşim oranı %",
    "visit_rate": "Ziyaret oranı %",
    "follow_rate": "Ziyaret → takip %",
}

# (numerator, denominator) for each derived rate, in percent.
RATES = {
    "engagement_rate": ("interactions", "reach"),
    "visit_rate": ("profile_visits", "reach"),
    "follow_rate": ("follows", "profile_visits"),
}

# Below this many days per period a comparison is reported as too early.
MIN_DAYS = 14
# Below this many follows in either period the follow comparison is noise.
MIN_FOLLOWS = 10


# A day with at least this many follows, and far above a normal day, is a
# bulk recount (e.g. the account switched between private, public or
# professional and Meta counted every follower as new), not real follows.
BULK_FOLLOWS_MIN = 100
BULK_FOLLOWS_FACTOR = 20


def remove_bulk_follows(daily):
    """Blank out bulk-recount days in `follows`.

    Returns (daily, removed) where removed is a Series of the blanked values.
    """
    if "follows" not in daily:
        return daily, pd.Series(dtype="Int64")
    follows = daily["follows"]
    typical = follows[follows > 0].median()
    if pd.isna(typical):
        return daily, pd.Series(dtype="Int64")
    bulk = (follows >= BULK_FOLLOWS_MIN) & (follows > typical * BULK_FOLLOWS_FACTOR)
    bulk = bulk.fillna(False)
    out = daily.copy()
    out.loc[bulk, "follows"] = pd.NA
    return out, follows[bulk]


def bulk_follows_note(removed):
    if not len(removed):
        return None
    days = ", ".join(f"{d:%d.%m.%Y} ({int(v)})" for d, v in removed.items())
    return (f"Şu günlerdeki yeni takip sayısı hesaba katılmadı: {days}. Bu sayılar takipçi toplamına "
            "yakın; hesap gizli/herkese açık ya da profesyonel hesap arasında geçiş yaptığında Meta "
            "tüm takipçileri o gün yeni takip olarak sayıyor.")


def default_trend_metric(daily):
    """Reach once it covers a month, otherwise views (exports of long ranges
    don't include reach)."""
    if "reach" in daily and daily["reach"].notna().sum() >= 28:
        return "reach"
    return "views" if "views" in daily else daily.columns[0]


def label(metric):
    return LABELS.get(metric, metric)


def add_rates(counts):
    """Add percentage rate columns to a frame of summed counts."""
    out = counts.astype(float)
    for name, (num, den) in RATES.items():
        if num in out and den in out:
            out[name] = (out[num] / out[den].where(out[den] > 0) * 100).round(1)
    return out


def weekly(daily):
    """Sum daily metrics into 7-day blocks counted back from the last day.

    Blocks line up with "last 7 days" exports from Business Suite. The oldest
    block can be shorter than 7 days; its length is in the `days` column.
    """
    last = daily.index.max()
    block = ((last - daily.index).days // 7).to_numpy()
    grouped = daily.astype(float).groupby(block)
    # min_count=1: a week with no data for a metric stays empty instead of 0.
    sums = grouped.sum(min_count=1)
    sums["days"] = grouped.size()
    starts = daily.index.to_series().groupby(block).min()
    sums.index = pd.DatetimeIndex(starts.values, name="week_start")
    sums = sums.sort_index()
    return add_rates(sums)


def with_rolling(weeks, column, window=4):
    """Weekly values of one column plus its rolling average over `window` weeks."""
    out = pd.DataFrame({"Haftalık": weeks[column]})
    if column in RATES:
        num, den = RATES[column]
        rolled = weeks[num].rolling(window, min_periods=1).sum() / \
            weeks[den].rolling(window, min_periods=1).sum().where(lambda s: s > 0) * 100
    else:
        rolled = weeks[column].rolling(window, min_periods=1).mean()
    out[f"Son {window} hafta ort."] = rolled.round(1)
    return out


def _rate(frame, num, den):
    """Rate in percent over the rows where both counts are known."""
    both = frame[[num, den]].dropna()
    total = both[den].sum()
    return both[num].sum() / total * 100 if total else float("nan")


def _period_summary(daily, start, end):
    part = daily.loc[start:end].astype(float)
    sums = part.sum(min_count=1)
    values = {m: part[m].mean() for m in daily.columns}
    values.update({r: _rate(part, num, den) for r, (num, den) in RATES.items()
                   if num in part and den in part})
    return len(part), sums, pd.Series(values)


def evaluate_change(daily, start, end=None, window_days=28):
    """Compare the period after a change with the same-length period before it.

    Counts are compared as per-day averages, rates from summed counts.
    Returns (table, notes) where notes lists reasons to be careful.
    """
    start = pd.Timestamp(start)
    last_day = daily.index.max()
    end = pd.Timestamp(end) if end is not None and not pd.isna(end) else None
    after_end = min(end or start + pd.Timedelta(days=window_days - 1), last_day)
    length = (after_end - start).days + 1
    before_start = start - pd.Timedelta(days=max(length, 1))
    before_end = start - pd.Timedelta(days=1)

    notes = []
    if start > last_day:
        return None, ["Bu değişiklik için henüz veri yok."]

    days_before, sums_before, before = _period_summary(daily, before_start, before_end)
    days_after, sums_after, after = _period_summary(daily, start, after_end)

    if days_before == 0:
        return None, ["Değişiklik öncesine ait veri yok; karşılaştırma yapılamıyor."]
    if min(days_before, days_after) < MIN_DAYS:
        notes.append(
            f"Henüz erken: önce {days_before} gün, sonra {days_after} gün veri var. "
            f"Güvenilir bir sonuç için her iki dönemde de en az {MIN_DAYS} gün gerekli."
        )
    if "follows" in sums_before and min(sums_before["follows"], sums_after["follows"]) < MIN_FOLLOWS \
            and not pd.isna(sums_before["follows"]) and not pd.isna(sums_after["follows"]):
        notes.append(
            f"Takip sayısı az (önce {int(sums_before['follows'])}, sonra {int(sums_after['follows'])}); "
            "takip ve dönüşüm oranındaki fark şans eseri olabilir."
        )

    table = pd.DataFrame({"Önce": before, "Sonra": after})
    # Metrics the exports don't cover for this period (e.g. reach) are left out.
    table = table.dropna(how="all")
    table["Değişim %"] = ((table["Sonra"] - table["Önce"]) /
                          table["Önce"].where(table["Önce"] != 0) * 100).round(1)
    table.index = [label(m) for m in table.index]
    shown_start = max(before_start, daily.index.min())
    period = (f"Önce: {shown_start:%d.%m.%Y} – {before_end:%d.%m.%Y} ({days_before} gün) · "
              f"Sonra: {start:%d.%m.%Y} – {after_end:%d.%m.%Y} ({days_after} gün)")
    return table.round(2), [period] + notes


KPI_METRICS = ["reach", "profile_visits", "follows", "follow_rate"]


def last_week_summary(weeks, metrics=KPI_METRICS, compare_weeks=4):
    """Last 7-day block against the average of the blocks before it.

    Returns {metric: (value, change_percent or None)} and the number of
    previous weeks used for the comparison.
    """
    last = weeks.iloc[-1]
    previous = weeks.iloc[:-1].tail(compare_weeks)
    out = {}
    for metric in metrics:
        base = None
        if len(previous):
            base = _rate(previous, *RATES[metric]) if metric in RATES else previous[metric].mean()
        ok = base is not None and not pd.isna(base) and base != 0 and not pd.isna(last[metric])
        out[metric] = (last[metric], (last[metric] - base) / base * 100 if ok else None)
    return out, len(previous)


def funnel_summary(weeks, n_weeks=4):
    """Summed reach, profile visits and follows over the last weeks, with step rates.

    Only weeks where all three are known are used, so the steps describe the
    same people.
    """
    recent = weeks[["reach", "profile_visits", "follows"]].dropna().tail(n_weeks)
    sums = recent[["reach", "profile_visits", "follows"]].sum()
    visit_pct = sums["profile_visits"] / sums["reach"] * 100 if sums["reach"] else 0
    follow_pct = sums["follows"] / sums["profile_visits"] * 100 if sums["profile_visits"] else 0
    return len(recent), sums, visit_pct, follow_pct
