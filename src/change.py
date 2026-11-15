"""Change analyses -> data/processed/{district_change.csv, state_change.csv, change_summary.json}
 Census 2010-11 -> 2015-16: irrigated share and marginal-holding share (state file for common states; tehsil file for districts
   whose name is unchanged, dropping districts whose cropped area moved by > 40% or < 2,000 ha, which signals coverage artefacts).
 Soil 2023-24 -> 2024-25: change in % unhealthy samples, same district and parameter, >= 100 samples in both years.
"""
from pathlib import Path
import json
import duckdb, numpy as np, pandas as pd
from features import BAD, norm

ROOT = Path(__file__).resolve().parents[1]
PROC, INT = ROOT / "data" / "processed", ROOT / "data" / "interim"
con = duckdb.connect()
AGG = """SUM(CASE WHEN crop_code IN (999,1999) THEN total_ar END) gca, SUM(CASE WHEN crop_code IN (999,1999) THEN irr_ar END) irr,
         SUM(CASE WHEN crop_code=999 THEN hold_no END) h, SUM(CASE WHEN crop_code=999 AND farm_size_category='Marginal' THEN hold_no END) hm"""

# ---- state level (common states) ----
st = con.execute(f"SELECT year, state_name, {AGG} FROM '{INT}/agcensus_state.parquet' GROUP BY ALL").df()
a, b = st[st.year == "2010-11"].set_index("state_name"), st[st.year == "2015-16"].set_index("state_name")
c = a.join(b, lsuffix="_10", rsuffix="_15", how="inner")
sc = pd.DataFrame({"irr_10": c.irr_10 / c.gca_10 * 100, "irr_15": c.irr_15 / c.gca_15 * 100,
                   "marg_10": c.hm_10 / c.h_10 * 100, "marg_15": c.hm_15 / c.h_15 * 100})
sc["irr_change_pp"], sc["marg_change_pp"] = sc.irr_15 - sc.irr_10, sc.marg_15 - sc.marg_10
sc.reset_index().to_csv(PROC / "state_change.csv", index=False)

# ---- district level (census) ----
def q(y):
    d = con.execute(f"SELECT state_name, district_name, {AGG} FROM '{INT}/agcensus_tehsil.parquet' WHERE year='{y}' GROUP BY ALL").df()
    d["k"] = d.district_name.map(norm)
    return d.groupby(["state_name", "k"], as_index=False)[["gca", "irr", "h", "hm"]].sum()

d = q("2010-11").merge(q("2015-16"), on=["state_name", "k"], suffixes=("_10", "_15"))
d["gca_change_pct"] = (d.gca_15 / d.gca_10 - 1) * 100
d["census_ok"] = (d.gca_change_pct.abs() <= 40) & (d.gca_10 >= 2000)
d["irr_change_pp"] = d.irr_15 / d.gca_15 * 100 - d.irr_10 / d.gca_10 * 100
d["marg_change_pp"] = d.hm_15 / d.h_15 * 100 - d.hm_10 / d.h_10 * 100
d.loc[~d.census_ok, ["irr_change_pp", "marg_change_pp"]] = np.nan
idx = pd.read_parquet(PROC / "district_index.parquet")[["state_name", "district_name", "ag_district"]]
idx["k"] = idx.ag_district.fillna("").map(norm)
d = idx.merge(d[["state_name", "k", "gca_change_pct", "census_ok", "irr_change_pp", "marg_change_pp"]], on=["state_name", "k"], how="left")

# ---- soil ----
bad = ",".join(f"('{n}','{l}')" for n, l in BAD.items())
s = con.execute(f"""WITH b(nutrient_name, lvl) AS (VALUES {bad})
  SELECT s.year, s.state_name, s.district_name, s.nutrient_name, SUM(s.value) tot,
         SUM(CASE WHEN s.nutrient_level=b.lvl THEN s.value ELSE 0 END) bad
  FROM '{INT}/soil.parquet' s JOIN b USING (nutrient_name) GROUP BY ALL""").df()
s["pct"] = np.where(s.tot > 0, s.bad / s.tot * 100, np.nan)
k3 = ["state_name", "district_name", "nutrient_name"]
j = s[s.year == "2023-24"].set_index(k3)[["tot", "pct"]].join(s[s.year == "2024-25"].set_index(k3)[["tot", "pct"]], lsuffix="_23", rsuffix="_24", how="inner")
j = j[(j.tot_23 >= 100) & (j.tot_24 >= 100)].dropna()
j["d"] = j.pct_24 - j.pct_23
nat = j.groupby(level="nutrient_name").d.median().round(2)
sd = j.groupby(level=["state_name", "district_name"]).agg(soil_delta_pp=("d", "mean"), soil_n_params=("d", "size")).reset_index()
sd = sd[sd.soil_n_params >= 9]
out = d.drop(columns=["ag_district", "k"]).merge(sd[["state_name", "district_name", "soil_delta_pp"]], on=["state_name", "district_name"], how="outer")
out.to_csv(PROC / "district_change.csv", index=False)

summ = {"state_n": int(len(sc)), "state_irr_median_pp": float(sc.irr_change_pp.median()), "state_irr_up_share": float((sc.irr_change_pp > 0).mean()),
        "state_marg_median_pp": float(sc.marg_change_pp.median()),
        "district_census_compared": int(d.census_ok.notna().sum()), "district_census_kept": int(d.census_ok.fillna(False).sum()),
        "district_irr_median_pp": float(d.irr_change_pp.median()), "district_irr_up_share": float((d.irr_change_pp.dropna() > 0).mean()),
        "soil_districts": int(len(sd)), "soil_median_pp": float(sd.soil_delta_pp.median()), "soil_worse_share": float((sd.soil_delta_pp > 0).mean()),
        "soil_by_nutrient_median_pp": nat.to_dict()}
(PROC / "change_summary.json").write_text(json.dumps(summ, indent=2)); print(json.dumps(summ, indent=2))
