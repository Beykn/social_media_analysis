"""Web interface for tracking account growth and the changes behind it.

Run: streamlit run app.py
"""
from datetime import date

import pandas as pd
import streamlit as st

from src.changes import CATEGORIES, load_changes, save_changes
from src.charts import followers_chart, trend_chart
from src.load_insights import RAW_DIR, load_daily_metrics, save_exports
from src.metrics import LABELS, bulk_follows_note, default_trend_metric, evaluate_change, remove_bulk_follows, funnel_summary, label, last_week_summary, weekly
from src.profile import load_snapshots, save_snapshot, with_unfollows

st.set_page_config(page_title="Büyüme Takibi", page_icon="📈", layout="wide")

FUNNEL_METRICS = ["reach", "profile_visits", "follows", "follow_rate",
                  "visit_rate", "engagement_rate", "interactions", "views", "link_clicks"]
TARGET_OPTIONS = [LABELS[m] for m in FUNNEL_METRICS]


def load_data():
    try:
        daily, removed = remove_bulk_follows(load_daily_metrics())
    except (FileNotFoundError, ValueError):
        return None, None
    return daily, bulk_follows_note(removed)


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
            chart = followers_chart(hist)
            st.altair_chart(chart, width="stretch")
            with st.expander("Profil geçmişi"):
                table = hist.rename(columns={"date": "Tarih", "followers": "Takipçi", "following": "Takip edilen",
                                             "net_change": "Net değişim", "new_follows": "Yeni takip",
                                             "unfollows": "Takibi bırakan (tahmini)"})
                table["Tarih"] = table["Tarih"].dt.strftime("%d.%m.%Y")
                st.dataframe(table, hide_index=True, width="stretch")
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
    summary, n_previous = last_week_summary(weeks)

    st.subheader("Son 7 gün")
    period = f"{weeks.index[-1].date()} – {daily.index.max().date()}"
    if n_previous:
        period += f" · Karşılaştırma: önceki {n_previous} haftanın ortalaması"
    st.caption(period)
    cols = st.columns(4)
    for col, (metric, (value, change)) in zip(cols, summary.items()):
        delta = None if change is None else f"{change:+.0f}%"
        col.metric(label(metric), fmt(value, metric), delta)
    if not n_previous:
        st.info("Karşılaştırma için en az 2 haftalık veri gerekli. Her hafta yeni bir dışa aktarım ekledikçe değişimler burada görünecek.")

    n_weeks, sums, visit_pct, follow_pct = funnel_summary(weeks)
    st.markdown(
        f"**Huni (son {n_weeks} hafta):** "
        f"Erişim {fmt(sums['reach'], 'reach')} → "
        f"Profil ziyareti {fmt(sums['profile_visits'], 'x')} (%{visit_pct:.1f}) → "
        f"Yeni takip {fmt(sums['follows'], 'x')} (%{follow_pct:.1f})"
    )
    st.caption("Erişim, günlük erişimlerin toplamıdır; aynı kişi farklı günlerde yeniden sayılır.")

    st.divider()
    left, right = st.columns([1, 3])
    with left:
        metric = st.selectbox("Ölçü", FUNNEL_METRICS, format_func=label,
                              index=FUNNEL_METRICS.index(default_trend_metric(daily)))
        view = st.radio("Görünüm", ["Haftalık", "Günlük"], horizontal=True)
    with right:
        st.altair_chart(trend_chart(daily, weeks, metric, view, changes), width="stretch")

    with st.expander("Haftalık tablo"):
        table = weeks.copy()
        table.index = table.index.date
        table = table.rename(columns={**LABELS, "days": "Gün"})
        st.dataframe(table, width="stretch")


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
        width="stretch",
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
            st.dataframe(table, width="stretch")


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
            folder, metrics, skipped = save_exports([(f.name, f.getvalue()) for f in files])
        except Exception as e:
            st.error(f"Dosyalar okunamadı, Business Suite dışa aktarımı olduklarından emin ol. ({e})")
            return
        st.success(f"{len(metrics)} dosya kaydedildi: {folder.name} · " + ", ".join(label(m) for m in metrics))
        if skipped:
            st.info("Günlük veri içermediği için atlandı: " + ", ".join(skipped) + ". Boş geldiyse "
                    "(Business Suite uzun aralıklarda erişim ve ziyaret vermeyebiliyor) daha kısa bir "
                    "aralıkla yeniden dışa aktar.")


def main():
    st.title("Instagram büyüme takibi")
    daily, data_note = load_data()
    changes = load_changes()

    tabs = st.tabs(["Huni", "Değişiklikler", "Veri yükle"])
    with tabs[0]:
        profile_section(daily)
        st.divider()
        if daily is None:
            st.info("Henüz veri yok. **Veri yükle** sekmesinden Business Suite dışa aktarımını ekle.")
        else:
            funnel_tab(daily, changes)
            if data_note:
                st.caption(data_note)
    with tabs[1]:
        changes_tab(daily, changes)
    with tabs[2]:
        upload_tab()


main()
