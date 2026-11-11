"""Web interface for tracking account growth and the changes behind it.

Run: streamlit run app.py
"""
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from src.changes import CATEGORIES, load_changes, save_changes
from src.load_insights import RAW_DIR, load_daily_metrics, save_exports
from src.metrics import LABELS, add_rates, evaluate_change, label, weekly, with_rolling
from src.profile import load_snapshots, save_snapshot, with_unfollows

st.set_page_config(page_title="Büyüme Takibi", page_icon="📈", layout="wide")

SERIES_COLORS = ["#2a78d6", "#eb6834"]
CHANGE_COLOR = "#8a8984"
FUNNEL_METRICS = ["reach", "profile_visits", "follows", "follow_rate",
                  "visit_rate", "engagement_rate", "interactions", "views", "link_clicks"]
TARGET_OPTIONS = [LABELS[m] for m in FUNNEL_METRICS]


def load_data():
    try:
        return load_daily_metrics()
    except (FileNotFoundError, ValueError):
        return None


def fmt(value, metric):
    if pd.isna(value):
        return "–"
    return f"%{value:.1f}" if metric.endswith("_rate") else f"{value:,.0f}".replace(",", ".")


def profile_section(daily):
    st.subheader("Profil")
    snaps = load_snapshots()
    last = None
    if len(snaps):
        hist = with_unfollows(snaps, daily)
        last = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else None

        def change(col):
            return None if prev is None else f"{int(last[col] - prev[col]):+d}"

        cols = st.columns(4)
        cols[0].metric("Takipçi", fmt(last["followers"], "x"), change("followers"))
        cols[1].metric("Takip edilen", fmt(last["following"], "x"), change("following"), delta_color="off")
        ratio = last["followers"] / last["following"] if last["following"] else None
        cols[2].metric("Takipçi / takip edilen", f"{ratio:.2f}" if ratio else "–")
        cols[3].metric(
            "Takibi bırakan (tahmini)", fmt(last["unfollows"], "x"),
            help="Önceki girişten bu yana gelen yeni takip (Business Suite) eksi takipçi sayısındaki net "
                 "değişim. Bu aralığın tüm günleri için dışa aktarım yoksa hesaplanamaz.",
        )
        since = f" · önceki giriş {prev['date']:%d.%m.%Y}" if prev is not None else ""
        st.caption(f"Son giriş: {last['date']:%d.%m.%Y}{since}")

        if len(hist) > 1:
            chart = alt.Chart(hist).mark_line(strokeWidth=2, color=SERIES_COLORS[0], point=True).encode(
                # One labelled position per snapshot, in date order.
                x=alt.X("yearmonthdate(date):O", title=None, axis=alt.Axis(format="%d.%m", labelAngle=0)),
                y=alt.Y("followers:Q", title="Takipçi", scale=alt.Scale(zero=False)),
                tooltip=[alt.Tooltip("date:T", title="Tarih", format="%d.%m.%Y"),
                         alt.Tooltip("followers:Q", title="Takipçi"),
                         alt.Tooltip("following:Q", title="Takip edilen")],
            ).properties(height=220)
            st.altair_chart(chart, use_container_width=True)
            with st.expander("Profil geçmişi"):
                table = hist.rename(columns={"date": "Tarih", "followers": "Takipçi", "following": "Takip edilen",
                                             "net_change": "Net değişim", "new_follows": "Yeni takip",
                                             "unfollows": "Takibi bırakan (tahmini)"})
                table["Tarih"] = table["Tarih"].dt.strftime("%d.%m.%Y")
                st.dataframe(table, hide_index=True, use_container_width=True)
    else:
        st.info("Henüz profil sayısı girilmedi. Profilindeki takipçi ve takip edilen sayısını aşağıdan ekle; "
                "her hafta veri yüklerken yeniden girersen zaman içindeki değişimi burada görürsün.")

    with st.expander("Profil sayılarını gir", expanded=last is None):
        with st.form("profile_snapshot"):
            day = st.date_input("Tarih", value=date.today(), format="DD.MM.YYYY")
            left, right = st.columns(2)
            followers = left.number_input("Takipçi", min_value=0, step=1,
                                          value=int(last["followers"]) if last is not None else 0)
            following = right.number_input("Takip edilen", min_value=0, step=1,
                                           value=int(last["following"]) if last is not None else 0)
            if st.form_submit_button("Kaydet", type="primary"):
                save_snapshot(day, int(followers), int(following))
                st.toast("Profil sayıları kaydedildi.")
                st.rerun()


def funnel_tab(daily, changes):
    weeks = weekly(daily)
    last = weeks.iloc[-1]
    previous = weeks.iloc[:-1].tail(4)

    st.subheader("Son 7 gün")
    period = f"{weeks.index[-1].date()} – {daily.index.max().date()}"
    if len(previous):
        period += f" · Karşılaştırma: önceki {len(previous)} haftanın ortalaması"
    st.caption(period)
    cols = st.columns(4)
    for col, metric in zip(cols, ["reach", "profile_visits", "follows", "follow_rate"]):
        delta = None
        if len(previous):
            if metric == "follow_rate":
                base = previous["follows"].sum() / previous["profile_visits"].sum() * 100 \
                    if previous["profile_visits"].sum() else None
            else:
                base = previous[metric].mean()
            if base:
                delta = f"{(last[metric] - base) / base * 100:+.0f}%"
        col.metric(label(metric), fmt(last[metric], metric), delta)
    if not len(previous):
        st.info("Karşılaştırma için en az 2 haftalık veri gerekli. Her hafta yeni bir dışa aktarım ekledikçe değişimler burada görünecek.")

    recent = weeks.tail(4)
    sums = recent[["reach", "profile_visits", "follows"]].sum()
    visit_pct = sums["profile_visits"] / sums["reach"] * 100 if sums["reach"] else 0
    follow_pct = sums["follows"] / sums["profile_visits"] * 100 if sums["profile_visits"] else 0
    st.markdown(
        f"**Huni (son {len(recent)} hafta):** "
        f"Erişim {fmt(sums['reach'], 'reach')} → "
        f"Profil ziyareti {fmt(sums['profile_visits'], 'x')} (%{visit_pct:.1f}) → "
        f"Yeni takip {fmt(sums['follows'], 'x')} (%{follow_pct:.1f})"
    )
    st.caption("Erişim, günlük erişimlerin toplamıdır; aynı kişi farklı günlerde yeniden sayılır.")

    st.divider()
    left, right = st.columns([1, 3])
    with left:
        metric = st.selectbox("Ölçü", FUNNEL_METRICS, format_func=label)
        view = st.radio("Görünüm", ["Haftalık", "Günlük"], horizontal=True)
    with right:
        st.altair_chart(trend_chart(daily, weeks, metric, view, changes), use_container_width=True)

    with st.expander("Haftalık tablo"):
        table = weeks.copy()
        table.index = table.index.date
        table = table.rename(columns={**LABELS, "days": "Gün"})
        st.dataframe(table, use_container_width=True)


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


def changes_tab(daily, changes):
    st.subheader("Değişiklik listesi")
    st.caption("Hesabında yaptığın her değişikliği bir satır olarak ekle. Aynı anda tek bir değişiklik "
               "yapmaya ve her birini en az 2–4 hafta korumaya çalış. Satır eklemek için tablonun altındaki "
               "+ işaretini, silmek için satırı seçip çöp kutusunu kullan.")
    # An empty editor renders as a tiny box; start with one blank row to fill in.
    # Rows without a start date or description are dropped on save.
    editable = changes if len(changes) else changes.reindex([0])
    edited = st.data_editor(
        editable,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="changes_editor",
        column_config={
            "start_date": st.column_config.DateColumn("Başlangıç", required=True, format="DD.MM.YYYY"),
            "end_date": st.column_config.DateColumn("Bitiş (boşsa sürüyor)", format="DD.MM.YYYY"),
            "category": st.column_config.SelectboxColumn("Kategori", options=CATEGORIES),
            "description": st.column_config.TextColumn("Ne değiştirdin?", required=True, width="large"),
            "target_metric": st.column_config.SelectboxColumn("Hedef ölçü", options=TARGET_OPTIONS),
            "hypothesis": st.column_config.TextColumn("Beklentin", width="medium"),
            "result_note": st.column_config.TextColumn("Sonuç notu", width="medium"),
        },
    )
    if st.button("Değişiklikleri kaydet", type="primary"):
        count = save_changes(edited)
        st.toast(f"{count} değişiklik kaydedildi.")
        st.rerun()

    saved = changes.dropna(subset=["start_date"])
    if daily is None or not len(saved):
        return

    st.divider()
    st.subheader("Değerlendirme")
    st.caption("Her değişiklikten sonraki dönem (bitiş yoksa en fazla 28 gün), değişiklikten hemen önceki "
               "aynı uzunluktaki dönemle karşılaştırılır. Sayılar günlük ortalama, oranlar dönem toplamından hesaplanır.")
    for _, row in saved.sort_values("start_date", ascending=False).iterrows():
        title = f"{row['start_date']:%d.%m.%Y} · {row['description']}"
        with st.expander(title):
            if row.get("hypothesis"):
                st.markdown(f"**Beklenti:** {row['hypothesis']}")
            table, notes = evaluate_change(daily, row["start_date"], row["end_date"])
            if table is None:
                st.info(notes[0])
                continue
            st.caption(notes[0])
            for note in notes[1:]:
                st.warning(note)
            target = row.get("target_metric")
            if target in table.index:
                r = table.loc[target]
                delta = None if pd.isna(r["Değişim %"]) else f"{r['Değişim %']:+.1f}%"
                st.metric(f"Hedef: {target}", f"{r['Sonra']:.2f}", delta)
            st.dataframe(table, use_container_width=True)


def upload_tab():
    st.subheader("Business Suite verisi ekle")
    st.markdown(
        "Meta Business Suite'te **İstatistikler**'i aç, tarih aralığını seç ve verileri CSV olarak dışa aktar. "
        "Aynı dışa aktarımdaki tüm dosyaları birlikte yükle; tarih aralığına göre "
        f"`{RAW_DIR.relative_to(RAW_DIR.parent.parent)}/<başlangıç>_<bitiş>/` klasörüne kaydedilir."
    )
    files = st.file_uploader("CSV dosyaları", type="csv", accept_multiple_files=True)
    if files and st.button("Yükle", type="primary"):
        try:
            folder, metrics = save_exports([(f.name, f.getvalue()) for f in files])
        except Exception as e:
            st.error(f"Dosyalar okunamadı, Business Suite dışa aktarımı olduklarından emin ol. ({e})")
            return
        st.success(f"{len(metrics)} dosya kaydedildi: {folder.name} · " + ", ".join(label(m) for m in metrics))


def main():
    st.title("Instagram büyüme takibi")
    daily = load_data()
    changes = load_changes()

    tabs = st.tabs(["Huni", "Değişiklikler", "Veri yükle"])
    with tabs[0]:
        profile_section(daily)
        st.divider()
        if daily is None:
            st.info("Henüz veri yok. **Veri yükle** sekmesinden Business Suite dışa aktarımını ekle.")
        else:
            funnel_tab(daily, changes)
    with tabs[1]:
        changes_tab(daily, changes)
    with tabs[2]:
        upload_tab()


main()
