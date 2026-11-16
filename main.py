"""Soil, Water and Crop Mismatch Atlas (Streamlit). Run: streamlit run app/main.py. Reads only data/processed/."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import requests
import datetime as dt

HERE = Path(__file__).resolve().parent
PROC = next((b / "data" / "processed" for b in (HERE, HERE.parent) if (b / "data" / "processed" / "district_index.parquet").exists()), None)
COMP = {"soil": "Soil stress", "water": "Water stress", "equity": "Equity exposure", "crop": "Crop concentration"}
MEAN = {"soil": "a large share of tested soil samples are unhealthy", "water": "little of the cropped land is irrigated",
        "equity": "tribal, Scheduled Caste and marginal farmers form much of the farming base",
        "crop": "farming depends on very few crops, so one shock hits most land"}
PAL = ["#2E7D5B", "#E0A526", "#C0553A", "#3E6C8E", "#8E6AAE"]
DESC = {"Rainfed paddy belt (east & centre)": "Paddy-dominated, mostly unirrigated, sizeable tribal share. The highest-exposure group.",
        "Irrigated rice-wheat plains": "Well irrigated and cereal-heavy; nitrogen is the main soil gap. Lowest water stress.",
        "Semi-arid cotton-soybean-millet plateau": "Large holdings, rainfed-leaning, highest micronutrient deficiency.",
        "Tribal-majority hill & northeast districts": "Mostly tribal and Scheduled Caste farmland, acidic soils, least MSP-listed crop area.",
        "Smallholder plantation & mixed-crop districts": "Marginal holdings, plantation and horticulture mix, high macronutrient stress."}
NUT = ["nitrogen", "organic_carbon", "phosphorus", "potassium", "boron", "zinc", "sulphur", "iron", "manganese", "copper", "soil_ph", "electrical_conductivity"]
FEAT = {"c_soil": "Soil stress (pct)", "c_water": "Water stress (pct)", "c_equity": "Equity exposure (pct)", "c_crop": "Crop concentration (pct)",
        "soil_stress": "Unhealthy soil samples (%)", "water_irrigated_pct": "Irrigated area (%)", "eq_marginal_hold_pct": "Marginal holdings (%)",
        "eq_st_sc_area_pct": "ST+SC share of area (%)", "msp_area_share": "MSP-listed crop area (%)", "crop_hhi": "Crop concentration (HHI)"}

import plotly.io as pio
try:  # keep the custom chart theme in browser dark mode (Streamlit would otherwise re-theme charts)
    from streamlit.delta_generator import DeltaGenerator as _DG
    _dg_pc = _DG.plotly_chart
    _DG.plotly_chart = lambda self, *a, **k: _dg_pc(self, *a, **{"theme": None, **k})
    _st_pc = st.plotly_chart
    st.plotly_chart = lambda *a, **k: _st_pc(*a, **{"theme": None, **k})
except Exception:
    pass
SEQ = ["#fff6e5", "#fcd9a0", "#f2a65a", "#d8683c", "#992e2e"]
_ax = dict(gridcolor="#e8eee9", zerolinecolor="#d5ded8", linecolor="#d5ded8", automargin=True)
pio.templates["atlas"] = go.layout.Template(layout=dict(
    font=dict(family="Inter, sans-serif", color="#2b3a32", size=13), colorway=PAL, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    xaxis=_ax, yaxis=_ax, title=dict(x=0.01, font=dict(size=15, color="#17493a")),
    hoverlabel=dict(bgcolor="white", font=dict(family="Inter", size=12)), legend=dict(orientation="h", y=-0.18, bgcolor="rgba(0,0,0,0)")))
pio.templates.default = "atlas"
st.set_page_config(page_title="Soil, Water & Crop Mismatch Atlas", page_icon="🌾", layout="wide")
if PROC is None:
    st.error("Data files not found. The repo must contain data/processed/district_index.parquet (commit the data/processed folder), "
             "next to this file or one level above it.")
    st.stop()
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif}
:root{color-scheme:light}
.stApp{background:#FAFBF9}
:where(.stApp,[data-testid="stSidebar"]) :where(p,li,label,h1,h2,h3,h4,h5,span,small){color:#1d2b24}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] *{color:#5a6d62!important}
.stTabs [data-baseweb="tab"] p{color:inherit}
[data-baseweb="select"]>div,[data-baseweb="input"]>div{background:#fff!important;border-color:#cfd9d2!important}
[data-baseweb="select"] *{color:#1d2b24!important}
[data-baseweb="popover"] ul,[data-baseweb="menu"]{background:#fff!important}
[data-baseweb="popover"] li,[data-baseweb="popover"] li *{color:#1d2b24!important}
[data-testid="stHeader"]{background:transparent}
#MainMenu,footer,header{visibility:hidden}.block-container{padding-top:1rem;max-width:1280px}
.hero{background:radial-gradient(circle at 88% 15%,#9cc58a 0,transparent 42%),linear-gradient(125deg,#17493a,#2E7D5B);padding:1.8rem 2.2rem;border-radius:20px;margin-bottom:1.2rem;box-shadow:0 10px 30px rgba(23,73,58,.28)}
.hero .eyebrow{font-size:.7rem;letter-spacing:.16em;color:#bfe0c8;font-weight:600}
.hero h1{margin:.2rem 0 .4rem;font-size:2.1rem;font-weight:800;color:#fff;letter-spacing:-.02em}
.hero p{margin:0;color:#e3f2e7;max-width:760px;font-size:1rem}
.chips{margin-top:1rem}.chips span{display:inline-block;background:rgba(255,255,255,.16);color:#fff;border-radius:999px;padding:.2rem .75rem;margin-right:.45rem;font-size:.78rem;font-weight:600}
.kpi{background:#fff;border:1px solid #e3eae5;border-radius:16px;padding:1rem 1.1rem;box-shadow:0 2px 8px rgba(23,73,58,.06);transition:transform .15s,box-shadow .15s}
.kpi:hover{transform:translateY(-2px);box-shadow:0 8px 18px rgba(23,73,58,.14)}
.kpi span{font-size:.7rem;color:#6a7b71;text-transform:uppercase;letter-spacing:.07em;font-weight:600}
.kpi b{display:block;font-size:1.75rem;color:#17493a;letter-spacing:-.02em;margin:.1rem 0}.kpi small{color:#8a9a90;font-size:.78rem}
.insight{background:#fff;color:#2b3a32;border:1px solid #e3eae5;border-left:4px solid #E0A526;padding:.8rem 1.1rem;border-radius:12px;margin:.5rem 0 1.4rem;font-size:.92rem;line-height:1.55}
h3{color:#17493a;font-weight:700;letter-spacing:-.01em;margin-top:1.6rem}
.stTabs [data-baseweb="tab-list"]{gap:4px;overflow-x:auto;border-bottom:1px solid #dfe7e1}
.stTabs [data-baseweb="tab"]{font-weight:600;font-size:.88rem;padding:.55rem .9rem;border-radius:10px 10px 0 0;color:#5a6d62;white-space:nowrap}
.stTabs [aria-selected="true"]{background:#e8f2ec;color:#17493a}
[data-testid="stSidebar"]{background:#f1f5f2;border-right:1px solid #e3eae5}
[data-testid="stPlotlyChart"]{background:#fff;border:1px solid #e8eee9;border-radius:14px;padding:.4rem;box-shadow:0 1px 4px rgba(23,73,58,.04)}
.foot{color:#8a9a90;font-size:.78rem;margin-top:2rem;text-align:center}
</style>""", unsafe_allow_html=True)


@st.cache_data
def load():
    idx = pd.read_parquet(PROC / "district_index.parquet").merge(
        pd.read_csv(PROC / "district_clusters.csv"), on=["state_name", "district_name"], how="left")
    ex = pd.read_csv(PROC / "district_extras.csv").drop(columns=["soil_nitrogen", "soil_stress", "soil_n_samples"])
    idx = idx.merge(ex, on=["state_name", "district_name"], how="left")
    cg = pd.read_csv(PROC / "district_change.csv").drop(columns=["census_ok"])
    idx = idx.merge(cg, on=["state_name", "district_name"], how="left")
    ii = pd.read_csv(PROC / "district_insights.csv")
    idx = idx.merge(ii, on=["state_name", "district_name"], how="left")
    mm = pd.read_csv(PROC / "district_more.csv")
    idx = idx.merge(mm, on=["state_name", "district_name"], how="left")
    idx["key"] = idx.state_name + " | " + idx.district_name
    geo = json.loads((PROC / "district_geo.geojson").read_text())
    for f in geo["features"]:
        f["properties"]["key"] = f["properties"]["state_name"] + " | " + f["properties"]["district_name"]
    return idx, geo, json.loads((PROC / "index_summary.json").read_text()), pd.read_csv(PROC / "cluster_profiles.csv")


idx, geo, summary, prof = load()
ext = json.loads((PROC / "extras_summary.json").read_text())
chg = json.loads((PROC / "change_summary.json").read_text())
ins = json.loads((PROC / "insights_summary.json").read_text())
more = json.loads((PROC / "more_summary.json").read_text())
hs = pd.read_csv(PROC / "state_horticulture.csv")
sc = pd.read_csv(PROC / "state_change.csv")
ranked = idx[idx.dvi.notna()].copy()

# ---- live weather helpers (Open-Meteo, free, no key, non-commercial, CC BY 4.0) ----
FC_URL, AR_URL = "https://api.open-meteo.com/v1/forecast", "https://archive-api.open-meteo.com/v1/archive"
DAILY = "precipitation_sum,et0_fao_evapotranspiration"


@st.cache_data
def centres(_geo):
    out = {}
    for ft in _geo["features"]:
        pts = []
        def walk(c):
            if isinstance(c[0], (int, float)):
                pts.append(c)
            else:
                for x in c:
                    walk(x)
        walk(ft["geometry"]["coordinates"])
        a = np.array(pts)
        out[ft["properties"]["key"]] = (round(float((a[:, 1].min() + a[:, 1].max()) / 2), 2), round(float((a[:, 0].min() + a[:, 0].max()) / 2), 2))
    return out


COORDS = centres(geo)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_forecast(lat, lon):
    try:
        r_ = requests.get(FC_URL, params={"latitude": lat, "longitude": lon, "daily": DAILY, "forecast_days": 7, "timezone": "auto"}, timeout=15)
        r_.raise_for_status(); d_ = r_.json()["daily"]
        return pd.DataFrame({"date": pd.to_datetime(d_["time"]), "rain": pd.to_numeric(d_["precipitation_sum"]), "et0": pd.to_numeric(d_["et0_fao_evapotranspiration"])}), None
    except Exception as e:
        return None, str(e)[:140]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_soil(lat, lon):
    for var in ("soil_moisture_9_to_27cm", "soil_moisture_7_to_28cm", "soil_moisture_9_27cm"):   # variable naming differs across API versions
        try:
            r_ = requests.get(FC_URL, params={"latitude": lat, "longitude": lon, "hourly": var, "forecast_days": 1, "timezone": "auto"}, timeout=15)
            if r_.status_code != 200:
                continue
            v = [x for x in r_.json()["hourly"][var] if x is not None]
            if v:
                return float(np.mean(v)), var
        except Exception:
            continue
    return None, None


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_archive(lat, lon, end):
    try:
        r_ = requests.get(AR_URL, params={"latitude": lat, "longitude": lon, "start_date": "2001-01-01", "end_date": end, "daily": "precipitation_sum", "timezone": "auto"}, timeout=45)
        r_.raise_for_status(); d_ = r_.json()["daily"]
        return pd.Series(pd.to_numeric(d_["precipitation_sum"]).to_numpy(), index=pd.to_datetime(d_["time"])), None
    except Exception as e:
        return None, str(e)[:140]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_multi(lats, lons):
    try:
        r_ = requests.get(FC_URL, params={"latitude": ",".join(map(str, lats)), "longitude": ",".join(map(str, lons)), "daily": DAILY, "forecast_days": 7, "timezone": "auto"}, timeout=30)
        r_.raise_for_status(); j = r_.json(); j = j if isinstance(j, list) else [j]
        return [(float(np.nansum(np.array(x["daily"]["precipitation_sum"], dtype=float))), float(np.nansum(np.array(x["daily"]["et0_fao_evapotranspiration"], dtype=float)))) for x in j], None
    except Exception as e:
        return None, str(e)[:140]


def anomaly(s, n_days):
    s = s.dropna(); end = s.index[-1]
    cur = float(s[end - pd.Timedelta(days=n_days - 1):end].sum()); yrs, hist = [], []
    for y in range(2001, 2021):
        try:
            e = pd.Timestamp(y, end.month, end.day)
        except ValueError:
            e = pd.Timestamp(y, end.month, 28)
        yrs.append(y); hist.append(float(s[e - pd.Timedelta(days=n_days - 1):e].sum()))
    h = np.array(hist)
    return cur, float(h.mean()), float((h < cur).mean() * 100), yrs, hist, end


def _cat_y(fig):
    for t in fig.data:
        try:
            y = t.y
            if y is not None and len(y) and isinstance(y[0], str):
                return True
        except Exception:
            pass
    return False


def sty(fig, h=420):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=50, b=10))
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
    if _cat_y(fig):   # text labels on the vertical axis (district / state / parameter names): reserve room explicitly
        fig.update_layout(margin=dict(l=210, r=20, t=50, b=10))
    return fig


def tip(t):
    st.markdown(f'<div class="insight"><b style="color:#B7791F">&#128161; How to read this</b><br>{t}</div>', unsafe_allow_html=True)


def kpi(col, label, val, sub=""):
    col.markdown(f'<div class="kpi"><span>{label}</span><b>{val}</b><small>{sub}</small></div>', unsafe_allow_html=True)


# ---- sidebar ----
st.sidebar.markdown("#### Index weights")
st.sidebar.caption("Components are nearly uncorrelated, so weights genuinely change the ranking.")
w = {k: st.sidebar.slider(v, 0.0, 1.0, 0.25, 0.05) for k, v in COMP.items()}
if sum(w.values()) == 0:
    w = {k: 1.0 for k in w}
tot = sum(w.values())
ranked["dvi_custom"] = sum(ranked[f"c_{k}"] * w[k] / tot for k in COMP)
ranked["rank_custom"] = ranked.dvi_custom.rank(ascending=False, method="min").astype(int)
state = st.sidebar.selectbox("State", ["All"] + sorted(ranked.state_name.unique()))
cluster = st.sidebar.selectbox("Profile", ["All"] + sorted(ranked.cluster_name.dropna().unique()))
view = ranked.copy()
if state != "All":
    view = view[view.state_name == state]
if cluster != "All":
    view = view[view.cluster_name == cluster]
st.sidebar.caption(f"{len(view)} districts in view")

st.markdown(f'<div class="hero"><div class="eyebrow">AGRICULTURE &middot; DISTRICT ATLAS</div><h1>Soil, Water &amp; Crop Mismatch Atlas</h1>'
            '<p>Where do soil health, irrigation and cropping patterns work against each other, and which farmers are most exposed?</p>'
            f'<div class="chips"><span>{summary["n_districts_total"]} districts</span><span>{summary["n_ranked"]} ranked</span><span>5 public datasets</span><span>17.7M rows</span></div></div>',
            unsafe_allow_html=True)


def cmap(df, col, label, h=560, scale=SEQ):
    base = df[df.has_census & df[col].notna()]
    fig = px.choropleth_map(base, geojson=geo, locations="key", featureidkey="properties.key", color=col, color_continuous_scale=scale,
                            hover_name="district_name", hover_data={"key": False, "state_name": True, "cluster_name": True}, map_style="carto-positron",
                            zoom=3.2 if state == "All" else 5, center={"lat": 22.5, "lon": 80}, opacity=0.82, labels={col: label})
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=h, coloraxis_colorbar=dict(title="", thickness=12, len=0.6))
    fig.update_traces(marker_line_width=0.3, marker_line_color="#ffffff")
    return fig


st_mean = ranked.groupby("state_name").agg(n=("dvi", "size"), dvi=("dvi_custom", "mean")).query("n>=8").sort_values("dvi", ascending=False)
top50 = ranked.nsmallest(50, "rank_custom")
belt = "Rainfed paddy belt (east & centre)"
tabs = st.tabs(["Overview", "Explore", "Rankings", "States", "District profile", "Profiles", "Hotspots & equity", "Change over time", "More insights", "Farms, crops & horticulture", "Compare & peers", "Live priority", "Method"])

# ---- overview ----
with tabs[0]:
    c = st.columns(4)
    kpi(c[0], "Districts ranked", f"{len(ranked)}", f"of {summary['n_districts_total']} with soil data")
    kpi(c[1], "Most exposed state", st_mean.index[0], f"mean index {st_mean.dvi.iloc[0]:.2f}")
    kpi(c[2], "Top 50 in paddy belt", f"{(top50.cluster_name == belt).sum()} of 50", "same profile, mostly east & centre")
    kpi(c[3], "Soil + water double burden", f"{int(ranked.double_burden.sum())}", "districts high on both")
    st.write("")
    l, r = st.columns([3, 2])
    with l:
        st.plotly_chart(cmap(view, "dvi_custom", "Index"), width="stretch")
    with r:
        t = view.nsmallest(12, "rank_custom").iloc[::-1]
        f = px.bar(t, x="dvi_custom", y=t.district_name + ", " + t.state_name.str[:3], orientation="h", color="dvi_custom",
                   color_continuous_scale=SEQ, title="Top 12 districts in view", labels={"dvi_custom": "Index", "y": ""})
        f.update_coloraxes(showscale=False)
        st.plotly_chart(sty(f, 560), width="stretch")
    tip(f"Darker districts combine more soil, water, equity and crop-concentration pressure under your weights. "
        f"{st_mean.index[0]} is highest on average ({st_mean.dvi.iloc[0]:.2f}) and {st_mean.index[-1]} lowest ({st_mean.dvi.iloc[-1]:.2f}). "
        f"{(top50.top_crop == 'Paddy').sum()} of the current top 50 grow mainly paddy.")
    h1, h2 = st.columns(2)
    f = px.histogram(view, x="dvi_custom", nbins=30, color_discrete_sequence=[PAL[0]], title="Distribution of the index", labels={"dvi_custom": "Index"})
    h1.plotly_chart(sty(f, 330), width="stretch")
    cs = ranked[[f"c_{k}" for k in COMP]].corr(method="spearman").round(2)
    cs.index = cs.columns = list(COMP.values())
    h2.plotly_chart(sty(px.imshow(cs, text_auto=True, color_continuous_scale="RdBu_r", zmin=-1, zmax=1, title="Do the components overlap?"), 330), width="stretch")
    tip("The index is spread across districts rather than bunched. The correlation grid shows the four components are close to independent (values near 0), "
        "so a district can be exposed on one dimension and fine on others. That is why the weight sliders matter.")

# ---- explore ----
with tabs[1]:
    a, b, c3 = st.columns(3)
    m = a.selectbox("Map colour", list(FEAT), format_func=FEAT.get, index=4)
    xs = b.selectbox("Scatter X", list(FEAT), format_func=FEAT.get, index=0)
    ys = c3.selectbox("Scatter Y", list(FEAT), format_func=FEAT.get, index=1)
    st.plotly_chart(cmap(view, m, FEAT[m], 480, "Viridis_r" if "irrigated" in m or "msp" in m else SEQ), width="stretch")
    f = px.scatter(view, x=xs, y=ys, color="cluster_name", size="gca", size_max=20, hover_name="district_name", hover_data=["state_name"],
                   color_discrete_sequence=PAL, labels={xs: FEAT[xs], ys: FEAT[ys], "cluster_name": ""}, title=f"{FEAT[ys]} vs {FEAT[xs]}")
    if xs.startswith("c_") and ys.startswith("c_"):
        f.add_vline(x=0.75, line_dash="dot", line_color="#999"); f.add_hline(y=0.75, line_dash="dot", line_color="#999")
    st.plotly_chart(sty(f, 520), width="stretch")
    rho = view[[xs, ys]].corr(method="spearman").iloc[0, 1]
    tip(f"Each bubble is a district (size = cropped area). Spearman correlation between the two axes in this view: <b>{rho:.2f}</b>. "
        "Near zero means no relationship; beyond ±0.4 is a notable link. For percentile axes, the dotted lines mark the top quarter, so the top-right corner is the double burden.")

# ---- rankings ----
with tabs[2]:
    n = st.slider("Districts to show", 10, 40, 20, 5)
    t = view.nsmallest(n, "rank_custom").iloc[::-1]
    parts = pd.DataFrame({COMP[k]: t[f"c_{k}"] * w[k] / tot for k in COMP})
    parts["d"] = (t.district_name + ", " + t.state_name.str[:3]).values
    f = px.bar(parts.melt("d"), x="value", y="d", color="variable", orientation="h", color_discrete_sequence=PAL,
               labels={"value": "Contribution to index", "d": "", "variable": ""}, title="What drives each district's score")
    st.plotly_chart(sty(f, 120 + 24 * n), width="stretch")
    tip("Each bar splits a district's index into its four weighted components. A long soil segment means the score is mostly a soil problem; "
        "a long water segment means irrigation is the main gap. Districts with the same score can need very different interventions.")
    base = ranked.nsmallest(25, "dvi_rank").iloc[::-1]
    f = go.Figure(go.Scatter(x=base.dvi_rank, y=base.district_name + ", " + base.state_name.str[:3], mode="markers", marker=dict(color="#C0553A", size=9),
                  error_x=dict(type="data", symmetric=False, array=(base.rank_p95 - base.dvi_rank).clip(lower=0), arrayminus=(base.dvi_rank - base.rank_p5).clip(lower=0),
                               color="#aaa", thickness=3)))
    f.update_layout(title="Top 25 (equal weights): how far do ranks move under 5,000 random weightings?", xaxis_title="Rank (1 = most exposed)")
    st.plotly_chart(sty(f, 640), width="stretch")
    s = summary["sensitivity"]
    tip(f"Dots are baseline ranks; grey bars span the 5th to 95th percentile rank. Short bars (Mayurbhanj, Saraikela Kharsawan, Jharsuguda) are robust to weighting; "
        f"long bars depend on how you weight. Across draws a median {s['median_top50_overlap_with_baseline']*100:.0f}% of the top 50 survives.")
    show = view.nsmallest(100, "rank_custom")[["rank_custom", "state_name", "district_name", "cluster_name", "dvi_custom", "top_crop", "top50_stability"]]
    st.dataframe(show.round(2).rename(columns=lambda c: c.replace("_", " ")), hide_index=True, width="stretch")
    st.download_button("Download full table (CSV)", ranked.to_csv(index=False), "district_index.csv")

# ---- states ----
with tabs[3]:
    sm = ranked.groupby("state_name").agg(n=("dvi", "size"), dvi=("dvi_custom", "mean")).query("n>=5").sort_values("dvi")
    f = px.bar(sm.reset_index(), x="dvi", y="state_name", orientation="h", color="dvi", color_continuous_scale=SEQ,
               labels={"dvi": "Mean index", "state_name": ""}, title="Mean index by state (states with 5+ ranked districts)")
    f.update_coloraxes(showscale=False)
    st.plotly_chart(sty(f, 620), width="stretch")
    sp = ranked.groupby("state_name").dvi_custom.agg(["size", "min", "max"]).query("size>=8")
    sp["spread"] = sp["max"] - sp["min"]; sp = sp.sort_values("spread", ascending=False)
    tip(f"State averages hide a lot: the widest gaps between a state's highest and lowest district are in {sp.index[0]} ({sp.spread.iloc[0]:.2f}), {sp.index[1]} ({sp.spread.iloc[1]:.2f}) and {sp.index[2]} ({sp.spread.iloc[2]:.2f}). Use the district tabs for targeting; "
        "use this view for the broad regional pattern (east and north-east high, Punjab and Haryana low).")
    nm = ranked.groupby("state_name")[[f"soil_{x}" for x in NUT]].median()
    nm.columns = [x.replace("_", " ").title() for x in NUT]
    nm = nm[ranked.groupby("state_name").size() >= 5]
    st.plotly_chart(sty(px.imshow(nm.T, color_continuous_scale=SEQ, aspect="auto", labels=dict(color="% unhealthy"),
                                  title="Median % unhealthy soil samples, by state and parameter"), 520), width="stretch")
    tip("Nitrogen and organic carbon are low almost everywhere; the interesting variation is in micronutrients (boron, zinc, iron) and in acidity, "
        "which concentrate in particular states. Blank cells mean the parameter was not tested.")

# ---- district profile ----
with tabs[4]:
    pick = st.selectbox("District", sorted(ranked.key), index=sorted(ranked.key).index("Odisha | Mayurbhanj") if "Odisha | Mayurbhanj" in set(ranked.key) else 0)
    r = ranked[ranked.key == pick].iloc[0]
    l, rr = st.columns(2)
    c = st.columns(3)
    kpi(c[0], "Index", f"{r.dvi_custom:.2f}", f"rank {int(r.rank_custom)} of {len(ranked)}")
    kpi(c[1], "Profile", r.cluster_name.split(" (")[0].split(" &")[0], "")
    kpi(c[2], "Top crop", r.top_crop, f"{r.top_crop_share:.0f}% of listed crop area")
    comps = {k: r[f"c_{k}"] for k in COMP}
    hi = [k for k, v in comps.items() if v >= 0.75]
    lo = [COMP[k] for k, v in comps.items() if v <= 0.25]
    story = (f"<b>{r.district_name}</b> ranks {int(r.rank_custom)} of {len(ranked)}. "
             + ("Its main pressures: " + "; ".join(f"<i>{COMP[k].lower()}</i> ({MEAN[k]})" for k in hi) + ". " if hi else "No component is in the national top quarter. ")
             + (f"It is relatively better off on {', '.join(x.lower() for x in lo)}. " if lo else "")
             + (f"Under equal weights it stays in the top 50 in {r.top50_stability*100:.0f}% of random weightings. " if r.top50_stability > 0 else "")
             + ("It is a soil+water double burden district. " if r.double_burden else "")
             + ("Census link is approximate (boundary changed). " if r.boundary_note == "approx" else ""))
    st.markdown(f'<div class="insight">{story}</div>', unsafe_allow_html=True)
    l, rr = st.columns(2)
    v = list(comps.values())
    rf = go.Figure(go.Scatterpolar(r=v + v[:1], theta=list(COMP.values()) + [COMP["soil"]], fill="toself", line_color=PAL[0]))
    rf.update_layout(polar=dict(radialaxis=dict(range=[0, 1])), showlegend=False, title="Percentile on each component (1 = most exposed)")
    l.plotly_chart(sty(rf, 380), width="stretch")
    nd = pd.DataFrame({"Parameter": [x.replace("_", " ").title() for x in NUT], "This district": [r[f"soil_{x}"] for x in NUT],
                       "National median": [ranked[f"soil_{x}"].median() for x in NUT]}).dropna()
    rr.plotly_chart(sty(px.bar(nd.melt("Parameter"), x="Parameter", y="value", color="variable", barmode="group", color_discrete_sequence=[PAL[0], "#bbb"],
                               labels={"value": "% unhealthy", "variable": ""}, title="Soil: unhealthy samples vs national median"), 380), width="stretch")
    st.caption(f"Soil data {r.soil_year}, {int(r.soil_n_samples):,} samples. Unhealthy = Low (N, P, K, OC), Deficient (B, Cu, Fe, Mn, S, Zn), Acidic (pH), Saline (EC).")

    st.caption(f"Soil stress {r.soil_stress:.1f}% unhealthy, 95% interval about +/-{r.soil_ci:.1f} pts (normal approximation; ignores village clustering).")
    st.markdown("**What if irrigation improved?**")
    up = st.slider("Raise irrigated share of cropped area by (points)", 0, 40, 10, 5)
    nw = max(0.0, r.water_stress - up)
    cw = (ranked.water_stress < nw).mean()
    new = sum((cw if k == "water" else r[f"c_{k}"]) * w[k] / tot for k in COMP)
    new_rank = int((ranked.dvi_custom > new).sum() + 1)
    st.markdown(f'<div class="insight">With +{up} points of irrigation, water stress falls from {r.water_stress:.0f}% to {nw:.0f}%, the index moves from {r.dvi_custom:.2f} to <b>{new:.2f}</b> '
                f'and the rank from {int(r.rank_custom)} to about <b>{new_rank}</b>. Other districts are held fixed, so this is a simple what-if, not a forecast.</div>', unsafe_allow_html=True)

    st.markdown("### Live weather near this district")
    st.caption("Weather: Open-Meteo.com (CC BY 4.0, free non-commercial tier), model data at the district's map centre, not a rain gauge.")
    ll = COORDS.get(pick)
    if ll is None:
        st.info("This district has no map polygon, so live weather is unavailable for it.")
    else:
        lat, lon = ll
        if st.button("Refresh live data", key="refresh_live"):
            fetch_forecast.clear(); fetch_soil.clear(); fetch_archive.clear(); fetch_multi.clear()
        fc, err = fetch_forecast(lat, lon)
        if fc is None:
            st.warning(f"Live weather could not be loaded ({err}). The rest of the app is unaffected.")
        else:
            fc["net"] = fc.rain - fc.et0; bal = float(fc.net.sum())
            f = go.Figure()
            f.add_bar(x=fc.date, y=fc.rain, name="Rain (mm)", marker_color=PAL[3])
            f.add_bar(x=fc.date, y=-fc.et0, name="Crop water demand, ET0 (mm, plotted negative)", marker_color=PAL[1])
            f.add_trace(go.Scatter(x=fc.date, y=fc.net.cumsum(), mode="lines+markers", name="Cumulative balance (mm)", line=dict(color=PAL[2])))
            f.update_layout(barmode="relative", title=f"Next 7 days: rain vs crop water demand near {r.district_name}", yaxis_title="mm")
            st.plotly_chart(sty(f, 380), width="stretch")
            sm, smv = fetch_soil(lat, lon)
            c = st.columns(3)
            kpi(c[0], "Rain, next 7 days", f"{fc.rain.sum():.0f} mm", "forecast total")
            kpi(c[1], "Crop water demand", f"{fc.et0.sum():.0f} mm", "reference crop (ET0), next 7 days")
            kpi(c[2], "Soil moisture", f"{sm:.2f}" if sm is not None else "n/a", "m3/m3 at 9-27 cm, next 24 h" if sm is not None else "not available")
            verdict = (f"demand exceeds rain by about <b>{-bal:.0f} mm</b>: the district is heading into a water deficit, so irrigation or stored soil water will be needed" if bal < -20
                       else f"rain is expected to exceed demand by about <b>{bal:.0f} mm</b>" if bal > 20 else "rain and demand are roughly balanced")
            tip(f"Over the next 7 days {verdict}. ET0 is the water a well-watered reference grass would use; real crops need ET0 times a crop factor that changes with growth stage, so this is a signal, not an irrigation schedule. "
                "Soil moisture is volumetric and depends heavily on soil type, so compare it with this location's own usual range rather than a fixed threshold.")
        st.markdown("#### Rainfall vs the long-term normal")
        nd = st.radio("Window (days)", [30, 60, 90], horizontal=True, key="anom_n")
        sr, err2 = fetch_archive(lat, lon, str(dt.date.today() - dt.timedelta(days=5)))
        if sr is None or sr.dropna().empty:
            st.warning(f"Rainfall history could not be loaded ({err2}).")
        else:
            cur, nrm, pct, yrs, hist, aend = anomaly(sr, nd)
            c = st.columns(3)
            kpi(c[0], f"Rain, last {nd} days", f"{cur:.0f} mm", f"to {aend:%d %b %Y}")
            kpi(c[1], "Normal (2001-2020)", f"{nrm:.0f} mm", "same dates, average of 20 years")
            kpi(c[2], "Heavier than", f"{pct:.0f}% of years", "of the 20 baseline years")
            f = go.Figure(go.Bar(x=[str(y) for y in yrs] + ["Now"], y=hist + [cur], marker_color=["#cfd8d2"] * len(yrs) + [PAL[2]]))
            f.update_layout(title=f"Rain over the same {nd}-day window, each year", yaxis_title="mm", showlegend=False)
            st.plotly_chart(sty(f, 330), width="stretch")
            if nrm < 5:
                msg = "little rain is normal for these dates, so a percentage anomaly would be misleading; judge it in millimetres"
            else:
                lab = ("much drier than normal (drought watch)" if pct <= 10 else "drier than normal" if pct <= 25 else "much wetter than normal (flood or waterlogging watch)" if pct >= 90
                       else "wetter than normal" if pct >= 75 else "near normal")
                msg = f"the last {nd} days were <b>{lab}</b>: {cur:.0f} mm against a typical {nrm:.0f} mm ({(cur - nrm) / nrm * 100:+.0f}%)"
            tip(f"For this district, {msg}. Data is ERA5-style reanalysis on a 10 to 25 km grid, ending {aend:%d %b} because the archive lags a few days. It is not station rainfall and local totals can differ a lot.")

# ---- profiles ----
with tabs[5]:
    cm = ranked.groupby("cluster_name")[[f"c_{k}" for k in COMP] + ["dvi"]].median()
    cm.columns = list(COMP.values()) + ["Index"]
    st.plotly_chart(sty(px.imshow(cm, text_auto=".2f", color_continuous_scale=SEQ, aspect="auto", title="Median percentile by profile"), 330), width="stretch")
    cnt = ranked.cluster_name.value_counts().reset_index()
    l, rr = st.columns([2, 3])
    l.plotly_chart(sty(px.pie(cnt, names="cluster_name", values="count", hole=0.5, color_discrete_sequence=PAL, title="Districts per profile"), 380), width="stretch")
    with rr:
        for nme, d in DESC.items():
            sub = ranked[ranked.cluster_name == nme]
            st.markdown(f"**{nme}** ({len(sub)} districts, median index {sub.dvi.median():.2f})  \n{d}")
    tip("Profiles summarise typical combinations of conditions. The rainfed paddy belt stands out on index, water stress and crop concentration. "
        "Silhouette scores are low (0.17 to 0.18), so treat profiles as a descriptive grouping, not hard categories.")

# ---- hotspots & equity ----
with tabs[6]:
    mo = ext["moran"]
    c = st.columns(4)
    kpi(c[0], "Moran's I", f"{mo['I']:.2f}", f"p = {mo['p']:.3f}, {mo['n']} districts")
    kpi(c[1], "Hot spots", f"{ext['lisa_counts'].get('High-High', 0)}", "significant high-exposure clusters")
    kpi(c[2], "Cold spots", f"{ext['lisa_counts'].get('Low-Low', 0)}", "significant low-exposure clusters")
    kpi(c[3], "Tribal irrigation gap", f"{ext['irr_gap_median']:.1f} pts", "median within a district")
    st.write("")
    LC = {"High-High": "#C0553A", "Low-Low": "#2E7D5B", "High-Low": "#E0A526", "Low-High": "#3E6C8E", "Not significant": "#dcdcdc"}
    lv = view[view.lisa.notna() & view.has_census]
    f = px.choropleth_map(lv, geojson=geo, locations="key", featureidkey="properties.key", color="lisa", color_discrete_map=LC, hover_name="district_name",
                          map_style="carto-positron", zoom=3.2 if state == "All" else 5, center={"lat": 22.5, "lon": 80}, opacity=0.82, labels={"lisa": ""})
    f.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=500, legend=dict(orientation="h", y=0.02))
    st.plotly_chart(f, width="stretch")
    tip(f"Moran's I of {mo['I']:.2f} (permutation p = {mo['p']:.3f}) means high-index districts sit next to other high-index districts far more than chance allows: "
        "exposure is a regional pattern, not scattered. Red = significant hot spots (high district among high neighbours), green = cold spots; amber/blue are spatial outliers. "
        "Computed on the equal-weight index with six nearest neighbours.")
    a, b = st.columns(2)
    gp = view.dropna(subset=["irr_gap"]).nlargest(15, "irr_gap").iloc[::-1]
    f = px.bar(gp, x="irr_gap", y=gp.district_name + ", " + gp.state_name.str[:3], orientation="h", color_discrete_sequence=[PAL[2]],
               labels={"irr_gap": "Irrigated share: other farmers minus ST farmers (pts)", "y": ""}, title="Where tribal farms are least irrigated vs their neighbours")
    a.plotly_chart(sty(f, 470), width="stretch")
    f = px.scatter(view, x="msp_growth_pct", y="dvi_custom", color="cluster_name", color_discrete_sequence=PAL, hover_name="district_name",
                   labels={"msp_growth_pct": "Area-weighted MSP growth since 2014-15 (% a year)", "dvi_custom": "Index", "cluster_name": ""}, title="MSP growth of a district's crops vs exposure")
    b.plotly_chart(sty(f, 470), width="stretch")
    rho_m = view[["msp_growth_pct", "dvi_custom"]].corr(method="spearman").iloc[0, 1]
    tip(f"<b>Irrigation gap:</b> the median tribal-vs-other gap <i>within</i> a district is only {ext['irr_gap_median']:.1f} points and {ext['irr_gap_share_positive']*100:.0f}% of districts show tribal farms less irrigated. "
        "So the big irrigation disparity is <i>between</i> districts (tribal areas are in rainfed regions), not inside them. "
        f"<b>MSP:</b> across the districts in view, the rank correlation between MSP growth of a district's crops and its index is {rho_m:+.2f}: faster-growing-MSP districts tend to be <i>less</i> exposed. Part of this is mechanical, because paddy-heavy districts (slower MSP growth) are also the most crop-concentrated, so read it as an association, not an effect of MSP. "
        "MSP is a price floor, not procurement, and coverage is a lower bound.")
    st.plotly_chart(cmap(view, "nitrogen_mismatch", "N mismatch (%)", 430, "Oranges"), width="stretch")
    tip("<b>Nitrogen mismatch</b> = share of area in nitrogen-hungry crops (paddy, wheat, maize, cotton, sugarcane) x share of soil samples low in nitrogen. "
        "The crop list is an <b>assumption</b> from agronomy, not from these datasets. Dark districts grow demanding crops on nitrogen-poor soil.")

# ---- change over time ----
with tabs[7]:
    c = st.columns(4)
    kpi(c[0], "States more irrigated", f"{int(round(chg['state_irr_up_share']*chg['state_n']))} of {chg['state_n']}", f"median {chg['state_irr_median_pp']:+.1f} pts, 2010-11 to 2015-16")
    kpi(c[1], "Marginal holdings", f"{chg['state_marg_median_pp']:+.1f} pts", "median state change in share of holdings")
    kpi(c[2], "Districts compared", f"{chg['district_census_kept']} of {chg['district_census_compared']}", "pass the coverage filter")
    kpi(c[3], "Soil, one year", f"{chg['soil_median_pp']:+.2f} pts", f"median change, {chg['soil_districts']} districts")
    st.markdown("### Agriculture Census: 2010-11 to 2015-16")
    a, b = st.columns(2)
    for col, key, ttl, sg in ((a, "irr_change_pp", "Change in irrigated share (points)", 1), (b, "marg_change_pp", "Change in marginal-holding share (points)", 1)):
        t = sc.sort_values(key)
        f = px.bar(t, x=key, y="state_name", orientation="h", color=t[key] > 0, color_discrete_map={True: PAL[0], False: PAL[2]}, labels={key: "points", "state_name": ""}, title=ttl)
        f.update_layout(showlegend=False)
        col.plotly_chart(sty(f, 640), width="stretch")
    tip(f"Across the {chg['state_n']} states present in both census years, irrigation rose in {chg['state_irr_up_share']*100:.0f}% of them (median {chg['state_irr_median_pp']:+.1f} points) and marginal holdings "
        f"became a larger share of all holdings (median {chg['state_marg_median_pp']:+.1f} points): irrigation is slowly widening while farms keep fragmenting. "
        "Seven states (UP, MP, Rajasthan, Karnataka, Tamil Nadu, Tripura, Puducherry) are missing from the 2010-11 state file, so national totals are not compared.")
    ch = view[view.irr_change_pp.notna()]
    f = cmap(ch, "irr_change_pp", "Irrigation change (pts)", 440, "RdYlGn")
    f.update_coloraxes(cmid=0)
    st.plotly_chart(f, width="stretch")
    tip(f"District view (green = more irrigated). Only {chg['district_census_kept']} of {chg['district_census_compared']} districts with an unchanged name could be compared: the rest were dropped because "
        "cropped area moved by more than 40% or was under 2,000 ha, which points to coverage differences in the 2010-11 tehsil file rather than real change. Of those kept, "
        f"{chg['district_irr_up_share']*100:.0f}% became more irrigated (median {chg['district_irr_median_pp']:+.1f} points). Treat individual districts with caution; the pattern is more reliable than any single value.")
    st.markdown("### Soil Health Card: 2023-24 to 2024-25")
    a, b = st.columns(2)
    sv = view.soil_delta_pp.dropna()
    f = px.histogram(sv, nbins=40, color_discrete_sequence=[PAL[3]], labels={"value": "Change in % unhealthy samples (points)"}, title="District soil change, one year")
    f.add_vline(x=0, line_dash="dot", line_color="#666"); f.update_layout(showlegend=False)
    a.plotly_chart(sty(f, 380), width="stretch")
    nt = pd.Series(chg["soil_by_nutrient_median_pp"]).sort_values().reset_index(); nt.columns = ["Parameter", "pts"]
    b.plotly_chart(sty(px.bar(nt, x="pts", y="Parameter", orientation="h", color_discrete_sequence=[PAL[1]], title="Median change by parameter (points)"), 380), width="stretch")
    f = cmap(view[view.soil_delta_pp.notna()], "soil_delta_pp", "Soil change (pts)", 440, "RdYlGn_r")
    f.update_coloraxes(cmid=0)
    st.plotly_chart(f, width="stretch")
    tip(f"Soil health barely moved: the median district changed by {chg['soil_median_pp']:+.2f} points and {chg['soil_worse_share']*100:.0f}% worsened, close to a coin flip. "
        "Every parameter's median change is within about 0.2 points. With only one year apart, and different villages sampled each year (coverage roughly doubled), "
        "this is best read as <b>no detectable trend</b>, not as stability or improvement. Red = more unhealthy samples, green = fewer.")

# ---- more insights ----
with tabs[8]:
    dc = ins["driver_counts"]
    c = st.columns(4)
    kpi(c[0], "Most common constraint", max(dc, key=dc.get), f"{max(dc.values())} districts")
    kpi(c[1], "One clear driver", f"{ins['clear_margin_share']*100:.0f}%", "lead component ahead by 0.15+")
    kpi(c[2], "Multi-micronutrient", f"{ins['micro_ge4']}", "districts high on 4+ of 6 gaps")
    kpi(c[3], "Z-score agreement", f"{ins['rho_z']:.2f}", "rank correlation with the index")
    DC = {"Soil": PAL[0], "Water": PAL[3], "Equity": PAL[4], "Crop concentration": PAL[1]}
    st.markdown("### What kind of help does each district need?")
    pv = view[view.primary_driver.notna() & view.has_census]
    f = px.choropleth_map(pv, geojson=geo, locations="key", featureidkey="properties.key", color="primary_driver", color_discrete_map=DC, hover_name="district_name",
                          hover_data={"key": False, "state_name": True, "driver_margin": ":.2f"}, map_style="carto-positron", zoom=3.2 if state == "All" else 5,
                          center={"lat": 22.5, "lon": 80}, opacity=0.85, labels={"primary_driver": ""})
    f.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=480, legend=dict(orientation="h", y=0.02))
    f.update_traces(marker_line_width=0.3, marker_line_color="#ffffff")
    st.plotly_chart(f, width="stretch")
    cr = pd.crosstab(view.cluster_name, view.primary_driver).reset_index().melt("cluster_name")
    st.plotly_chart(sty(px.bar(cr, x="value", y="cluster_name", color="primary_driver", orientation="h", color_discrete_map=DC,
                               labels={"value": "districts", "cluster_name": "", "primary_driver": ""}, title="Leading constraint within each profile"), 340), width="stretch")
    tip(f"Each district is coloured by the component where it is most exposed (soil {dc.get('Soil', 0)}, water {dc.get('Water', 0)}, crop concentration {dc.get('Crop concentration', 0)}, "
        f"equity {dc.get('Equity', 0)} districts). Rough reading: <b>soil</b> points to soil testing and micronutrient or organic-carbon programmes, <b>water</b> to irrigation, "
        f"<b>crop concentration</b> to diversification, <b>equity</b> to support targeted at tribal and marginal farmers. Only {ins['clear_margin_share']*100:.0f}% of districts have a clear single driver "
        "(lead of 0.15+ over the runner-up), so for most districts the problems overlap. This is a descriptive guide, not a prescription.")
    st.markdown("### Micronutrient hotspots")
    a, b = st.columns([3, 2])
    a.plotly_chart(cmap(view, "n_micro_hi", "Micronutrients in top quartile", 430, SEQ), width="stretch")
    mo = pd.DataFrame(ins["moran"]).T.reset_index(); mo.columns = ["Parameter", "I", "p"]
    mo["Parameter"] = mo.Parameter.str.replace("_", " ").str.title(); mo = mo.sort_values("I")
    b.plotly_chart(sty(px.bar(mo, x="I", y="Parameter", orientation="h", color_discrete_sequence=[PAL[2]], labels={"I": "Moran's I"}, title="How regionally clustered is each parameter?"), 430), width="stretch")
    sts = ", ".join(f"{k} ({v})" for k, v in ins["micro_ge4_states"].items())
    tip(f"The map counts how many of six micronutrient gaps (boron, zinc, iron, manganese, copper, sulphur) put a district in the national top quarter; {ins['micro_ge4']} districts reach four or more, "
        f"concentrated in {sts}. The chart shows Moran's I per parameter (all significant): nitrogen ({ins['moran']['nitrogen']['I']:.2f}) and organic carbon ({ins['moran']['organic_carbon']['I']:.2f}) are strongly regional, "
        f"while copper ({ins['moran']['copper']['I']:.2f}) is close to random. Regional gaps suit state programmes; scattered ones need district-level testing.")
    st.markdown("### Does the index method matter?")
    rk = ranked.dropna(subset=["z_rank", "pca_rank"])
    f = go.Figure()
    f.add_trace(go.Scatter(x=rk.dvi_rank, y=rk.z_rank, mode="markers", name="Z-score index", marker=dict(color=PAL[0], size=5, opacity=0.6)))
    f.add_trace(go.Scatter(x=rk.dvi_rank, y=rk.pca_rank, mode="markers", name="PCA (first component)", marker=dict(color=PAL[2], size=5, opacity=0.6)))
    f.add_trace(go.Scatter(x=[1, len(rk)], y=[1, len(rk)], mode="lines", name="Same rank", line=dict(color="#999", dash="dot")))
    f.update_layout(xaxis_title="Rank under the percentile index", yaxis_title="Rank under the alternative", title="Rankings under alternative index designs")
    st.plotly_chart(sty(f, 440), width="stretch")
    tip(f"Replacing percentile ranks with z-scores barely changes the picture (rank correlation {ins['rho_z']:.2f}; {ins['overlap50_z']*100:.0f}% of the top 50 is unchanged). "
        f"A PCA-based score disagrees (correlation {ins['rho_pca']:.2f}; only {ins['overlap50_pca']*100:.0f}% of the top 50 overlaps) because the first component explains just {ins['pc1_var']*100:.0f}% of the variance: "
        "the four components do not move together, so one statistical axis cannot summarise them. That supports using an explicit, adjustable weighting.")
    st.markdown("### Inequality within states")
    sp = ranked.groupby("state_name").dvi_custom.agg(["size", "min", "mean", "max"]).query("size>=8")
    sp["spread"] = sp["max"] - sp["min"]; sp = sp.sort_values("spread")
    f = go.Figure()
    for nm, r_ in sp.iterrows():
        f.add_trace(go.Scatter(x=[r_["min"], r_["max"]], y=[nm, nm], mode="lines", line=dict(color="#cfd8d2", width=6), showlegend=False, hoverinfo="skip"))
    f.add_trace(go.Scatter(x=sp["mean"], y=sp.index, mode="markers", marker=dict(color=PAL[2], size=9), name="State mean"))
    f.update_layout(xaxis_title="Index (bar = lowest to highest district)", title="Range of district scores inside each state")
    st.plotly_chart(sty(f, 640), width="stretch")
    tip(f"Bars span each state's lowest to highest district. {sp.index[-1]} has the widest range ({sp.spread.iloc[-1]:.2f}) and {sp.index[0]} the narrowest ({sp.spread.iloc[0]:.2f}). "
        "Where the bar is long, the state average hides districts in very different situations, so targeting should be at district level.")

# ---- farms, crops & horticulture ----
with tabs[9]:
    c = st.columns(4)
    kpi(c[0], "Large vs small farms", f"{more['farm_gap_median']:+.1f} pts", "median irrigation gap inside a district")
    kpi(c[1], "Large farms ahead", f"{more['farm_gap_pos_share']*100:.0f}%", f"of {more['farm_gap_n']} districts with enough data")
    kpi(c[2], "Area changing crop", f"{more['crop_shift_median']:.0f}%", "median district, 2010-11 to 2015-16")
    kpi(c[3], "Horticulture vs exposure", f"{more['hort_rho']:+.2f}", f"state rank correlation, {more['hort_states']} states")
    st.markdown("### Irrigation by farm size")
    fg = view[view.farm_irr_gap.notna()]
    f = cmap(fg, "farm_irr_gap", "Large minus small (pts)", 440, "RdBu")
    f.update_coloraxes(cmid=0)
    st.plotly_chart(f, width="stretch")
    f = px.scatter(fg, x="small_irr", y="large_irr", color="cluster_name", color_discrete_sequence=PAL, hover_name="district_name",
                   labels={"small_irr": "Irrigated share, marginal + small farms (%)", "large_irr": "Irrigated share, medium + large farms (%)", "cluster_name": ""},
                   title="Irrigation on small vs large farms in the same district")
    f.add_shape(type="line", x0=0, y0=0, x1=100, y1=100, line=dict(color="#999", dash="dot"))
    st.plotly_chart(sty(f, 440), width="stretch")
    side = "medium and large farms are better irrigated than marginal and small ones in the same district" if more["farm_gap_median"] > 0 else "marginal and small farms are better irrigated than large ones in the same district"
    tip(f"Across {more['farm_gap_n']} districts (at least 2,000 ha in both groups), the median gap is {more['farm_gap_median']:+.1f} points, and large farms are ahead in {more['farm_gap_pos_share']*100:.0f}%: typically {side}. "
        "Points above the dotted line are districts where large farms are more irrigated. Blue on the map = large farms ahead, red = small farms ahead. Compare with the tribal gap on the Hotspots tab: both gaps inside districts are small next to the differences between districts.")
    st.markdown("### Shifts in crop mix, 2010-11 to 2015-16")
    a, b = st.columns([3, 2])
    a.plotly_chart(cmap(view, "crop_shift", "Area changing crop (%)", 430, SEQ), width="stretch")
    nt = pd.DataFrame({"pp": {**more["crop_gain"], **more["crop_loss"]}}).reset_index().rename(columns={"index": "Crop"}).sort_values("pp")
    f = px.bar(nt, x="pp", y="Crop", orientation="h", color=nt.pp > 0, color_discrete_map={True: PAL[0], False: PAL[2]}, labels={"pp": "change in share of crop area (points)", "Crop": ""}, title="Biggest national gainers and losers")
    f.update_layout(showlegend=False)
    b.plotly_chart(sty(f, 430), width="stretch")
    top = view.nlargest(12, "crop_shift")[["state_name", "district_name", "crop_shift", "top_gain", "top_loss"]].round(1)
    st.dataframe(top.rename(columns={"state_name": "State", "district_name": "District", "crop_shift": "Area changing crop (%)", "top_gain": "Biggest gain", "top_loss": "Biggest loss"}), hide_index=True, width="stretch")
    tip(f"Crop shift is the share of a district's crop area that moved between crops (half the summed absolute change in crop shares). The median district shifted {more['crop_shift_median']:.0f}% in five years. "
        f"Nationally {list(more['crop_gain'])[0]} gained the most share and {list(more['crop_loss'])[0]} lost the most. Only {more['crop_shift_n']} districts pass the coverage filter, and differences in how crops were recorded between census rounds can inflate shifts, so read the pattern, not individual values.")
    st.markdown("### Horticulture and exposure (state level)")
    a, b = st.columns(2)
    f = px.scatter(hs, x="hort_prod_cagr", y="mean_dvi", size="hort_prod_2024_25", text="state_name", color_discrete_sequence=[PAL[0]],
                   labels={"hort_prod_cagr": "Horticulture output growth, 2012-13 to 2024-25 (% a year)", "mean_dvi": "Mean index"}, title="Faster horticulture growth vs state exposure")
    f.update_traces(textposition="top center", textfont_size=9)
    a.plotly_chart(sty(f, 470), width="stretch")
    fc = pd.DataFrame(more["forecast"]).T.reset_index().rename(columns={"index": "Estimate", "median_abs_error_pct": "Median error by crop and state (%)", "mean_abs_national_error_pct": "Mean error nationally (%)"})
    b.plotly_chart(sty(px.bar(fc.melt("Estimate"), x="Estimate", y="value", color="variable", barmode="group", color_discrete_sequence=[PAL[2], PAL[3]],
                              labels={"value": "% error vs final", "variable": ""}, title="How reliable are early horticulture estimates?"), 470), width="stretch")
    rel = "essentially no relationship" if abs(more["hort_rho"]) < 0.2 else ("a modest relationship" if abs(more["hort_rho"]) < 0.4 else "a notable relationship")
    tip(f"Across {more['hort_states']} states with a 2012-13 baseline, horticulture growth and mean exposure show {rel} (rank correlation {more['hort_rho']:+.2f}), so faster diversification into fruits and vegetables is not simply a story of the least exposed states. "
        f"State-level only: horticulture data has no district detail. Forecasts improve with each stage: the first advance estimate misses by a median {more['forecast']['1st advance']['median_abs_error_pct']:.1f}% per crop and state, the third by {more['forecast']['3rd advance']['median_abs_error_pct']:.1f}%, "
        "though national totals are closer than any single crop. Telangana and several small states are absent because they lack a 2012-13 baseline or enough ranked districts.")

# ---- compare & peers ----
with tabs[10]:
    opts = sorted(ranked.key)
    d_lo = ranked.nsmallest(1, "dvi_custom").key.iloc[0]
    d_hi = "Odisha | Mayurbhanj" if "Odisha | Mayurbhanj" in opts else opts[0]
    ca, cb = st.columns(2)
    ka = ca.selectbox("District A", opts, index=opts.index(d_hi), key="cmp_a")
    kb = cb.selectbox("District B", opts, index=opts.index(d_lo), key="cmp_b")
    A = ranked[ranked.key == ka].iloc[0]; B = ranked[ranked.key == kb].iloc[0]
    st.markdown("### Side by side")
    l, r_ = st.columns([2, 3])
    names = list(COMP.values())
    rf = go.Figure()
    for R, col in ((A, PAL[2]), (B, PAL[0])):
        v = [R[f"c_{k}"] for k in COMP]
        rf.add_trace(go.Scatterpolar(r=v + v[:1], theta=names + names[:1], fill="toself", name=R.district_name, line_color=col, opacity=0.6))
    rf.update_layout(polar=dict(radialaxis=dict(range=[0, 1])), title="Percentile on each component")
    l.plotly_chart(sty(rf, 380), width="stretch")
    rows = [("Index (your weights)", "dvi_custom", "{:.2f}"), ("Rank", "rank_custom", "{:.0f}"), ("Irrigated area (%)", "water_irrigated_pct", "{:.0f}"),
            ("Marginal holdings (%)", "eq_marginal_hold_pct", "{:.0f}"), ("ST + SC share of area (%)", "eq_st_sc_area_pct", "{:.0f}"), ("Top crop", "top_crop", "{}"),
            ("Top crop share (%)", "top_crop_share", "{:.0f}"), ("Unhealthy soil samples (%)", "soil_stress", "{:.0f}"), ("Soil samples tested", "soil_n_samples", "{:,.0f}")]
    tb = pd.DataFrame({"Metric": [x[0] for x in rows], f"A: {A.district_name}": [x[2].format(A[x[1]]) for x in rows], f"B: {B.district_name}": [x[2].format(B[x[1]]) for x in rows]})
    r_.dataframe(tb, hide_index=True, width="stretch")
    dif = {COMP[k]: A[f"c_{k}"] - B[f"c_{k}"] for k in COMP}; big = max(dif, key=lambda k: abs(dif[k]))
    tip(f"The biggest difference between {A.district_name} and {B.district_name} is <b>{big.lower()}</b> ({dif[big]:+.2f} in percentile terms, positive = A more exposed). "
        "Defaults compare a highly exposed district with the least exposed one under your weights; change either box to compare any two.")
    st.markdown("### Better-off peers of District A")
    cf = ["cereal_share", "rice_wheat_share", "crop_hhi", "eq_marginal_hold_pct", "eq_st_sc_area_pct"]
    Fm = ranked[cf].copy(); Fm["lg"] = np.log1p(ranked.gca); Fm = Fm.fillna(Fm.median())
    Xm = ((Fm - Fm.mean()) / Fm.std().replace(0, 1)).to_numpy()
    pos = int(np.where(ranked.key.to_numpy() == ka)[0][0])
    dist = np.linalg.norm(Xm - Xm[pos], axis=1); dist[pos] = np.inf
    near = ranked.iloc[np.argsort(dist)[:15]]
    better = near[near.dvi_custom < A.dvi_custom - 0.05].nsmallest(6, "dvi_custom")
    peer_txt = "No clearly better-off peers: District A is already among the least exposed of its peer group."
    if len(better):
        pt = better[["district_name", "state_name", "dvi_custom", "top_crop"]].copy()
        pt.columns = ["District", "State", "Index", "Top crop"]
        pt["Index vs A"] = (better.dvi_custom - A.dvi_custom).round(2)
        for k in COMP:
            pt[COMP[k] + " (pct vs A)"] = (better[f"c_{k}"] - A[f"c_{k}"]).round(2)
        st.dataframe(pt.round(2), hide_index=True, width="stretch")
        gp = {COMP[k]: better[f"c_{k}"].mean() - A[f"c_{k}"] for k in COMP}; lead = min(gp, key=gp.get)
        peer_txt = f"Among the 15 districts most similar in crop mix and farm structure, the better-off ones differ most on <b>{lead.lower()}</b> ({gp[lead]:+.2f} percentile on average vs {A.district_name})."
    tip(peer_txt + " Peers are matched on crop mix (cereal, paddy-wheat and concentration shares), marginal and tribal/SC farm shares and cropped area. "
        "<b>Lower exposure is not the same as higher yield or income</b>: there is no yield data here, so treat peers as benchmarks to study, not proof that a practice works.")
    st.markdown("### Soil tests to prioritise in District A")
    sg = pd.DataFrame({"Parameter": [x.replace("_", " ").title() for x in NUT], "District (% unhealthy)": [A[f"soil_{x}"] for x in NUT],
                       "National median (%)": [ranked[f"soil_{x}"].median() for x in NUT]}).dropna()
    sg["Gap (pts)"] = sg["District (% unhealthy)"] - sg["National median (%)"]; sg = sg.sort_values("Gap (pts)", ascending=False)
    st.dataframe(sg.head(6).round(1), hide_index=True, width="stretch")
    conf = "High"
    if A.xwalk_tier in ("3_code", "4_fuzzy") or A.soil_n_samples < 2000:
        conf = "Medium"
    if A.boundary_note == "approx" or A.soil_n_samples < 800:
        conf = "Low"
    tip(f"Parameters above are those where District A has the most unhealthy samples relative to the national median, so they are the first candidates for closer testing. This describes the gaps; it is <b>not a fertiliser recommendation</b> "
        f"(doses depend on crop, soil type and local advice, so check with the local agriculture extension service). <b>Data confidence: {conf}</b> (rule of thumb: Medium if fewer than 2,000 soil samples or a fuzzy census match; Low if fewer than 800 or an approximate boundary link).")
    top_gap = ", ".join(f"{r.Parameter} ({r['Gap (pts)']:+.0f} pts)" for _, r in sg.head(3).iterrows())
    brief = (f"# District brief: {A.district_name}, {A.state_name}\n\n- Index: {A.dvi_custom:.2f} (rank {int(A.rank_custom)} of {len(ranked)}); profile: {A.cluster_name}\n"
             f"- Components (percentile, 1 = most exposed): " + ", ".join(f"{COMP[k]} {A[f'c_{k}']:.2f}" for k in COMP) + "\n"
             f"- Irrigated area {A.water_irrigated_pct:.0f}%; marginal holdings {A.eq_marginal_hold_pct:.0f}%; ST+SC share of area {A.eq_st_sc_area_pct:.0f}%; top crop {A.top_crop} ({A.top_crop_share:.0f}% of listed crop area)\n"
             f"- Soil: {A.soil_stress:.0f}% of samples unhealthy overall; largest gaps vs national median: {top_gap}\n"
             f"- Better-off peers: " + (", ".join(f"{r.district_name} ({r.state_name})" for r in better.itertuples()) or "none") + "\n"
             f"- Data confidence: {conf}\n\nCaveats: soil data 2023-25 and census 2015-16 (structure, not one moment); associations only; district-level, not farm-level; not agronomic advice.\n")
    st.download_button("Download District A brief (Markdown)", brief, f"{A.district_name}_brief.md".replace(" ", "_"))

# ---- live priority ----
with tabs[11]:
    st.markdown("### Which already-exposed districts face a dry week?")
    st.caption("Exposure index (your weights) combined with the 7-day forecast water deficit (crop water demand minus rain). Weather: Open-Meteo.com (CC BY 4.0, non-commercial).")
    nl = st.slider("Most-exposed districts to check", 10, 60, 30, 5, key="live_n")
    cand = view[view.key.isin(COORDS)].nsmallest(nl, "rank_custom").copy()
    if cand.empty:
        st.info("No mapped districts in the current filter.")
    else:
        la, lo = tuple(COORDS[k][0] for k in cand.key), tuple(COORDS[k][1] for k in cand.key)
        res, errm = fetch_multi(la, lo)
        if res is None or len(res) != len(cand):
            st.warning(f"Live forecast could not be loaded ({errm or 'unexpected response'}). The rest of the app is unaffected.")
        else:
            cand["rain7"], cand["et07"] = [x[0] for x in res], [x[1] for x in res]
            cand["deficit"] = cand.et07 - cand.rain7
            cand["priority"] = (cand.dvi_custom.rank(pct=True) + cand.deficit.rank(pct=True)) / 2
            cand = cand.sort_values("priority", ascending=False)
            f = px.scatter(cand, x="deficit", y="dvi_custom", color="priority", color_continuous_scale=SEQ, hover_name="district_name", hover_data=["state_name"],
                           labels={"deficit": "7-day water deficit (mm, ET0 minus rain; negative = rain exceeds demand)", "dvi_custom": "Exposure index", "priority": "Priority"},
                           title="Exposure vs this week's water deficit")
            f.add_vline(x=float(cand.deficit.median()), line_dash="dot", line_color="#999"); f.add_hline(y=float(cand.dvi_custom.median()), line_dash="dot", line_color="#999")
            st.plotly_chart(sty(f, 460), width="stretch")
            tb = cand[["district_name", "state_name", "rank_custom", "dvi_custom", "rain7", "et07", "deficit", "priority"]].head(15)
            tb.columns = ["District", "State", "Exposure rank", "Index", "Rain 7d (mm)", "Demand 7d (mm)", "Deficit (mm)", "Priority"]
            st.dataframe(tb.round(2), hide_index=True, width="stretch")
            top = cand.iloc[0]
            tip(f"Priority is the average of a district's exposure percentile and its water-deficit percentile within these {len(cand)} districts. Top right of the chart = already vulnerable and facing the driest week; "
                f"right now that is led by <b>{top.district_name}, {top.state_name}</b> (deficit {top.deficit:.0f} mm). In wet spells most deficits are negative, so the ranking then only shows <i>relative</i> dryness. "
                "A one-week forecast is not a drought assessment and crop stage matters; use it to decide where to look closer, and confirm with local field reports.")

# ---- method ----
with tabs[12]:
    s = summary["sensitivity"]
    st.markdown(f"""**Coverage.** {summary['n_districts_total']} soil districts; {summary['n_with_census']} link to the 2015-16 census; {summary['n_ranked']} ranked (soil + census data, at least 500 samples).

**Index.** Four percentile-rank components: *soil* (mean share of unhealthy samples over 12 parameters), *water* (unirrigated share of cropped area), *equity* (ST+SC area share and marginal-holding share), *crop* (Herfindahl concentration). Equity measures **who is exposed**, not how weak a district is.

**Sensitivity.** Over {s['draws']:,} random weightings a median {s['median_top50_overlap_with_baseline']*100:.0f}% of the top {s['top_n']} stays; {s['districts_in_top50_in_90pct_of_draws']} districts stay in 90% of draws.

**Limits.** Soil data is 2023-25 and the census 2010-16 (structure, not one moment). Associations only. Boundaries are 2011, so newer districts have no polygon. MSP coverage is a lower bound. No prices, income or yields.""")

st.markdown('<div class="foot">Data: Soil Health Card, Agriculture Census 2010-16, MSP statements, Horticulture statistics (Ministry of Agriculture &amp; Farmers Welfare). Associations only; see Method for limits.</div>', unsafe_allow_html=True)
