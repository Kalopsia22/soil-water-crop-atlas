"""More insights -> data/processed/district_insights.csv + insights_summary.json
 primary constraint per district, multi-micronutrient hotspots (+ Moran's I per nutrient), z-score / PCA index comparison."""
from pathlib import Path
import json
import numpy as np, pandas as pd, geopandas as gpd
from scipy.stats import spearmanr
from libpysal.weights import KNN
from esda.moran import Moran

PROC = Path(__file__).resolve().parents[1] / "data" / "processed"
r = pd.read_parquet(PROC / "district_index.parquet"); r = r[r.dvi.notna()].copy()
comp = ["c_soil", "c_water", "c_equity", "c_crop"]; C = r[comp]
lab = {"c_soil": "Soil", "c_water": "Water", "c_equity": "Equity", "c_crop": "Crop concentration"}
srt = np.sort(C.to_numpy(), axis=1)
r["primary_driver"], r["driver_margin"] = C.idxmax(axis=1).map(lab), srt[:, -1] - srt[:, -2]

MICRO = ["boron", "zinc", "iron", "manganese", "copper", "sulphur"]; mc = [f"soil_{m}" for m in MICRO]
r["n_micro_hi"] = (r[mc] >= r[mc].quantile(0.75)).sum(axis=1)     # missing parameters count as not high

cols = ["soil_stress", "water_stress", "crop_hhi"]; Z = (r[cols] - r[cols].mean()) / r[cols].std()
eqv = (r.eq_st_area_pct + r.eq_sc_area_pct + r.eq_marginal_hold_pct) / 2; Z["eq"] = (eqv - eqv.mean()) / eqv.std()
z = Z.mean(axis=1)
X = (C - C.mean()).to_numpy(); u, s, vt = np.linalg.svd(X, full_matrices=False)
pc = X @ vt[0]; pc = pc * np.sign(spearmanr(pc, r.dvi)[0])
r["z_rank"], r["pca_rank"] = z.rank(ascending=False, method="min"), pd.Series(pc, index=r.index).rank(ascending=False, method="min")
top = lambda rank: set(r.index[rank <= 50])
base = top(r.dvi_rank)

geo = gpd.read_file(PROC / "district_geo.geojson"); mor = {}
for n in MICRO + ["nitrogen", "organic_carbon"]:
    g = geo[geo[f"soil_{n}"].notna()].reset_index(drop=True)
    w = KNN.from_dataframe(g, k=6); w.transform = "r"; np.random.seed(42)
    m = Moran(g[f"soil_{n}"].values, w, permutations=499); mor[n] = {"I": float(m.I), "p": float(m.p_sim)}

r[["state_name", "district_name", "primary_driver", "driver_margin", "n_micro_hi", "z_rank", "pca_rank"]].to_csv(PROC / "district_insights.csv", index=False)
hi = r[r.n_micro_hi >= 4]
out = {"driver_counts": r.primary_driver.value_counts().to_dict(), "clear_margin_share": float((r.driver_margin >= 0.15).mean()),
       "micro_ge4": int(len(hi)), "micro_ge4_states": hi.state_name.value_counts().head(4).to_dict(),
       "rho_z": float(spearmanr(z, r.dvi)[0]), "rho_pca": float(spearmanr(pc, r.dvi)[0]), "pc1_var": float((s ** 2 / (s ** 2).sum())[0]),
       "overlap50_z": len(base & top(r.z_rank)) / 50, "overlap50_pca": len(base & top(r.pca_rank)) / 50, "moran": mor}
(PROC / "insights_summary.json").write_text(json.dumps(out, indent=2)); print(json.dumps(out, indent=1))
