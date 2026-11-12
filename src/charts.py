"""Altair charts shared by the Streamlit app and the static site."""
import altair as alt
import pandas as pd

from src.metrics import add_rates, label, with_rolling

SERIES_COLORS = ["#2a78d6", "#eb6834"]
CHANGE_COLOR = "#8a8984"


def followers_chart(hist):
    return alt.Chart(hist).mark_line(strokeWidth=2, color=SERIES_COLORS[0], point=True).encode(
        # One labelled position per snapshot, in date order.
        x=alt.X("yearmonthdate(date):O", title=None, axis=alt.Axis(format="%d.%m", labelAngle=0)),
        y=alt.Y("followers:Q", title="Takipçi", scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip("date:T", title="Tarih", format="%d.%m.%Y"),
                 alt.Tooltip("followers:Q", title="Takipçi"),
                 alt.Tooltip("following:Q", title="Takip edilen")],
    ).properties(height=220)


def trend_chart(daily, weeks, metric, view, changes):
    if view == "Haftalık":
        data = with_rolling(weeks, metric)
    else:
        data = pd.DataFrame({"Günlük": add_rates(daily)[metric]})
    long = data.reset_index(names="date").melt("date", var_name="Seri", value_name="Değer")

    base = alt.Chart(long).encode(
        # Ticks on whole days only; weekly points get a tick per week.
        x=alt.X("date:T", title=None, axis=alt.Axis(
            format="%d.%m", tickCount={"interval": "day", "step": 7 if view == "Haftalık" else 1})),
        y=alt.Y("Değer:Q", title=label(metric)),
        color=alt.Color("Seri:N", scale=alt.Scale(range=SERIES_COLORS),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=[alt.Tooltip("date:T", title="Tarih", format="%d.%m.%Y"),
                 "Seri:N", alt.Tooltip("Değer:Q", format=",.1f")],
    )
    chart = base.mark_line(strokeWidth=2) + base.mark_circle(size=70)

    marks = changes.dropna(subset=["start_date"])
    if len(marks):
        rules = pd.DataFrame({
            "date": pd.to_datetime(marks["start_date"]),
            "Değişiklik": marks["description"],
            "Kategori": marks["category"],
        })
        chart += alt.Chart(rules).mark_rule(color=CHANGE_COLOR, strokeDash=[4, 4], strokeWidth=1.5).encode(
            x="date:T",
            tooltip=[alt.Tooltip("date:T", title="Başlangıç", format="%d.%m.%Y"), "Kategori:N", "Değişiklik:N"],
        )
    return chart.properties(height=320)
