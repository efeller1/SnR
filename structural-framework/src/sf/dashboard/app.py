"""§7 dashboard v1 (Streamlit). Run `python -m sf history` first, then:

    streamlit run src/sf/dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sf.config import CONFIG_DIR, DATA_DIR, load_config  # noqa: E402
from sf.history import load_history  # noqa: E402
from sf.trends.load import load_trends  # noqa: E402
from sf.trends.score import score_trend, trend_history  # noqa: E402

st.set_page_config(page_title="Structural Framework", layout="wide")
cfg = load_config()
HIST = DATA_DIR / "processed" / "history"
if not (HIST / "composite.parquet").exists():
    st.error("No scored history yet. Run `python -m sf ingest` then `python -m sf history`.")
    st.stop()
h = load_history(HIST)
comps = h["components"]
stance = h["stance"]
dates = h["composite"].index
t = st.sidebar.selectbox("As of", list(reversed(dates)), format_func=lambda d: d.date().isoformat())
prev = dates[dates.get_loc(t) - 1] if dates.get_loc(t) > 0 else None
view = st.sidebar.radio("View", ["Overview", "Regime", "Asset drilldown", "Trends", "Allocation", "Change log"])


def color(v):
    if pd.isna(v):
        return "color: #999"
    # 1 = red ... 3 = neutral ... 5 = green
    r, g = (220, int(60 + 160 * (v - 1) / 2)) if v < 3 else (int(220 - 160 * (v - 3) / 2), 180)
    return f"background-color: rgba({r},{g},80,0.35)"


if view == "Overview":
    st.header(f"Overview — {t.date()}")
    rows = []
    for aid, a in cfg.assets.assets.items():
        c = comps.loc[aid].loc[t] if (aid, t) in comps.index else pd.Series(dtype=float)
        comp = h["composite"].loc[t, aid]
        rows.append({"asset": aid, "group": a.group, **{k: c.get(k) for k in ("STR", "REG", "CAP", "VAL", "LIQ", "MOM")},
                     "Composite": comp, "Stance": stance.loc[(aid, t), "stance"],
                     "Δ vs last month": comp - h["composite"].loc[prev, aid] if prev is not None else None,
                     "trend": h["composite"][aid].loc[:t].tail(24).round(2).tolist()})
    df = pd.DataFrame(rows).set_index("asset")
    num = ["STR", "REG", "CAP", "VAL", "LIQ", "MOM", "Composite"]
    st.dataframe(df.style.map(color, subset=num).format("{:.1f}", subset=num, na_rep="NA")
                 .format("{:+.2f}", subset=["Δ vs last month"], na_rep=""),
                 column_config={"trend": st.column_config.LineChartColumn("24m composite", y_min=1, y_max=5)},
                 width="stretch")
    trends = load_trends()
    if trends:
        st.subheader("Trends")
        st.dataframe(pd.DataFrame([{"trend": k, **score_trend(v)} for k, v in trends.items()]).set_index("trend")
                     .style.map(color).format("{:.1f}"), width="stretch")

elif view == "Regime":
    r = h["regime"]
    row = r.loc[t]
    st.header(f"Regime — {t.date()}")
    c = st.columns(4)
    c[0].metric("Quadrant", str(row["quadrant"]))
    c[1].metric("FDI", "NA" if pd.isna(row["fdi"]) else f"{row['fdi']:.2f}", str(row["liquidity_driver"]))
    c[2].metric("Real rates", str(row["real_rates"]),
                None if pd.isna(row["real_10y"]) else f"10y TIPS {row['real_10y']:.2f}%")
    c[3].metric("Global order", str(row["global_order"]))
    st.subheader("FDI history")
    st.line_chart(r[["fdi"]].loc[:t])
    st.subheader("Regime timeline")
    st.dataframe(r.loc[:t, ["quadrant", "liquidity_driver", "real_rates", "global_order"]].iloc[::-1],
                 width="stretch")

elif view == "Asset drilldown":
    aid = st.selectbox("Asset", list(cfg.assets.assets))
    a = cfg.assets.assets[aid]
    st.header(a.name)
    st.caption(a.thesis)
    if a.breaks_if:
        st.markdown("**Breaks if:** " + "; ".join(a.breaks_if))
    rows = []
    for m in a.metrics:
        rows.append({"metric": m.id, "name": m.name, "component": m.component or "diagnostic",
                     "value": h["metric_values"].loc[t, m.id], "percentile": h["metric_pct"].loc[t, m.id],
                     "score": h["metric_scores"].loc[t, m.id], "weight": h["metric_weights"].loc[t, m.id],
                     "Δ score": (h["metric_scores"].loc[t, m.id] - h["metric_scores"].loc[prev, m.id])
                     if prev is not None else None})
    df = pd.DataFrame(rows).set_index("metric")
    st.dataframe(df.style.map(color, subset=["score"]).format(
        {"value": "{:.4g}", "percentile": "{:.2f}", "score": "{:.1f}", "weight": "{:.2f}", "Δ score": "{:+.2f}"},
        na_rep="NA"), width="stretch")
    moved = df["Δ score"].abs().sort_values(ascending=False).dropna().head(3)
    if len(moved):
        st.markdown("**What changed:** " + ", ".join(f"{k} ({df.loc[k, 'Δ score']:+.2f})" for k in moved.index))
    pick = st.selectbox("History chart", df.index)
    st.line_chart(pd.DataFrame({"value": h["metric_values"][pick], "score": h["metric_scores"][pick]}).loc[:t])
    st.subheader("Component history")
    st.line_chart(comps.loc[aid].loc[:t])

elif view == "Trends":
    for k, tr in load_trends().items():
        s = score_trend(tr)
        with st.expander(f"{tr.name} — opportunity {s['opportunity']:.2f}", expanded=True):
            st.write(tr.thesis)
            st.markdown("**Value chain:** " + " → ".join(f"**{n.node}** (bottleneck)" if n.bottleneck else n.node
                                                         for n in tr.value_chain))
            st.markdown(f"**Capital cycle:** {tr.capital_cycle_stage}  |  **Priced in:** {tr.priced_in}/5  |  "
                        f"**Durability:** {s['durability']:.2f}  |  **Review:** {tr.review_date}")
            st.markdown("**Kill criteria:**\n" + "\n".join(f"- {'🔴' if kc.triggered else '🟢'} {kc.text}"
                                                           for kc in tr.kills))
            th = trend_history(tr)
            if len(th):
                st.dataframe(th, width="stretch")

elif view == "Allocation":
    st.header(f"Model allocation — {t.date()}")
    st.caption("Placeholders for testing, not a recommendation (§3.5).")
    base = pd.Series(cfg.allocation.base_weights)
    tilted = h["allocation"].loc[t]
    comp = h["composite"].loc[t, base.index]
    st.dataframe(pd.DataFrame({"base": base, "tilted": tilted, "change": tilted - base, "composite": comp})
                 .style.format({"base": "{:.1%}", "tilted": "{:.1%}", "change": "{:+.1%}", "composite": "{:.2f}"}),
                 width="stretch")
    st.area_chart(h["allocation"].loc[:t], stack=True)

else:
    st.header("Change log")
    with open(CONFIG_DIR / "changelog.yaml") as f:
        st.dataframe(pd.DataFrame(yaml.safe_load(f)).iloc[::-1], width="stretch")
