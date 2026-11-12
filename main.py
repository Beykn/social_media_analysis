"""Summarize Instagram account metrics exported from Meta Business Suite.

Usage: python main.py
Reads data/raw/*/*.csv, prints a summary and writes reports/daily_metrics.png.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from src.load_insights import load_daily_metrics
from src.metrics import LABELS, add_rates, bulk_follows_note, remove_bulk_follows

REPORT_DIR = Path(__file__).resolve().parent / "reports"

DAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

SURFACE = "#fcfcfb"
SERIES = "#2a78d6"
TEXT = "#0b0b0b"
TEXT_MUTED = "#52514e"
GRID = "#e4e3df"


def rate(df, num, den):
    both = df[[num, den]].dropna()
    return both[num].sum() / both[den].sum() * 100 if both[den].sum() else None


def print_summary(df):
    start, end = df.index.min().date(), df.index.max().date()
    print(f"Dönem: {start} - {end} ({len(df)} gün)\n")
    print("Son 14 gün:")
    print(add_rates(df.tail(14)).to_string(float_format=lambda v: f"{v:g}"))

    totals = df.sum()
    print("\nGünlük değerlerin toplamı:")
    for metric, total in totals.items():
        days = int(df[metric].notna().sum())
        note = f"  ({days} günlük veri)" if days < len(df) else ""
        print(f"  {LABELS.get(metric, metric):<16} {int(total)}{note}")
    # The same account can be reached on several days, so this is not the
    # number of unique accounts reached in the period.
    print("  (Erişim toplamı tekil kişi sayısı değildir; aynı kişi her gün yeniden sayılır.)")

    # Rates only over days where both numbers are known.
    if {"interactions", "reach"} <= set(df) and rate(df, "interactions", "reach") is not None:
        print(f"\nOrtalama etkileşim oranı: {rate(df, 'interactions', 'reach'):.1f}% (etkileşim / erişim)")
    if {"follows", "profile_visits"} <= set(df) and rate(df, "follows", "profile_visits") is not None:
        print(f"Ziyaretin takibe dönüşmesi: {rate(df, 'follows', 'profile_visits'):.1f}%")
    if "reach" in df:
        best = df["reach"].idxmax()
        print(f"En yüksek erişim: {best.date()} ({DAYS_TR[best.day_of_week]}) - {df.loc[best, 'reach']}")


def plot_daily(df, path):
    metrics = list(df.columns)
    cols = 3
    rows = -(-len(metrics) // cols)
    fig, axes = plt.subplots(rows, cols, figsize=(12, 3.2 * rows), facecolor=SURFACE, squeeze=False)

    for ax, metric in zip(axes.flat, metrics):
        values = df[metric].astype(float)
        ax.bar(df.index, values, width=0.6, color=SERIES)
        ax.set_facecolor(SURFACE)
        ax.set_title(LABELS.get(metric, metric), loc="left", color=TEXT, fontsize=11)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.tick_params(colors=TEXT_MUTED, labelsize=8, length=0)
        ax.set_xticks(df.index)
        ax.set_xticklabels([d.strftime("%d.%m") for d in df.index])
        ax.set_ylim(bottom=0, top=None if values.max() > 0 else 1)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        if values.max() == 0:
            ax.text(0.5, 0.5, "Bu dönemde hiç yok", transform=ax.transAxes,
                    ha="center", va="center", fontsize=9, color=TEXT_MUTED)
        # Label only the peak day so the panel stays readable.
        if values.max() > 0:
            peak = values.idxmax()
            ax.annotate(f"{int(values[peak])}", (peak, values[peak]), textcoords="offset points",
                        xytext=(0, 3), ha="center", fontsize=8, color=TEXT)

    for ax in list(axes.flat)[len(metrics):]:
        ax.set_visible(False)

    fig.suptitle("Günlük Instagram metrikleri", x=0.01, ha="left", color=TEXT, fontsize=13)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print(f"\nGrafik kaydedildi: {path}")


if __name__ == "__main__":
    daily, removed = remove_bulk_follows(load_daily_metrics())
    if bulk_follows_note(removed):
        print(bulk_follows_note(removed))
    print_summary(daily)
    plot_daily(daily, REPORT_DIR / "daily_metrics.png")
