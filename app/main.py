"""Soil, Water and Crop Mismatch Atlas: Streamlit app.

Run:  streamlit run app/main.py
Reads only data/processed/* (no raw data needed), so it deploys as-is.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
COMP = {"soil": "Soil stress", "water": "Water stress", "equity": "Equity exposure", "crop": "Crop concentration"}

st.set_page_config(page_title="Soil, Water & Crop Mismatch Atlas", layout="wide")


@st.cache_data
def load():
    idx = pd.read_parquet(PROC / "district_index.parquet")
    cl = pd.read_csv(PROC / "district_clusters.csv")
    idx = idx.merge(cl, on=["state_name", "district_name"], how="left")
    idx["key"] = idx.state_name + " | " + idx.district_name
    geo = json.loads((PROC / "district_geo.geojson").read_text())
    for f in geo["features"]:
        p = f["properties"]
        f["properties"]["key"] = p["state_name"] + " | " + p["district_name"]
    summary = json.loads((PROC / "index_summary.json").read_text())
    prof = pd.read_csv(PROC / "cluster_profiles.csv")
    return idx, geo, summary, prof


idx, geo, summary, prof = load()
ranked = idx[idx.dvi.notna()].copy()

# ---------------- sidebar ----------------
st.sidebar.header("Index weights")
st.sidebar.caption("The four components are close to uncorrelated, so the weights genuinely change the ranking.")
w = {k: st.sidebar.slider(v, 0.0, 1.0, 0.25, 0.05) for k, v in COMP.items()}
if sum(w.values()) == 0:
    st.sidebar.warning("All weights are zero; using equal weights.")
    w = {k: 1.0 for k in w}
tot = sum(w.values())
ranked["dvi_custom"] = sum(ranked[f"c_{k}"] * w[k] / tot for k in COMP)
ranked["rank_custom"] = ranked.dvi_custom.rank(ascending=False, method="min").astype(int)
states = ["All"] + sorted(ranked.state_name.unique())
state = st.sidebar.selectbox("State", states)
cluster_opts = ["All"] + sorted(ranked.cluster_name.dropna().unique())
cluster = st.sidebar.selectbox("Profile (cluster)", cluster_opts)

view = ranked.copy()
if state != "All":
    view = view[view.state_name == state]
if cluster != "All":
    view = view[view.cluster_name == cluster]

st.title("Soil, Water and Crop Mismatch Atlas")
st.caption("Where do soil health, irrigation and cropping pattern work against each other, and which farmers "
           "are most exposed? District-level, built from Soil Health Card and Agriculture Census data.")

tabs = st.tabs(["Map", "Ranking", "District profile", "Profiles (clusters)", "Method & limits"])

# ---------------- map ----------------
with tabs[0]:
    metric_labels = {"dvi_custom": "Vulnerability index (your weights)", "c_soil": "Soil stress (percentile)",
                     "c_water": "Water stress (percentile)", "c_equity": "Equity exposure (percentile)",
                     "c_crop": "Crop concentration (percentile)", "water_irrigated_pct": "Irrigated share of cropped area (%)",
                     "soil_stress": "Unhealthy soil samples (%)", "msp_area_share": "Area under MSP-listed crops (%, lower bound)",
                     "eq_marginal_hold_pct": "Marginal holdings (% of holdings)"}
    m = st.selectbox("Colour by", list(metric_labels), format_func=metric_labels.get)
    base = idx.drop(columns=[c for c in ["dvi_custom"] if c in idx]).merge(
        ranked[["key", "dvi_custom"]], on="key", how="left")
    base = base[base.has_census]
    if state != "All":
        base = base[base.state_name == state]
    if cluster != "All":
        base = base[base.cluster_name == cluster]
    base = base[base[m].notna()]
    fig = px.choropleth_map(
        base, geojson=geo, locations="key", featureidkey="properties.key", color=m,
        color_continuous_scale="YlOrRd" if m in ("dvi_custom", "c_soil", "c_water", "c_equity", "c_crop") else "Viridis",
        hover_name="district_name", hover_data={"key": False, "state_name": True, "cluster_name": True},
        map_style="carto-positron", zoom=3.3 if state == "All" else 5, center={"lat": 22.5, "lon": 80},
        opacity=0.8, labels={m: metric_labels[m]})
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=620)
    st.plotly_chart(fig, width="stretch")
    st.caption("Boundaries are 2011 census boundaries, so districts created later have no polygon "
               f"(map covers {len(geo['features'])} districts). Grey/absent = no census link or too few soil samples.")

# ---------------- ranking ----------------
with tabs[1]:
    n = st.slider("Show top N districts", 10, 100, 25, 5)
    t = view.nsmallest(n, "rank_custom")[["rank_custom", "state_name", "district_name", "cluster_name", "dvi_custom",
                                          "c_soil", "c_water", "c_equity", "c_crop", "top_crop",
                                          "top50_stability", "rank_p5", "rank_p95", "double_burden"]].copy()
    t.columns = ["Rank", "State", "District", "Profile", "Index", "Soil", "Water", "Equity", "Crop concentration",
                 "Top crop", "Stays in top 50 (share of random weightings)", "Rank p5", "Rank p95", "Soil+water double burden"]
    st.dataframe(t.round(2), hide_index=True, width="stretch")
    st.caption("Stability, rank p5 and p95 describe the *equal-weight* baseline under 5,000 random weightings; "
               "they do not update with your sliders. A wide p5 to p95 range means the position depends on the weights.")
    st.download_button("Download full district table (CSV)", ranked.to_csv(index=False), "district_index.csv")

# ---------------- district profile ----------------
with tabs[2]:
    pick = st.selectbox("District", sorted(ranked.key))
    r = ranked[ranked.key == pick].iloc[0]
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader(r.district_name)
        st.write(f"**{r.state_name}**  |  profile: *{r.cluster_name}*")
        st.metric("Index (your weights)", f"{r.dvi_custom:.2f}", f"rank {int(r.rank_custom)} of {len(ranked)}", delta_color="off")
        st.write(f"Top crop: **{r.top_crop}** ({r.top_crop_share:.0f}% of listed crop area)")
        st.write(f"Under baseline weights it stays in the national top 50 in **{r.top50_stability*100:.0f}%** of 5,000 random "
                 f"weightings (rank range {int(r.rank_p5)} to {int(r.rank_p95)}).")
        if r.double_burden:
            st.warning("Double burden: high soil stress AND high water stress (both in the top quarter nationally).")
        if r.boundary_note == "approx":
            st.info("Census link is approximate: this district's boundary changed after the census.")
        st.caption(f"Soil data: {r.soil_year}, {int(r.soil_n_samples):,} samples tested.")
    with c2:
        vals = [r[f"c_{k}"] for k in COMP]
        rf = go.Figure(go.Scatterpolar(r=vals + vals[:1], theta=list(COMP.values()) + [list(COMP.values())[0]], fill="toself"))
        rf.update_layout(polar=dict(radialaxis=dict(range=[0, 1])), showlegend=False, height=340, margin=dict(t=30, b=10))
        st.plotly_chart(rf, width="stretch")
    nut = [c for c in ranked.columns if c.startswith("soil_") and c.endswith(tuple(["nitrogen", "phosphorus", "potassium", "organic_carbon", "boron", "copper", "iron", "manganese", "sulphur", "zinc", "soil_ph", "electrical_conductivity"]))]
    nd = pd.DataFrame({"Parameter": [c[5:].replace("_", " ").title() for c in nut],
                       "Unhealthy samples (%)": [r[c] for c in nut],
                       "National median (%)": [ranked[c].median() for c in nut]}).dropna()
    bar = px.bar(nd.melt("Parameter"), x="Parameter", y="value", color="variable", barmode="group", height=320,
                 labels={"value": "% of samples", "variable": ""})
    st.plotly_chart(bar, width="stretch")
    st.caption("Unhealthy = Low (N, P, K, organic carbon), Deficient (B, Cu, Fe, Mn, S, Zn), Acidic (pH), Saline (EC).")

# ---------------- clusters ----------------
with tabs[3]:
    st.write("k-means on nine percentile-ranked features, k = 5. Names describe the *typical* member: individual districts can fit poorly.")
    show = prof.copy()
    show.columns = [c.replace("_", " ") for c in show.columns]
    st.dataframe(show.round(2), hide_index=True, width="stretch")
    st.warning("Silhouette scores are low (0.17 to 0.18) for every k from 3 to 8: districts form a continuum, not cleanly separated "
               "groups. Treat profiles as a descriptive summary. Stability under resampling is good (adjusted Rand index about 0.87).")

# ---------------- method ----------------
with tabs[4]:
    s = summary["sensitivity"]
    st.markdown(f"""
**Coverage.** {summary['n_districts_total']} soil districts; {summary['n_with_census']} link to the 2015-16 Agriculture Census;
{summary['n_ranked']} are ranked (soil + census data and at least 500 soil samples).

**Index.** Four components, each a percentile rank among ranked districts: *soil* (mean share of unhealthy samples over 12 parameters),
*water* (unirrigated share of cropped area), *equity* (Scheduled Tribe + Scheduled Caste share of area, and marginal-holding share of holdings),
*crop* (area concentration across crops). Equity measures **who is exposed**, not how weak a district is.

**Sensitivity.** Across {s['draws']:,} random weightings, a median {s['median_top50_overlap_with_baseline']*100:.0f}% of the baseline top {s['top_n']}
stays in the top {s['top_n']}; only {s['districts_in_top50_in_90pct_of_draws']} districts stay in 90% of draws. Components are nearly uncorrelated, so the choice of weights matters.

**Limits.**
- Soil data is 2023-25 and the census 2010-16: the project matches *structure*, not one moment.
- Associations only; nothing here supports causal claims.
- District boundaries changed; {summary['n_districts_total'] - summary['n_with_census']} newer districts have no census link and are not ranked.
- MSP coverage is a lower bound (Arhar/Tur, mustard and sesamum have no separate census code).
- No prices, income or yields.
""")
