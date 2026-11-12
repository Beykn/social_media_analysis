"""Build the read-only GitHub Pages site from the data folder.

Run: python build_site.py  (writes _site/index.html)

The site shows the same numbers as the Funnel and Changes tabs of the web
app. Data is still entered in the app; pushing the data folder rebuilds the
site through .github/workflows/pages.yml.
"""
import json
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from src.changes import load_changes
from src.charts import followers_chart, trend_chart
from src.load_insights import load_daily_metrics
from src.metrics import (LABELS, bulk_follows_note, default_trend_metric, remove_bulk_follows, evaluate_change, funnel_summary, label,
                         last_week_summary, weekly)
from src.profile import load_snapshots, with_unfollows

OUT_DIR = Path(__file__).resolve().parent / "_site"
TREND_METRICS = ["reach", "profile_visits", "follows", "follow_rate",
                 "visit_rate", "engagement_rate", "interactions", "views", "link_clicks"]
VIEWS = ["Haftalık", "Günlük"]


def fmt(value, metric=""):
    if value is None or pd.isna(value):
        return "–"
    if metric.endswith("_rate"):
        return f"%{value:.1f}".replace(".", ",")
    return f"{value:,.0f}".replace(",", ".")


def spec(chart):
    return json.loads(chart.configure(background="transparent").configure_view(stroke=None).to_json())


def tile(title, value, change=None, neutral=False, note=None):
    delta = ""
    if change is not None:
        cls = "neutral" if neutral or change == 0 else ("up" if change > 0 else "down")
        arrow = "" if change == 0 else ("▲ " if change > 0 else "▼ ")
        delta = f'<div class="delta {cls}">{arrow}{escape(change_text(change))}</div>'
    hint = f'<div class="hint">{escape(note)}</div>' if note else ""
    return (f'<div class="tile"><div class="tile-title">{escape(title)}</div>'
            f'<div class="tile-value">{escape(value)}</div>{delta}{hint}</div>')


def change_text(change):
    return change if isinstance(change, str) else f"{change:+.0f}%"


def table_html(df, index=True):
    return df.to_html(classes="data", border=0, index=index, na_rep="–", escape=True)


def profile_section(daily, specs):
    snaps = load_snapshots()
    if not len(snaps):
        return '<p class="muted">Henüz profil sayısı girilmedi.</p>'
    hist = with_unfollows(snaps, daily)
    last = hist.iloc[-1]
    prev = hist.iloc[-2] if len(hist) > 1 else None

    def diff(col):
        return None if prev is None else f"{int(last[col] - prev[col]):+d}"

    ratio = last["followers"] / last["following"] if last["following"] else None
    tiles = [
        tile("Takipçi", fmt(last["followers"]), diff("followers")),
        tile("Takip edilen", fmt(last["following"]), diff("following"), neutral=True),
        tile("Takipçi / takip edilen", f"{ratio:.2f}".replace(".", ",") if ratio else "–"),
        tile("Takibi bırakan (tahmini)", fmt(last["unfollows"]),
             note="Yeni takip eksi takipçi sayısındaki net değişim"),
    ]
    since = f" · önceki giriş {prev['date']:%d.%m.%Y}" if prev is not None else ""
    out = f'<div class="tiles">{"".join(tiles)}</div>'
    out += f'<p class="muted">Son giriş: {last["date"]:%d.%m.%Y}{since}</p>'
    if len(hist) > 1:
        specs["followers"] = spec(followers_chart(hist))
        out += '<div class="chart" id="chart-followers"></div>'
        table = hist.rename(columns={"date": "Tarih", "followers": "Takipçi", "following": "Takip edilen",
                                     "net_change": "Net değişim", "new_follows": "Yeni takip",
                                     "unfollows": "Takibi bırakan (tahmini)"})
        table["Tarih"] = table["Tarih"].dt.strftime("%d.%m.%Y")
        out += f'<details><summary>Profil geçmişi</summary>{table_html(table, index=False)}</details>'
    return out


def funnel_section(daily, weeks, changes, specs):
    summary, n_previous = last_week_summary(weeks)
    period = f"{weeks.index[-1]:%d.%m.%Y} – {daily.index.max():%d.%m.%Y}"
    if n_previous:
        period += f" · Karşılaştırma: önceki {n_previous} haftanın ortalaması"
    tiles = "".join(tile(label(m), fmt(v, m), c) for m, (v, c) in summary.items())
    out = f'<h2>Son 7 gün</h2><p class="muted">{period}</p><div class="tiles">{tiles}</div>'
    if not n_previous:
        out += ('<p class="note">Karşılaştırma için en az 2 haftalık veri gerekli. Her hafta yeni bir '
                'dışa aktarım eklendikçe değişimler burada görünecek.</p>')

    n_weeks, sums, visit_pct, follow_pct = funnel_summary(weeks)
    steps = [("Erişim", fmt(sums["reach"]), None),
             ("Profil ziyareti", fmt(sums["profile_visits"]), visit_pct),
             ("Yeni takip", fmt(sums["follows"]), follow_pct)]
    funnel = '<span class="arrow">→</span>'.join(
        f'<div class="step"><div class="tile-title">{name}</div><div class="tile-value">{value}</div>'
        + (f'<div class="muted">%{pct:.1f}</div>'.replace(".", ",") if pct is not None else "")
        + "</div>" for name, value, pct in steps)
    out += (f'<h2>Huni <span class="muted small">son {n_weeks} hafta</span></h2>'
            f'<div class="funnel">{funnel}</div>'
            '<p class="muted">Erişim, günlük erişimlerin toplamıdır; aynı kişi farklı günlerde yeniden sayılır.</p>')

    for metric in TREND_METRICS:
        for view in VIEWS:
            specs[f"trend:{metric}:{view}"] = spec(trend_chart(daily, weeks, metric, view, changes))
    default = default_trend_metric(daily)
    options = "".join(f'<option value="{m}"{" selected" if m == default else ""}>{escape(label(m))}</option>'
                      for m in TREND_METRICS)
    radios = "".join(
        f'<label><input type="radio" name="view" value="{v}"{" checked" if i == 0 else ""}> {v}</label>'
        for i, v in enumerate(VIEWS))
    out += ('<h2>Trend</h2><div class="controls">'
            f'<label>Ölçü <select id="metric">{options}</select></label>'
            f'<div class="radios">{radios}</div></div>'
            '<div class="chart" id="chart-trend"></div>')

    table = weeks.copy()
    table.index = table.index.strftime("%d.%m.%Y")
    table.index.name = "Hafta başı"
    table = table.rename(columns={**LABELS, "days": "Gün"}).round(1)
    out += f'<details><summary>Haftalık tablo</summary><div class="scroll">{table_html(table)}</div></details>'
    return out


def changes_section(daily, changes):
    saved = changes.dropna(subset=["start_date"]).sort_values("start_date", ascending=False)
    if not len(saved):
        return '<p class="muted">Henüz değişiklik eklenmedi.</p>'
    out = []
    for _, row in saved.iterrows():
        end = f" – {row['end_date']:%d.%m.%Y}" if pd.notna(row["end_date"]) else " · sürüyor"
        meta = " · ".join(escape(x) for x in [row["category"], row["target_metric"]] if x)
        body = ""
        if row["hypothesis"]:
            body += f'<p><strong>Beklenti:</strong> {escape(row["hypothesis"])}</p>'
        if row["result_note"]:
            body += f'<p><strong>Sonuç notu:</strong> {escape(row["result_note"])}</p>'
        if daily is not None:
            table, notes = evaluate_change(daily, row["start_date"], row["end_date"])
            if table is None:
                body += f'<p class="muted">{escape(notes[0])}</p>'
            else:
                body += f'<p class="muted">{escape(notes[0])}</p>'
                body += "".join(f'<p class="note">{escape(n)}</p>' for n in notes[1:])
                target = row["target_metric"]
                if target in table.index:
                    r = table.loc[target]
                    change = None if pd.isna(r["Değişim %"]) else r["Değişim %"]
                    value = f"{r['Sonra']:.2f}"
                    body += f'<div class="tiles">{tile("Hedef: " + target, value, change)}</div>'
                body += f'<div class="scroll">{table_html(table)}</div>'
        out.append(f'<details class="change"><summary><span class="date">{row["start_date"]:%d.%m.%Y}{end}</span> '
                   f'{escape(row["description"])}' + (f' <span class="muted small">{meta}</span>' if meta else "")
                   + f"</summary>{body}</details>")
    return "".join(out)


def build(out_dir=OUT_DIR):
    try:
        daily, removed = remove_bulk_follows(load_daily_metrics())
    except (FileNotFoundError, ValueError):
        daily, removed = None, []
    changes = load_changes()
    specs = {}

    body = f"<h2>Profil</h2>{profile_section(daily, specs)}"
    if daily is None:
        body += '<p class="muted">Henüz Business Suite verisi yok.</p>'
    else:
        body += funnel_section(daily, weekly(daily), changes, specs)
        note = bulk_follows_note(removed)
        if note:
            body += f'<p class="muted">{escape(note)}</p>'
    body += f"<h2>Değişiklikler</h2>{changes_section(daily, changes)}"

    built = datetime.now(ZoneInfo("Europe/Istanbul"))
    data_until = f" · veri {daily.index.max():%d.%m.%Y} tarihine kadar" if daily is not None else ""
    page = (TEMPLATE
            .replace("__BODY__", body)
            .replace("__UPDATED__", f"Güncellendi {built:%d.%m.%Y %H:%M}{data_until}")
            .replace("__SPECS__", json.dumps(specs, ensure_ascii=False).replace("</", "<\\/")))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(page, encoding="utf-8")
    (out_dir / ".nojekyll").write_text("")
    return out_dir / "index.html"


TEMPLATE = """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Büyüme Takibi</title>
<style>
:root {
  --bg: #fbfaf8; --surface: #ffffff; --border: #e4e2dd; --text: #1f1e1c;
  --muted: #6b6a66; --up: #1a7f4b; --down: #c2412d; --note-bg: #fdf3e2; --note-text: #7a4a06;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161615; --surface: #1f1f1e; --border: #34332f; --text: #ecebe8;
    --muted: #a3a29d; --up: #4cc38a; --down: #f0806c; --note-bg: #3a2c12; --note-text: #f2c97a;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
main { max-width: 1100px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 28px; margin: 0 0 4px; }
h2 { font-size: 19px; margin: 36px 0 8px; }
.muted { color: var(--muted); margin: 4px 0 12px; }
.small { font-size: 13px; font-weight: 400; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 12px 0; }
.tile, .step { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }
.tile-title { color: var(--muted); font-size: 13px; }
.tile-value { font-size: 28px; font-weight: 600; font-variant-numeric: tabular-nums; }
.delta { font-size: 13px; font-weight: 600; }
.delta.up { color: var(--up); } .delta.down { color: var(--down); } .delta.neutral { color: var(--muted); }
.hint { color: var(--muted); font-size: 12px; margin-top: 2px; }
.funnel { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.funnel .step { flex: 1 1 160px; }
.funnel .step .muted { margin: 0; font-size: 13px; }
.arrow { color: var(--muted); font-size: 20px; }
.note { background: var(--note-bg); color: var(--note-text); border-radius: 8px; padding: 10px 14px; }
.controls { display: flex; gap: 20px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
select { font: inherit; padding: 4px 8px; border-radius: 6px; border: 1px solid var(--border);
  background: var(--surface); color: var(--text); margin-left: 6px; }
.radios { display: flex; gap: 14px; }
.chart { width: 100%; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 12px; }
details { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 10px 14px; margin: 10px 0; }
summary { cursor: pointer; font-weight: 500; }
details.change .date { color: var(--muted); font-variant-numeric: tabular-nums; margin-right: 6px; }
.scroll { overflow-x: auto; }
table.data { border-collapse: collapse; margin-top: 10px; font-size: 13px; font-variant-numeric: tabular-nums; }
table.data th, table.data td { padding: 6px 10px; border-bottom: 1px solid var(--border); text-align: right; white-space: nowrap; }
table.data th { color: var(--muted); font-weight: 500; }
table.data tbody th { text-align: left; color: var(--text); }
footer { color: var(--muted); font-size: 13px; margin-top: 48px; }
</style>
</head>
<body>
<main>
<h1>Instagram büyüme takibi</h1>
<p class="muted">__UPDATED__</p>
__BODY__
<footer>Salt okunur görünüm. Veriler yerel uygulamadan girilir ve her push'ta bu sayfa yeniden oluşturulur.</footer>
</main>
<script src="https://cdn.jsdelivr.net/npm/vega@6.1.2"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-lite@6.4.1"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-embed@7.0.2"></script>
<script>
const SPECS = __SPECS__;
const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
const opts = { actions: false, renderer: "svg", theme: dark ? "dark" : undefined };
function draw(id, key) {
  const el = document.getElementById(id);
  if (!el || !SPECS[key]) return;
  const spec = { ...SPECS[key], width: "container", autosize: { type: "fit", contains: "padding" } };
  vegaEmbed(el, spec, opts).catch(console.error);
}
function drawTrend() {
  const metric = document.getElementById("metric");
  if (!metric) return;
  const view = document.querySelector('input[name="view"]:checked').value;
  draw("chart-trend", `trend:${metric.value}:${view}`);
}
draw("chart-followers", "followers");
drawTrend();
document.getElementById("metric")?.addEventListener("change", drawTrend);
document.querySelectorAll('input[name="view"]').forEach(r => r.addEventListener("change", drawTrend));
</script>
</body>
</html>
"""

if __name__ == "__main__":
    print(build())
