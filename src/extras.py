"""Extra analyses -> data/processed/district_extras.csv + extras_summary.json
 1 Moran's I + local hotspots (LISA) on the index   2 within-district irrigation gap (ST vs other farmers)
 3 MSP exposure (area-weighted MSP growth)           4 soil-stress confidence interval
 5 nitrogen mismatch = share of area in N-hungry crops x share of N-low samples (ASSUMPTION: paddy, wheat, maize, cotton, sugarcane)
"""
from pathlib import Path
import json, re
import duckdb, numpy as np, pandas as pd, geopandas as gpd
from libpysal.weights import KNN
from esda.moran import Moran, Moran_Local

ROOT = Path(__file__).resolve().parents[1]
PROC, INT = ROOT / "data" / "processed", ROOT / "data" / "interim"
norm = lambda s: re.sub(r"[^a-z0-9]", "", re.sub(r"\bdistrict\b", "", str(s).lower().replace("&", "and")))
con = duckdb.connect(); T = f"'{INT}/agcensus_tehsil.parquet'"

g = con.execute(f"""SELECT state_name, district_name,
  SUM(CASE WHEN social_group='Scheduled Tribe' THEN total_ar END) st_ar, SUM(CASE WHEN social_group='Scheduled Tribe' THEN irr_ar END) st_irr,
  SUM(CASE WHEN social_group!='Scheduled Tribe' THEN total_ar END) ot_ar, SUM(CASE WHEN social_group!='Scheduled Tribe' THEN irr_ar END) ot_irr
  FROM {T} WHERE year='2015-16' AND crop_code IN (999,1999) GROUP BY ALL""").df()
g["k"] = g.district_name.map(norm)
g = g.groupby(["state_name", "k"], as_index=False)[["st_ar", "st_irr", "ot_ar", "ot_irr"]].sum()
g["irr_st"], g["irr_other"] = g.st_irr / g.st_ar * 100, g.ot_irr / g.ot_ar * 100
g["irr_gap"] = np.where(g.st_ar >= 2000, g.irr_other - g.irr_st, np.nan)      # need >= 2,000 ha of ST cropland

cr = con.execute(f"""SELECT state_name, district_name, crop_code, SUM(total_ar) ar FROM {T}
  WHERE year='2015-16' AND crop_name IS NOT NULL AND crop_code%100!=99 AND crop_code NOT IN (111,121,131,8888)
  GROUP BY ALL HAVING SUM(total_ar)>0""").df()
cr["k"] = cr.district_name.map(norm)
cr = cr.groupby(["state_name", "k", "crop_code"], as_index=False).ar.sum()
m = pd.read_parquet(f"{INT}/msp.parquet"); m["y0"] = m.year.str[:4].astype(int)
PREF = {101: "paddy", 102: "jowar", 103: "bajra", 104: "maize", 105: "ragi", 106: "wheat", 107: "barley", 201: "gram", 203: "urad", 204: "moong",
        205: "masur", 1001: "groundnut", 1007: "sun", 1008: "saff", 1009: "soy", 1010: "niger", 1101: "cotton", 1102: "jute"}


def cagr(p):  # lowest-variety MSP per year since 2014-15, so mid-series variety splits do not distort growth
    d = m[m.crop.str.lower().str.startswith(p) & m.min_support_price.notna() & (m.y0 >= 2014)].groupby("y0").min_support_price.min()
    return (d.iloc[-1] / d.iloc[0]) ** (1 / (d.index[-1] - d.index[0])) - 1 if len(d) > 2 else np.nan


cg = {c: cagr(p) for c, p in PREF.items()}
cr["g"] = cr.crop_code.map(cg)


def agg(x):
    ok = x.g.notna(); a = x.ar[ok]
    return pd.Series({"msp_growth_pct": (x.g[ok] * a).sum() / a.sum() * 100 if a.sum() > 0 else np.nan,
                      "nhungry_share": x.ar[x.crop_code.isin([101, 106, 104, 1101, 401])].sum() / x.ar.sum() * 100})


d = cr.groupby(["state_name", "k"]).apply(agg, include_groups=False).reset_index()
idx = pd.read_parquet(PROC / "district_index.parquet"); idx["k"] = idx.ag_district.fillna("").map(norm)
x = idx[["state_name", "district_name", "k", "soil_nitrogen", "soil_stress", "soil_n_samples"]]
x = x.merge(g[["state_name", "k", "irr_st", "irr_other", "irr_gap"]], on=["state_name", "k"], how="left").merge(d, on=["state_name", "k"], how="left")
p = x.soil_stress / 100
x["soil_ci"] = 1.96 * np.sqrt(p * (1 - p) / x.soil_n_samples) * 100            # normal approximation; ignores village clustering
x["nitrogen_mismatch"] = x.nhungry_share / 100 * x.soil_nitrogen

geo = gpd.read_file(PROC / "district_geo.geojson"); geo = geo[geo.dvi.notna()].reset_index(drop=True)
w = KNN.from_dataframe(geo, k=6); w.transform = "r"
np.random.seed(42)
mi = Moran(geo.dvi.values, w, permutations=999)
ml = Moran_Local(geo.dvi.values, w, permutations=999)
lab = {1: "High-High", 2: "Low-High", 3: "Low-Low", 4: "High-Low"}
geo["lisa"] = [lab[q] if pv < 0.05 else "Not significant" for q, pv in zip(ml.q, ml.p_sim)]
x = x.merge(geo[["state_name", "district_name", "lisa"]], on=["state_name", "district_name"], how="left")
x.drop(columns=["k"]).to_csv(PROC / "district_extras.csv", index=False)
s = {"moran": {"I": float(mi.I), "p": float(mi.p_sim), "k_neighbours": 6, "n": int(len(geo))},
     "lisa_counts": geo.lisa.value_counts().to_dict(), "irr_gap_median": float(x.irr_gap.median()), "irr_gap_n": int(x.irr_gap.notna().sum()),
     "irr_gap_share_positive": float((x.irr_gap.dropna() > 0).mean()), "soil_ci_median_pts": float(x.soil_ci.median()),
     "msp_growth_range": [float(x.msp_growth_pct.min()), float(x.msp_growth_pct.max())]}
(PROC / "extras_summary.json").write_text(json.dumps(s, indent=2)); print(json.dumps(s, indent=2))
