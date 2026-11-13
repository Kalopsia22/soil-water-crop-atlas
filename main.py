"""Soil, Water and Crop Mismatch Atlas (Streamlit). Run: streamlit run app/main.py. Reads only data/processed/."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

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

st.set_page_config(page_title="Soil, Water & Crop Mismatch Atlas", page_icon="🌾", layout="wide")
if PROC is None:
    st.error("Data files not found. The repo must contain data/processed/district_index.parquet (commit the data/processed folder), "
             "next to this file or one level above it.")
    st.stop()
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif}
#MainMenu,footer,header{visibility:hidden}.block-container{padding-top:1rem;max-width:1400px}
.hero{background:linear-gradient(120deg,#1f5c43,#2E7D5B 55%,#86b36e);padding:1.5rem 2rem;border-radius:16px;margin-bottom:1rem}
.hero h1{margin:0;font-size:2rem;font-weight:800;color:#fff}.hero p{margin:.3rem 0 0;color:#eaf5ec}
.kpi{background:#fff;border:1px solid #e3eae5;border-radius:14px;padding:.9rem 1.1rem;box-shadow:0 1px 4px rgba(0,0,0,.06)}
.kpi b{display:block;font-size:1.7rem;color:#1f5c43}.kpi span{font-size:.75rem;color:#5b6b62;text-transform:uppercase;letter-spacing:.05em}.kpi small{color:#7a8a80}
.insight{background:#f1f8f3;color:#1d2b24;border-left:4px solid #2E7D5B;padding:.7rem 1rem;border-radius:8px;margin:.4rem 0 1.1rem;font-size:.93rem}
.stTabs [data-baseweb="tab"]{font-weight:600}
</style>""", unsafe_allow_html=True)


@st.cache_data
def load():
    idx = pd.read_parquet(PROC / "district_index.parquet").merge(
        pd.read_csv(PROC / "district_clusters.csv"), on=["state_name", "district_name"], how="left")
    idx["key"] = idx.state_name + " | " + idx.district_name
    geo = json.loads((PROC / "district_geo.geojson").read_text())
    for f in geo["features"]:
        f["properties"]["key"] = f["properties"]["state_name"] + " | " + f["properties"]["district_name"]
    return idx, geo, json.loads((PROC / "index_summary.json").read_text()), pd.read_csv(PROC / "cluster_profiles.csv")


idx, geo, summary, prof = load()
ranked = idx[idx.dvi.notna()].copy()


def sty(fig, h=420):
    fig.update_layout(template="plotly_white", height=h, margin=dict(l=10, r=10, t=45, b=10), font=dict(family="Inter"),
                      title_font=dict(size=15), legend=dict(orientation="h", y=-0.15))
    return fig


def tip(t):
    st.markdown(f'<div class="insight"><b>How to read this.</b> {t}</div>', unsafe_allow_html=True)


def kpi(col, label, val, sub=""):
    col.markdown(f'<div class="kpi"><span>{label}</span><b>{val}</b><small>{sub}</small></div>', unsafe_allow_html=True)


# ---- sidebar ----
st.sidebar.markdown("### Index weights")
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

st.markdown('<div class="hero"><h1>🌾 Soil, Water & Crop Mismatch Atlas</h1><p>Where do soil health, irrigation and cropping '
            'patterns work against each other, and which farmers are most exposed? District-level, from Soil Health Card and Agriculture Census data.</p></div>',
            unsafe_allow_html=True)


def cmap(df, col, label, h=560, scale="YlOrRd"):
    base = df[df.has_census & df[col].notna()]
    fig = px.choropleth_map(base, geojson=geo, locations="key", featureidkey="properties.key", color=col, color_continuous_scale=scale,
                            hover_name="district_name", hover_data={"key": False, "state_name": True, "cluster_name": True}, map_style="carto-positron",
                            zoom=3.2 if state == "All" else 5, center={"lat": 22.5, "lon": 80}, opacity=0.82, labels={col: label})
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=h, coloraxis_colorbar=dict(title="", thickness=12, len=0.6))
    return fig


st_mean = ranked.groupby("state_name").agg(n=("dvi", "size"), dvi=("dvi_custom", "mean")).query("n>=8").sort_values("dvi", ascending=False)
top50 = ranked.nsmallest(50, "rank_custom")
belt = "Rainfed paddy belt (east & centre)"
tabs = st.tabs(["Overview", "Explore", "Rankings", "States", "District profile", "Profiles", "Method"])

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
                   color_continuous_scale="YlOrRd", title="Top 12 districts in view", labels={"dvi_custom": "Index", "y": ""})
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
    st.plotly_chart(cmap(view, m, FEAT[m], 480, "Viridis_r" if "irrigated" in m or "msp" in m else "YlOrRd"), width="stretch")
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
    f = px.bar(sm.reset_index(), x="dvi", y="state_name", orientation="h", color="dvi", color_continuous_scale="YlOrRd",
               labels={"dvi": "Mean index", "state_name": ""}, title="Mean index by state (states with 5+ ranked districts)")
    f.update_coloraxes(showscale=False)
    st.plotly_chart(sty(f, 620), width="stretch")
    tip("State averages hide a lot: Maharashtra and Madhya Pradesh sit mid-table but contain districts at both extremes. Use the district tabs for targeting; "
        "use this view for the broad regional pattern (east and north-east high, Punjab and Haryana low).")
    nm = ranked.groupby("state_name")[[f"soil_{x}" for x in NUT]].median()
    nm.columns = [x.replace("_", " ").title() for x in NUT]
    nm = nm[ranked.groupby("state_name").size() >= 5]
    st.plotly_chart(sty(px.imshow(nm.T, color_continuous_scale="YlOrRd", aspect="auto", labels=dict(color="% unhealthy"),
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

# ---- profiles ----
with tabs[5]:
    cm = ranked.groupby("cluster_name")[[f"c_{k}" for k in COMP] + ["dvi"]].median()
    cm.columns = list(COMP.values()) + ["Index"]
    st.plotly_chart(sty(px.imshow(cm, text_auto=".2f", color_continuous_scale="YlOrRd", aspect="auto", title="Median percentile by profile"), 330), width="stretch")
    cnt = ranked.cluster_name.value_counts().reset_index()
    l, rr = st.columns([2, 3])
    l.plotly_chart(sty(px.pie(cnt, names="cluster_name", values="count", hole=0.5, color_discrete_sequence=PAL, title="Districts per profile"), 380), width="stretch")
    with rr:
        for nme, d in DESC.items():
            sub = ranked[ranked.cluster_name == nme]
            st.markdown(f"**{nme}** ({len(sub)} districts, median index {sub.dvi.median():.2f})  \n{d}")
    tip("Profiles summarise typical combinations of conditions. The rainfed paddy belt stands out on index, water stress and crop concentration. "
        "Silhouette scores are low (0.17 to 0.18), so treat profiles as a descriptive grouping, not hard categories.")

# ---- method ----
with tabs[6]:
    s = summary["sensitivity"]
    st.markdown(f"""**Coverage.** {summary['n_districts_total']} soil districts; {summary['n_with_census']} link to the 2015-16 census; {summary['n_ranked']} ranked (soil + census data, at least 500 samples).

**Index.** Four percentile-rank components: *soil* (mean share of unhealthy samples over 12 parameters), *water* (unirrigated share of cropped area), *equity* (ST+SC area share and marginal-holding share), *crop* (Herfindahl concentration). Equity measures **who is exposed**, not how weak a district is.

**Sensitivity.** Over {s['draws']:,} random weightings a median {s['median_top50_overlap_with_baseline']*100:.0f}% of the top {s['top_n']} stays; {s['districts_in_top50_in_90pct_of_draws']} districts stay in 90% of draws.

**Limits.** Soil data is 2023-25 and the census 2010-16 (structure, not one moment). Associations only. Boundaries are 2011, so newer districts have no polygon. MSP coverage is a lower bound. No prices, income or yields.""")
