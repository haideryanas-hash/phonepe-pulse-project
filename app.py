"""Pulse Atlas — a PhonePe Pulse explorer built with Streamlit + Plotly.

Run:  streamlit run app.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Pulse Atlas · PhonePe Pulse", page_icon="🟣", layout="wide")

HERE = Path(__file__).parent
DATA = HERE / "data" if (HERE / "data").exists() else HERE
ALLC, ALLI, ALLB = "All categories", "All India", "All brands"

# ───────────────────────── styling ─────────────────────────
st.markdown(
    """
<style>
.stApp{background:radial-gradient(1100px 520px at 8% -8%,#2d1559 0%,transparent 60%),
 radial-gradient(900px 480px at 100% 0%,#0c3b4c 0%,transparent 55%),#0a0714;}
section[data-testid=stSidebar]{background:#0e0920;border-right:1px solid #2a1f4a}
.block-container{padding-top:1.4rem;max-width:1500px}
.hero h1{font-size:2.5rem;margin:0;font-weight:800;letter-spacing:-.02em;
 background:linear-gradient(90deg,#fff,#c9a8ff 45%,#5eead4);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hero p{color:#a99bd1;margin:.2rem 0 1rem;font-size:.95rem}
.chip{display:inline-block;padding:2px 10px;margin-right:6px;border-radius:99px;font-size:.75rem;
 background:rgba(179,136,255,.14);border:1px solid rgba(179,136,255,.35);color:#e4d6ff}
.kpi{background:linear-gradient(160deg,rgba(255,255,255,.07),rgba(255,255,255,.02));
 border:1px solid rgba(179,136,255,.28);border-radius:16px;padding:14px 16px;height:100%}
.kpi .l{font-size:.7rem;letter-spacing:.13em;text-transform:uppercase;color:#a99bd1}
.kpi .v{font-size:1.65rem;font-weight:750;color:#fff;margin:2px 0}
.kpi .d{font-size:.82rem;font-weight:600}.kpi .d span{color:#8d80b5;font-weight:400}
.up{color:#4ade80}.down{color:#f87171}.na{color:#8d80b5}
.insight{border-left:3px solid #b388ff;padding:10px 14px;background:rgba(255,255,255,.035);
 border-radius:0 10px 10px 0;margin-bottom:12px}
.insight b{color:#e4d6ff}.insight small{color:#8d80b5}
</style>
""",
    unsafe_allow_html=True,
)


# ───────────────────────── data ─────────────────────────
@st.cache_data(show_spinner="Loading PhonePe Pulse data…")
def load():
    rd = lambda n: pd.read_csv(DATA / f"{n}.csv", usecols=lambda c: not c.startswith("Unnamed"))
    tx, br, mt, mu, tt, tu = (rd(n) for n in
        ["aggregated_transaction", "aggregated_user", "map_transaction", "map_user", "top_transaction", "top_user"])
    for d in (tx, br, mt, mu, tt, tu):
        d["p"] = d.year * 10 + d.quarter
    for d in (mt, mu, tt, tu):
        d["district"] = d.district.str.replace(r"\s+district$", "", regex=True).str.title()
    usp = (mu.groupby(["states", "p"], as_index=False).registered_user_counts.sum()
             .rename(columns={"registered_user_counts": "users"}))
    mu = mu.rename(columns={"registered_user_counts": "users"})
    tu = tu.rename(columns={"registered_user_counts": "users"})
    geo = json.loads((DATA / "india_states.geojson").read_text())
    cent = json.loads((DATA / "state_centroids.json").read_text())
    return tx, br, mt, mu, tt, tu, usp, geo, cent


TX, BR, MT, MU, TT, TU, USP, GEO, CENT = load()
YEARS = sorted(TX.year.unique().tolist())
STATES = sorted(TX.states.unique())
CATS = sorted(TX.trans_type.unique())
BRANDS = sorted(b for b in BR.brand.unique() if b != "Others")
LABEL = {p: f"{p // 10} Q{p % 10}" for p in sorted(TX.p.unique())}
_a = TX.groupby(["states", "year"]).amount.sum().unstack()
STATE_CAGR = (_a[YEARS[-1]] / _a[YEARS[0]]) ** (1 / (YEARS[-1] - YEARS[0])) - 1

pretty = lambda s: s.replace("-&-", " & ").replace("-", " ").title()
RAW = {pretty(s): s for s in STATES}

METRICS = {  # label -> (column, formatter kind)
    "Transaction count": ("txns", "count"),
    "Transaction value": ("amount", "money"),
    "Average ticket size": ("ticket", "rupee"),
    "Registered users": ("users", "count"),
    "Transactions per user": ("intensity", "ratio"),
    "Pulse Score (0-100)": ("score", "score"),
}
PALETTES = {"Violet Pulse": "Plasma", "Aurora": "Viridis", "Ember": "Magma", "Spectrum": "Turbo", "Lagoon": "Tealgrn"}
CATCOL = {"Peer-to-peer payments": "#b388ff", "Merchant payments": "#22d3ee", "Recharge & bill payments": "#fbbf24",
          "Financial Services": "#34d399", "Others": "#94a3b8"}
ARCH = {"Peer-to-peer payments": "P2P-led", "Merchant payments": "Merchant-led",
        "Recharge & bill payments": "Bill-pay-led", "Financial Services": "Fin-services-led", "Others": "Others-led"}


def human(v, kind):
    if v is None or pd.isna(v):
        return "–"
    a = abs(v)
    if kind == "money":
        if a >= 1e12: return f"₹{v / 1e12:,.2f} L Cr"
        if a >= 1e7: return f"₹{v / 1e7:,.1f} Cr"
        if a >= 1e5: return f"₹{v / 1e5:,.1f} L"
        return f"₹{v:,.0f}"
    if kind == "rupee": return f"₹{v:,.0f}"
    if kind == "count":
        for d, s in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
            if a >= d: return f"{v / d:,.2f}{s}"
        return f"{v:,.0f}"
    if kind == "ratio": return f"{v:,.1f}"
    if kind == "score": return f"{v:,.0f}"
    return f"{v:,.2f}"


# ───────────────────────── sidebar: control deck ─────────────────────────
with st.sidebar:
    st.markdown("### 🎛️ Control deck")
    METRIC = st.selectbox("Metric", list(METRICS))
    YEAR = st.selectbox("Year", ["All years"] + YEARS, index=len(YEARS))
    QUARTER = st.selectbox("Quarter", ["All quarters", "Q1", "Q2", "Q3", "Q4"])
    CAT = st.selectbox("Payment category", [ALLC] + CATS)
    FOCUS_LBL = st.selectbox("State focus", [ALLI] + list(RAW))
    MAPSTYLE = st.selectbox("Map style", ["Choropleth", "Bubble"])
    MAPMODE = st.selectbox("Map mode", ["Snapshot", "Time machine (animated)"])
    PALETTE = st.selectbox("Colour palette", list(PALETTES))
    SCALE = st.selectbox("Scale", ["Linear", "Log"])
    TOPN = st.selectbox("Top-N", [5, 10, 15, 20], index=1)
    BASIS = st.selectbox("Growth basis", ["YoY", "QoQ", "CAGR 2018→2022"])
    GRAIN = st.selectbox("Time grain", ["Quarterly", "Yearly"])
    BRAND = st.selectbox("Device brand", [ALLB] + BRANDS)
    st.caption("13 live selectors · every chart reacts to them.")

COL, KIND = METRICS[METRIC]
FOCUS = RAW.get(FOCUS_LBL, ALLI)
LOG = SCALE == "Log"
CSCALE = PALETTES[PALETTE]
ADDITIVE = COL in ("txns", "amount", "users")
TSCOL = COL if COL != "score" else "amount"  # score has no time-series; fall back to value
TSLBL = METRIC if COL != "score" else "Transaction value"
TSKIND = KIND if COL != "score" else "money"


def sel_keys(year, q):
    ys = YEARS if year == "All years" else [year]
    qs = [1, 2, 3, 4] if q == "All quarters" else [int(q[1])]
    return tuple(y * 10 + x for y in ys for x in qs)


KEYS = sel_keys(YEAR, QUARTER)
PERIOD = f"{YEAR if YEAR != 'All years' else '2018–2022'} · {QUARTER}"


# ───────────────────────── analytics layer ─────────────────────────
@st.cache_data
def state_table(keys, cat):
    keys = list(keys)
    allt = TX[TX.p.isin(keys)]
    t = allt if cat == ALLC else allt[allt.trans_type == cat]
    g = t.groupby("states").agg(txns=("trans_counts", "sum"), amount=("amount", "sum"))
    users = USP[USP.p == max(keys)].set_index("states").users  # users = stock → last period
    g["users"] = users
    g["ticket"] = g.amount / g.txns
    g["intensity"] = g.txns / g.users
    # Pulse Score: mean percentile of depth, merchant share, ticket, growth (all categories)
    ag = allt.groupby("states").agg(c=("trans_counts", "sum"), a=("amount", "sum"))
    mer = allt[allt.trans_type == "Merchant payments"].groupby("states").trans_counts.sum()
    comp = pd.DataFrame({"depth": ag.c / users, "merchant": mer / ag.c, "ticket": ag.a / ag.c})
    prev = [k - 10 for k in keys]
    if min(prev) >= 20181:
        comp["growth"] = ag.a / TX[TX.p.isin(prev)].groupby("states").amount.sum() - 1
    else:
        comp["growth"] = STATE_CAGR
    g["score"] = comp.rank(pct=True).mean(axis=1) * 100
    return g.reset_index()


@st.cache_data
def panel(cat, grain):
    t = TX if cat == ALLC else TX[TX.trans_type == cat]
    if grain == "Quarterly":
        g = t.groupby(["states", "p"], as_index=False).agg(txns=("trans_counts", "sum"), amount=("amount", "sum"))
        g = g.merge(USP, on=["states", "p"], how="left")
        g["order"], g["t"] = g.p, g.p.map(LABEL)
    else:
        g = t.groupby(["states", "year"], as_index=False).agg(txns=("trans_counts", "sum"), amount=("amount", "sum"))
        u = USP[USP.p % 10 == 4].assign(year=lambda d: d.p // 10)[["states", "year", "users"]]
        g = g.merge(u, on=["states", "year"], how="left")
        g["order"], g["t"] = g.year, g.year.astype(str)
    return g


def series(cat, grain, state):
    g = panel(cat, grain)
    if state != ALLI:
        g = g[g.states == state]
    s = g.groupby(["order", "t"], as_index=False)[["txns", "amount", "users"]].sum()
    s["ticket"], s["intensity"] = s.amount / s.txns, s.txns / s.users
    return s


def agg(keys, cat, state):
    s = state_table(keys, cat)
    if state != ALLI:
        s = s[s.states == state]
    n, a, u = s.txns.sum(), s.amount.sum(), s.users.sum()
    return dict(txns=n, amount=a, ticket=a / n, users=u, intensity=n / u)


def growth_table(cat, col, basis):
    gcol = col if col != "score" else "amount"
    keys = KEYS
    if basis == "YoY":
        if YEAR == "All years":
            keys = tuple(k for k in KEYS if k // 10 == YEARS[-1])
        prev, n = tuple(k - 10 for k in keys), 1
    elif basis == "QoQ":
        last = max(KEYS)
        keys, prev, n = (last,), (last - 1 if last % 10 > 1 else last - 7,), 1
    else:
        qs = sorted({k % 10 for k in KEYS})
        keys = tuple(YEARS[-1] * 10 + x for x in qs)
        prev, n = tuple(YEARS[0] * 10 + x for x in qs), YEARS[-1] - YEARS[0]
    if min(prev) < 20181:
        return None
    cur, old = state_table(keys, cat), state_table(prev, cat)
    m = cur.merge(old[["states", gcol]], on="states", suffixes=("", "_0"))
    m["val"] = m[gcol]
    m["growth"] = (m[gcol] / m[gcol + "_0"]) ** (1 / n) - 1
    m["name"] = m.states.map(pretty)
    return m


@st.cache_data
def dist_table(keys, state):
    t, u = MT[MT.p.isin(keys)], MU[MU.p == max(keys)]
    if state != ALLI:
        t, u = t[t.states == state], u[u.states == state]
    g = t.groupby(["states", "district"], as_index=False).agg(txns=("trans_counts", "sum"), amount=("amount", "sum"))
    g = g.merge(u[["states", "district", "users"]], on=["states", "district"], how="left")
    g["ticket"], g["intensity"] = g.amount / g.txns, g.txns / g.users
    g["state_name"] = g.states.map(pretty)
    return g


def map_frame(df):
    """The boundary file folds Ladakh into J&K, so merge the two for map drawing."""
    jk = df[df.states.isin(["jammu-&-kashmir", "ladakh"])]
    if len(jk) < 2:
        return df
    row = dict(states="jammu-&-kashmir", txns=jk.txns.sum(), amount=jk.amount.sum(), users=jk.users.sum(),
               score=jk.score.mean())
    row["ticket"], row["intensity"] = row["amount"] / row["txns"], row["txns"] / row["users"]
    return pd.concat([df[~df.states.isin(jk.states)], pd.DataFrame([row])], ignore_index=True)


def brand_snapshot(state):
    ks = [k for k in KEYS if k <= BR.p.max()] or [BR.p.max()]
    bk = max(ks)
    b = BR[BR.p == bk]
    if state != ALLI:
        b = b[b.states == state]
    b = b.groupby("brand", as_index=False).user_counts.sum()
    b["share"] = b.user_counts / b.user_counts.sum()
    return b.sort_values("share", ascending=False), bk, bk != max(KEYS)


# ───────────────────────── UI helpers ─────────────────────────
_n = [0]


def show(fig, title="", h=420):
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      height=h, margin=dict(l=8, r=8, t=48 if title else 16, b=8), font=dict(color="#d9d0f5"),
                      title=dict(text=title, x=0.01, font=dict(size=15)), legend_title_text="")
    _n[0] += 1
    try:
        st.plotly_chart(fig, width="stretch", key=f"c{_n[0]}")
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, key=f"c{_n[0]}")


def card(label, val, delta, note):
    if delta is None:
        d = f'<span class="na">{note}</span>'
    else:
        d = f'<span class="{"up" if delta >= 0 else "down"}">{"▲" if delta >= 0 else "▼"} {abs(delta) * 100:.1f}%</span> <span>{note}</span>'
    return f'<div class="kpi"><div class="l">{label}</div><div class="v">{val}</div><div class="d">{d}</div></div>'


def insight(title, body):
    st.markdown(f'<div class="insight"><b>{title}</b><br>{body}</div>', unsafe_allow_html=True)


def kpi_delta(col, cur):
    if YEAR == "All years":
        qs = sorted({k % 10 for k in KEYS})
        a = agg(tuple(YEARS[-1] * 10 + x for x in qs), CAT, FOCUS)[col]
        b = agg(tuple(YEARS[0] * 10 + x for x in qs), CAT, FOCUS)[col]
        return (a / b) ** (1 / (YEARS[-1] - YEARS[0])) - 1, "CAGR 18→22"
    prev = tuple(k - 10 for k in KEYS)
    if min(prev) < 20181:
        return None, "first year of data"
    return cur / agg(prev, CAT, FOCUS)[col] - 1, "vs prior year"


# ───────────────────────── hero + KPI strip ─────────────────────────
st.markdown(
    f'<div class="hero"><h1>Pulse Atlas</h1><p>India’s digital-payments story, 2018–2022 · built on PhonePe Pulse</p>'
    f'<span class="chip">📍 {FOCUS_LBL}</span><span class="chip">🗓 {PERIOD}</span>'
    f'<span class="chip">💳 {CAT}</span><span class="chip">📊 {METRIC}</span></div>',
    unsafe_allow_html=True,
)
cur = agg(KEYS, CAT, FOCUS)
kdefs = [("Transactions", "txns", "count"), ("Value moved", "amount", "money"), ("Avg ticket", "ticket", "rupee"),
         ("Registered users", "users", "count"), ("Txns / user", "intensity", "ratio")]
for c, (lbl, k, kd) in zip(st.columns(5), kdefs):
    dlt, note = kpi_delta(k, cur[k])
    c.markdown(card(lbl, human(cur[k], kd), dlt, note), unsafe_allow_html=True)
st.write("")

tabs = st.tabs(["🗺️ Atlas", "📈 Growth lab", "🧬 Payment DNA", "📱 Users & devices",
                "🏙️ District explorer", "⚔️ Head-to-head", "🧠 Briefing"])

# ───────────────────────── 1 · ATLAS ─────────────────────────
with tabs[0]:
    zt = (lambda v: np.log10(pd.Series(v).clip(lower=1e-6))) if LOG else (lambda v: pd.Series(v))
    inv = (lambda t: 10 ** t) if LOG else (lambda t: t)

    def colorbar(zmin, zmax):
        tv = np.linspace(zmin, zmax, 5)
        return dict(tickvals=tv, ticktext=[human(inv(t), KIND) for t in tv], thickness=10, len=0.7, title="")

    left, right = st.columns([1.75, 1])
    with left:
        if MAPMODE.startswith("Time"):
            fr = pd.concat([map_frame(state_table((k,), CAT)).assign(period=LABEL[k]) for k in sorted(LABEL)],
                           ignore_index=True)
            fr["z"] = zt(fr[COL]).values
            fr["name"], fr["txt"] = fr.states.map(pretty), fr[COL].map(lambda v: human(v, KIND))
            fig = px.choropleth(fr, geojson=GEO, featureidkey="properties.state", locations="states", color="z",
                                animation_frame="period", range_color=(fr.z.min(), fr.z.max()),
                                color_continuous_scale=CSCALE, hover_name="name",
                                hover_data={"txt": True, "z": False, "states": False, "period": False},
                                labels={"txt": METRIC})
            fig.update_coloraxes(colorbar=colorbar(fr.z.min(), fr.z.max()))
            fig.update_geos(fitbounds="locations", visible=False)
            fig.update_traces(marker_line_color="#0a0714", marker_line_width=0.6)
            show(fig, f"Time machine · {METRIC}", 560)
        else:
            full = state_table(KEYS, CAT)
            mf = map_frame(full)
            if MAPSTYLE == "Choropleth":
                z = zt(mf[COL]).values
                hover = [f"<b>{pretty(s)}</b><br>{METRIC}: {human(v, KIND)}" for s, v in zip(mf.states, mf[COL])]
                fig = go.Figure(go.Choropleth(
                    geojson=GEO, featureidkey="properties.state", locations=mf.states, z=z, colorscale=CSCALE,
                    marker_line_color="#0a0714", marker_line_width=0.6, hovertext=hover, hoverinfo="text",
                    colorbar=colorbar(np.nanmin(z), np.nanmax(z))))
            else:
                ids = [f["id"] for f in GEO["features"]]
                base = go.Choropleth(geojson=GEO, featureidkey="properties.state", locations=ids, z=[0] * len(ids),
                                     colorscale=[[0, "#1a1233"], [1, "#1a1233"]], showscale=False,
                                     marker_line_color="#5b4a99", marker_line_width=0.5, hoverinfo="skip")
                f2 = full.dropna(subset=[COL])
                z = zt(f2[COL]).values
                size = 10 + 46 * np.sqrt(f2[COL].clip(lower=0) / f2[COL].max())
                hover = [f"<b>{pretty(s)}</b><br>{METRIC}: {human(v, KIND)}" for s, v in zip(f2.states, f2[COL])]
                sc = go.Scattergeo(lat=[CENT[s][0] for s in f2.states], lon=[CENT[s][1] for s in f2.states],
                                   text=hover, hoverinfo="text", marker=dict(
                                       size=size, color=z, colorscale=CSCALE, cmin=np.nanmin(z), cmax=np.nanmax(z),
                                       opacity=0.88, line=dict(color="rgba(255,255,255,.6)", width=0.8),
                                       colorbar=colorbar(np.nanmin(z), np.nanmax(z))))
                fig = go.Figure([base, sc])
            fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
            show(fig, f"{METRIC} · {PERIOD} · {CAT}", 560)
        if MAPSTYLE == "Bubble" and MAPMODE.startswith("Time"):
            st.caption("Time machine always renders as a choropleth.")
        st.caption("Ladakh is drawn inside J&K on the map (boundary file predates the 2019 split); charts keep them separate.")

    with right:
        d = state_table(KEYS, CAT).dropna(subset=[COL]).nlargest(TOPN, COL).sort_values(COL)
        fig = go.Figure(go.Bar(
            x=d[COL], y=d.states.map(pretty), orientation="h", text=[human(v, KIND) for v in d[COL]],
            textposition="outside", cliponaxis=False,
            marker_color=["#5eead4" if s == FOCUS else "#8b5cf6" for s in d.states]))
        if LOG:
            fig.update_xaxes(type="log")
        fig.update_xaxes(showgrid=False, showticklabels=False)
        show(fig, f"Top {TOPN} states · {METRIC}", 560)
        st.download_button("⬇ Download state table (CSV)", state_table(KEYS, CAT).to_csv(index=False),
                           "pulse_state_table.csv", "text/csv")

# ───────────────────────── 2 · GROWTH LAB ─────────────────────────
with tabs[1]:
    if COL == "score":
        st.caption("Pulse Score is a snapshot index, so time-series views below use Transaction value.")
    s = series(CAT, GRAIN, FOCUS)
    c1, c2 = st.columns([1.4, 1])
    with c1:
        fig = go.Figure(go.Scatter(x=s.t, y=s[TSCOL], fill="tozeroy", name=TSLBL, line=dict(color="#b388ff", width=3),
                                   fillcolor="rgba(139,92,246,.18)"))
        if GRAIN == "Quarterly":
            fig.add_trace(go.Scatter(x=s.t, y=s[TSCOL].rolling(4).mean(), name="4-quarter average",
                                     line=dict(color="#5eead4", dash="dot", width=2)))
        show(fig, f"{TSLBL} over time · {FOCUS_LBL}", 380)
    with c2:
        sq = series(CAT, "Quarterly", FOCUS)
        sq["g"] = sq[TSCOL].pct_change() * 100
        sq["y"], sq["q"] = (sq.order // 10).astype(str), "Q" + (sq.order % 10).astype(str)
        pv = sq.pivot(index="y", columns="q", values="g")
        fig = go.Figure(go.Heatmap(z=pv.values, x=pv.columns, y=pv.index, colorscale="RdYlGn", zmid=0,
                                   text=np.where(np.isnan(pv.values), "", np.round(pv.values, 0).astype("float")),
                                   texttemplate="%{text:.0f}%", colorbar=dict(thickness=8, title="")))
        fig.update_yaxes(autorange="reversed")
        show(fig, "Quarter-on-quarter growth heat-grid", 380)

    gt = growth_table(CAT, COL, BASIS)
    if gt is None:
        st.info("No earlier period exists for this selection — choose a later year, or switch the growth basis.")
    else:
        c3, c4 = st.columns([1, 1.3])
        with c3:
            d = gt.dropna(subset=["growth"]).nlargest(TOPN, "growth").sort_values("growth")
            fig = go.Figure(go.Bar(x=d.growth * 100, y=d.name, orientation="h",
                                   text=[f"{v * 100:+.0f}%" for v in d.growth], textposition="outside", cliponaxis=False,
                                   marker_color=["#5eead4" if s_ == FOCUS else "#22d3ee" for s_ in d.states]))
            fig.update_xaxes(showgrid=False, showticklabels=False)
            show(fig, f"Fastest growing · {BASIS} · {TSLBL if COL == 'score' else METRIC}", 440)
        with c4:
            m = gt.dropna(subset=["growth", "val", "users"]).copy()
            m = m[m.val > 0]
            mx, my = m.val.median(), m.growth.median()
            m["Quadrant"] = np.where(m.val >= mx, np.where(m.growth >= my, "Stars", "Cash cows"),
                                     np.where(m.growth >= my, "Rising", "Sleepers"))
            m["pct"] = m.growth * 100
            fig = px.scatter(m, x="val", y="pct", size="users", color="Quadrant", hover_name="name", log_x=True,
                             color_discrete_map={"Stars": "#fbbf24", "Rising": "#5eead4", "Cash cows": "#8b5cf6",
                                                 "Sleepers": "#64748b"}, size_max=38, labels={"val": "Size", "pct": "Growth %"})
            fig.add_vline(x=mx, line_dash="dot", line_color="#6b5aa8")
            fig.add_hline(y=my * 100, line_dash="dot", line_color="#6b5aa8")
            show(fig, "Growth matrix — size vs. growth (bubble = users)", 440)

# ───────────────────────── 3 · PAYMENT DNA ─────────────────────────
with tabs[2]:
    vcol = "amount" if COL == "amount" else "trans_counts"
    vlbl = "value" if vcol == "amount" else "count"
    t = TX if FOCUS == ALLI else TX[TX.states == FOCUS]
    t = t.assign(order=t.p if GRAIN == "Quarterly" else t.year)
    t["t"] = t.p.map(LABEL) if GRAIN == "Quarterly" else t.year.astype(str)
    mix = t.groupby(["order", "t", "trans_type"], as_index=False)[vcol].sum().sort_values("order")
    c1, c2 = st.columns(2)
    with c1:
        fig = px.area(mix, x="t", y=vcol, color="trans_type", groupnorm="percent", color_discrete_map=CATCOL)
        fig.update_yaxes(ticksuffix="%")
        show(fig, f"How the payment mix evolved ({vlbl}) · {FOCUS_LBL}", 400)
    with c2:
        k = TX[TX.p.isin(KEYS)]
        ind = k.groupby("trans_type")[vcol].sum()
        foc = (k if FOCUS == ALLI else k[k.states == FOCUS]).groupby("trans_type")[vcol].sum()
        cmp_ = pd.DataFrame({FOCUS_LBL: foc / foc.sum() * 100, "India": ind / ind.sum() * 100}).reset_index()
        fig = px.bar(cmp_.melt("trans_type"), x="trans_type", y="value", color="variable", barmode="group",
                     color_discrete_sequence=["#5eead4", "#8b5cf6"], labels={"value": "Share %", "trans_type": ""})
        show(fig, f"Mix vs. national average · {PERIOD}", 400)
    c3, c4 = st.columns([1.4, 1])
    with c3:
        piv = TX[TX.p.isin(KEYS)].pivot_table(index="states", columns="trans_type", values=vcol, aggfunc="sum")
        shr = piv.div(piv.sum(axis=1), axis=0) * 100
        shr["Archetype"] = piv.idxmax(axis=1).map(ARCH)
        shr["size"] = piv.sum(axis=1)
        shr["name"] = shr.index.map(pretty)
        fig = px.scatter(shr, x="Peer-to-peer payments", y="Merchant payments", color="Archetype", size="size",
                         hover_name="name", size_max=34, labels={"Peer-to-peer payments": "P2P share %",
                                                                 "Merchant payments": "Merchant share %"})
        show(fig, "State archetypes — who pays friends, who pays shops", 420)
    with c4:
        g = k if FOCUS == ALLI else k[k.states == FOCUS]
        tk = g.groupby("trans_type").agg(a=("amount", "sum"), c=("trans_counts", "sum"))
        tk["ticket"] = tk.a / tk.c
        tk = tk.sort_values("ticket")
        fig = go.Figure(go.Bar(x=tk.ticket, y=tk.index, orientation="h", marker_color=[CATCOL[i] for i in tk.index],
                               text=[f"₹{v:,.0f}" for v in tk.ticket], textposition="outside", cliponaxis=False))
        fig.update_xaxes(showgrid=False, showticklabels=False)
        show(fig, "Average ticket by category", 420)

# ───────────────────────── 4 · USERS & DEVICES ─────────────────────────
with tabs[3]:
    su = series(ALLC, GRAIN, FOCUS)
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure(go.Scatter(x=su.t, y=su.users, fill="tozeroy", line=dict(color="#22d3ee", width=3),
                                   fillcolor="rgba(34,211,238,.14)"))
        show(fig, f"Registered users · {FOCUS_LBL}", 330)
    with c2:
        fig = go.Figure(go.Scatter(x=su.t, y=su.intensity, mode="lines+markers", line=dict(color="#fbbf24", width=3)))
        show(fig, "Engagement depth — transactions per registered user", 330)

    c3, c4 = st.columns(2)
    snap, bk, shifted = brand_snapshot(FOCUS)
    with c3:
        top = snap.head(max(TOPN, 8)).sort_values("share")
        fig = go.Figure(go.Bar(x=top.share * 100, y=top.brand, orientation="h",
                               marker_color=["#5eead4" if b == BRAND else "#8b5cf6" for b in top.brand],
                               text=[f"{v * 100:.1f}%" for v in top.share], textposition="outside", cliponaxis=False))
        fig.update_xaxes(showgrid=False, showticklabels=False)
        show(fig, f"Device brand share · {FOCUS_LBL} · {LABEL[bk]}", 400)
    with c4:
        b = BR if FOCUS == ALLI else BR[BR.states == FOCUS]
        b = b.groupby(["p", "brand"], as_index=False).user_counts.sum()
        b["share"] = b.user_counts / b.groupby("p").user_counts.transform("sum") * 100
        b["t"] = b.p.map(LABEL)
        keep = set(snap.brand.head(6)) | ({BRAND} if BRAND != ALLB else set())
        fig = px.line(b[b.brand.isin(keep)].sort_values("p"), x="t", y="share", color="brand",
                      labels={"share": "Share %", "t": ""})
        for tr in fig.data:
            tr.line.width = 5 if tr.name == BRAND else 2
        show(fig, "Brand share over time", 400)
    if shifted:
        st.caption(f"Brand data in this dataset ends at {LABEL[BR.p.max()]}; showing the latest available quarter.")

    e = state_table(KEYS, CAT).dropna(subset=["intensity"]).assign(name=lambda d: d.states.map(pretty))
    fig = px.scatter(e, x="users", y="intensity", size="amount", color="score", hover_name="name", log_x=True,
                     color_continuous_scale=CSCALE, size_max=40, labels={"users": "Registered users",
                                                                          "intensity": "Txns per user", "score": "Pulse"})
    fig.add_hline(y=e.intensity.median(), line_dash="dot", line_color="#6b5aa8")
    show(fig, "Registered ≠ engaged — reach vs. depth (bubble = value, colour = Pulse Score)", 420)

# ───────────────────────── 5 · DISTRICT EXPLORER ─────────────────────────
with tabs[4]:
    dt = dist_table(KEYS, FOCUS)
    dsize = COL if ADDITIVE else "amount"
    dlbl = METRIC if ADDITIVE else "Transaction value"
    dkind = KIND if ADDITIVE else "money"
    ccol = "ticket" if dsize == "txns" else "intensity"
    clbl = "Avg ticket (₹)" if ccol == "ticket" else "Txns per user"
    c1, c2 = st.columns([1.3, 1])
    with c1:
        d = dt.nlargest(60 if FOCUS == ALLI else 40, dsize)
        path = [px.Constant("India" if FOCUS == ALLI else FOCUS_LBL)] + (["state_name"] if FOCUS == ALLI else []) + ["district"]
        fig = px.treemap(d, path=path, values=dsize, color=ccol, color_continuous_scale=CSCALE,
                         labels={ccol: clbl, dsize: dlbl})
        fig.update_traces(marker_line_color="#0a0714")
        show(fig, f"District footprint · size = {dlbl}, colour = {clbl}", 480)
    with c2:
        p = dt.nlargest(15, dsize).reset_index(drop=True)
        p["cum"] = p[dsize].cumsum() / dt[dsize].sum() * 100
        p["label"] = p.district if FOCUS != ALLI else p.district + ", " + p.state_name.str.split().str[0]
        fig = go.Figure([go.Bar(x=p.label, y=p[dsize], marker_color="#8b5cf6", name=dlbl),
                         go.Scatter(x=p.label, y=p.cum, yaxis="y2", name="Cumulative share", mode="lines+markers",
                                    line=dict(color="#5eead4", width=3))])
        fig.update_layout(yaxis2=dict(overlaying="y", side="right", ticksuffix="%", range=[0, 105], showgrid=False),
                          xaxis_tickangle=-45)
        show(fig, "Concentration curve — top 15 districts", 480)
    top3 = dt.nlargest(3, dsize)[dsize].sum() / dt[dsize].sum()
    insight("Concentration check",
            f"The top 3 districts hold <b>{top3 * 100:.0f}%</b> of {dlbl.lower()} in {FOCUS_LBL} for {PERIOD}.")

    st.markdown("##### 🏆 Hall of fame — from Pulse’s *top districts* tables")
    tcol = "amount" if COL == "amount" else "txns"
    tt = TT[TT.p.isin(KEYS)]
    tu = TU[TU.p == max(KEYS)]
    if FOCUS != ALLI:
        tt, tu = tt[tt.states == FOCUS], tu[tu.states == FOCUS]
    tt = tt.rename(columns={"trans_counts": "txns"}).groupby(["states", "district"], as_index=False)[[tcol]].sum()
    h1, h2 = st.columns(2)
    for col_, df_, val, ttl, kd, colr in ((h1, tt, tcol, "Top districts by " + ("value" if tcol == "amount" else "transactions"),
                                           "money" if tcol == "amount" else "count", "#fbbf24"),
                                          (h2, tu, "users", "Top districts by registered users", "count", "#22d3ee")):
        with col_:
            d = df_.groupby(["states", "district"], as_index=False)[val].sum().nlargest(TOPN, val).sort_values(val)
            fig = go.Figure(go.Bar(x=d[val], y=d.district + " · " + d.states.map(lambda s: pretty(s).split()[0]),
                                   orientation="h", marker_color=colr, text=[human(v, kd) for v in d[val]],
                                   textposition="outside", cliponaxis=False))
            fig.update_xaxes(showgrid=False, showticklabels=False)
            show(fig, ttl, 420)

# ───────────────────────── 6 · HEAD-TO-HEAD ─────────────────────────
with tabs[5]:
    s1, s2 = st.columns(2)
    A = RAW[s1.selectbox("Contender A", list(RAW), index=list(RAW).index("Maharashtra"))]
    B = RAW[s2.selectbox("Contender B", list(RAW), index=list(RAW).index("Karnataka"))]
    st_t = state_table(KEYS, CAT).set_index("states")
    gt2 = growth_table(CAT, "amount", "YoY" if BASIS == "YoY" else BASIS)
    st_t["growth"] = gt2.set_index("states").growth if gt2 is not None else STATE_CAGR
    dims = {"Volume": "txns", "Value": "amount", "Users": "users", "Ticket size": "ticket",
            "Engagement": "intensity", "Growth": "growth"}
    pct = st_t[list(dims.values())].rank(pct=True) * 100
    fig = go.Figure()
    for sname, colr in ((A, "#5eead4"), (B, "#f472b6")):
        r = pct.loc[sname].tolist()
        fig.add_trace(go.Scatterpolar(r=r + r[:1], theta=list(dims) + [list(dims)[0]], name=pretty(sname), fill="toself",
                                      line=dict(color=colr, width=3), opacity=0.75))
    fig.update_layout(polar=dict(bgcolor="rgba(0,0,0,0)", radialaxis=dict(range=[0, 100], gridcolor="#3b2a6b")))
    c1, c2 = st.columns([1, 1.2])
    with c1:
        show(fig, "Percentile rank across all states (100 = best)", 430)
    with c2:
        rows = {}
        for nm, kd in (("Transactions", "count"), ("Value", "money"), ("Registered users", "count"),
                       ("Avg ticket", "rupee"), ("Txns / user", "ratio"), ("Pulse Score", "score")):
            key = {"Transactions": "txns", "Value": "amount", "Registered users": "users", "Avg ticket": "ticket",
                   "Txns / user": "intensity", "Pulse Score": "score"}[nm]
            rows[nm] = [human(st_t.loc[A, key], kd), human(st_t.loc[B, key], kd)]
        tbl = pd.DataFrame(rows, index=[pretty(A), pretty(B)]).T
        try:
            st.dataframe(tbl, width="stretch")
        except TypeError:
            st.dataframe(tbl, use_container_width=True)
        fig = go.Figure()
        for sname, colr in ((A, "#5eead4"), (B, "#f472b6")):
            ss = series(CAT, GRAIN, sname)
            fig.add_trace(go.Scatter(x=ss.t, y=ss[TSCOL], name=pretty(sname), line=dict(color=colr, width=3)))
        show(fig, f"{TSLBL} over time", 270)

# ───────────────────────── 7 · BRIEFING ─────────────────────────
with tabs[6]:
    yr = TX.groupby("year")[["trans_counts", "amount"]].sum()
    y0, y1 = YEARS[0], YEARS[-1]
    n = y1 - y0
    cg = lambda c: ((yr[c][y1] / yr[c][y0]) ** (1 / n) - 1) * 100
    S = state_table(KEYS, CAT).dropna(subset=[COL])
    lead = S.loc[S[COL].idxmax()]
    L, R = st.columns(2)
    with L:
        insight("Hyper-growth, not just growth",
                f"Yearly transactions went from {human(yr.trans_counts[y0], 'count')} in {y0} to "
                f"{human(yr.trans_counts[y1], 'count')} in {y1} ({cg('trans_counts'):.0f}% CAGR); value moved "
                f"from {human(yr.amount[y0], 'money')} to {human(yr.amount[y1], 'money')} ({cg('amount'):.0f}% CAGR).")
        share5 = f" The top 5 states hold <b>{S.nlargest(5, COL)[COL].sum() / S[COL].sum() * 100:.0f}%</b> of the total." if ADDITIVE else ""
        insight(f"Who leads on {METRIC.lower()}",
                f"<b>{pretty(lead.states)}</b> is #1 at {human(lead[COL], KIND)} for {PERIOD}.{share5}")
        g = growth_table(CAT, COL, BASIS)
        if g is not None:
            g = g[g.val >= g.val.median()].dropna(subset=["growth"])
            if len(g):
                f = g.loc[g.growth.idxmax()]
                insight(f"Fastest scaling ({BASIS}, above-median size)",
                        f"<b>{f['name']}</b> grew {f.growth * 100:.0f}% — big enough that the growth is meaningful, "
                        f"not just a small-base effect.")
        eng = state_table(KEYS, CAT).dropna(subset=["intensity"])
        e = eng.loc[eng.intensity.idxmax()]
        insight("Deepest engagement",
                f"<b>{pretty(e.states)}</b> users make {e.intensity:,.1f} transactions each in the period — the "
                f"highest depth of any state.")
    with R:
        sh = lambda y, c: TX[(TX.year == y) & (TX.trans_type == c)].trans_counts.sum() / TX[TX.year == y].trans_counts.sum() * 100
        m0, m1, p1 = sh(y0, "Merchant payments"), sh(y1, "Merchant payments"), sh(y1, "Peer-to-peer payments")
        verdict = "merchant payments now out-number P2P" if m1 > p1 else "P2P still leads, with merchants closing in"
        insight("The merchant shift",
                f"Merchant payments went from {m0:.1f}% of transactions in {y0} to {m1:.1f}% in {y1} "
                f"(P2P: {p1:.1f}%) — {verdict}.")
        snap, bk, _ = brand_snapshot(FOCUS)
        top2 = snap.head(2)
        insight("Device landscape",
                f"In {FOCUS_LBL} ({LABEL[bk]}), <b>{top2.iloc[0].brand}</b> leads with {top2.iloc[0].share * 100:.0f}% of "
                f"registered users, followed by {top2.iloc[1].brand} ({top2.iloc[1].share * 100:.0f}%).")
        dn = dist_table(KEYS, ALLI)
        t10 = dn.nlargest(10, "amount").amount.sum() / dn.amount.sum() * 100
        insight("District concentration", f"The top 10 districts account for <b>{t10:.0f}%</b> of national value in {PERIOD}.")
        sc = S.nlargest(3, "score") if "score" in S else None
        if sc is not None:
            insight("Pulse Score podium", " · ".join(f"<b>{pretty(r.states)}</b> ({r.score:.0f})" for r in sc.itertuples()))
    with st.expander("📖 KPI glossary & data notes"):
        st.markdown(
            """
- **Value** is in ₹ (*L Cr* = lakh crore = ₹10¹²). **Transactions** use K / M / B.
- **Registered users** is a *stock* (cumulative), so multi-quarter selections use the last quarter; transactions are *flows* and are summed.
- **Transactions per user** = transactions in the period ÷ registered users at period end (engagement depth).
- **Pulse Score** = average percentile rank of engagement depth, merchant share, average ticket and growth (YoY, or 2018→22 CAGR when no prior year exists).
- **Growth matrix** splits states at the median size and median growth: *Stars*, *Rising*, *Cash cows*, *Sleepers*.
- **Data notes:** brand-level user data ends at 2022 Q1 · *top districts* tables hold each state’s top districts only · Ladakh is merged into J&K on the map only.
"""
        )
