"""Farm-size irrigation gap, district crop shifts, horticulture state overlay -> district_more.csv, state_horticulture.csv, more_summary.json"""
from pathlib import Path
import json, re
import duckdb, numpy as np, pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
PROC, INT = ROOT / "data" / "processed", ROOT / "data" / "interim"
norm = lambda s: re.sub(r"[^a-z0-9]", "", re.sub(r"\bdistrict\b", "", str(s).lower().replace("&", "and")))
con = duckdb.connect(); T = f"'{INT}/agcensus_tehsil.parquet'"
idx = pd.read_parquet(PROC / "district_index.parquet"); idx["k"] = idx.ag_district.fillna("").map(norm)

# 1 farm-size irrigation gap (2015-16): medium+large vs marginal+small
g = con.execute(f"""SELECT state_name, district_name,
  SUM(CASE WHEN farm_size_category IN ('Marginal','Small') THEN total_ar END) s_ar, SUM(CASE WHEN farm_size_category IN ('Marginal','Small') THEN irr_ar END) s_irr,
  SUM(CASE WHEN farm_size_category IN ('Medium','Large') THEN total_ar END) l_ar, SUM(CASE WHEN farm_size_category IN ('Medium','Large') THEN irr_ar END) l_irr
  FROM {T} WHERE year='2015-16' AND crop_code IN (999,1999) GROUP BY ALL""").df()
g["k"] = g.district_name.map(norm)
g = g.groupby(["state_name", "k"], as_index=False)[["s_ar", "s_irr", "l_ar", "l_irr"]].sum()
g["small_irr"], g["large_irr"] = g.s_irr / g.s_ar * 100, g.l_irr / g.l_ar * 100
g["farm_irr_gap"] = np.where((g.s_ar >= 2000) & (g.l_ar >= 2000), g.large_irr - g.small_irr, np.nan)   # >= 2,000 ha in both groups

# 2 crop shifts 2010-11 -> 2015-16 (same coverage filter as change.py)
def yr(y):
    c = con.execute(f"""SELECT state_name, district_name, crop_code, crop_name, SUM(total_ar) ar FROM {T} WHERE year='{y}' AND crop_name IS NOT NULL
        AND crop_code%100!=99 AND crop_code NOT IN (111,121,131,8888) GROUP BY ALL HAVING SUM(total_ar)>0""").df()
    t = con.execute(f"SELECT state_name, district_name, SUM(total_ar) gca FROM {T} WHERE year='{y}' AND crop_code IN (999,1999) GROUP BY ALL").df()
    for d in (c, t):
        d["k"] = d.district_name.map(norm)
    return c.groupby(["state_name", "k", "crop_code", "crop_name"], as_index=False).ar.sum(), t.groupby(["state_name", "k"], as_index=False).gca.sum()

c10, t10 = yr("2010-11"); c15, t15 = yr("2015-16")
t = t10.merge(t15, on=["state_name", "k"], suffixes=("_10", "_15"))
ok = t[((t.gca_15 / t.gca_10 - 1).abs() <= 0.4) & (t.gca_10 >= 2000)][["state_name", "k"]]
m = c10.merge(ok).merge(c15.merge(ok), on=["state_name", "k", "crop_code"], how="outer", suffixes=("_10", "_15"))
m[["ar_10", "ar_15"]] = m[["ar_10", "ar_15"]].fillna(0); m["crop_name"] = m.crop_name_15.fillna(m.crop_name_10)
grp = m.groupby(["state_name", "k"])
m["d"] = (m.ar_15 / grp.ar_15.transform("sum") - m.ar_10 / grp.ar_10.transform("sum")) * 100
cs = m.groupby(["state_name", "k"]).apply(lambda x: pd.Series({"crop_shift": 0.5 * x.d.abs().sum(), "top_gain": x.loc[x.d.idxmax(), "crop_name"], "top_gain_pp": x.d.max(),
        "top_loss": x.loc[x.d.idxmin(), "crop_name"], "top_loss_pp": x.d.min()}), include_groups=False).reset_index()
nat = m.groupby("crop_name")[["ar_10", "ar_15"]].sum()
sh10, sh15 = nat.ar_10 / nat.ar_10.sum(), nat.ar_15 / nat.ar_15.sum()
nat["pp"] = (sh15 - sh10) * 100; nat = nat[(sh10 > 0.005) | (sh15 > 0.005)]
out = idx[["state_name", "district_name", "k"]].merge(g[["state_name", "k", "small_irr", "large_irr", "farm_irr_gap"]], on=["state_name", "k"], how="left").merge(cs, on=["state_name", "k"], how="left")
out.drop(columns=["k"]).to_csv(PROC / "district_more.csv", index=False)

# 3 horticulture state overlay + forecast reliability
h = pd.read_parquet(f"{INT}/horticulture.parquet"); h = h[~h.crop_name.isin(["Honey", "Aromatics & Medicinal"])]
key = ["year", "state_name", "crop_category", "crop_name"]
b = h.assign(r=h.estimate_type.map({"Final Estimates": 0, "3rd Advance Estimates": 1, "2nd Advance Estimates": 2, "1st Advance Estimates": 3})).sort_values("r").drop_duplicates(key)
sy = b.groupby(["state_name", "year"])[["area", "production"]].sum().reset_index()
p, a = sy.pivot(index="state_name", columns="year", values="production"), sy.pivot(index="state_name", columns="year", values="area")
hs = pd.DataFrame({"hort_prod_2024_25": p["2024-25"], "hort_prod_cagr": ((p["2024-25"] / p["2012-13"]) ** (1 / 12) - 1) * 100,
                   "hort_area_cagr": ((a["2024-25"] / a["2012-13"]) ** (1 / 12) - 1) * 100})[p["2012-13"] > 50].dropna().reset_index()
r = idx[idx.dvi.notna()].groupby("state_name").agg(n=("dvi", "size"), mean_dvi=("dvi", "mean")).query("n>=5").reset_index()
hs["k"], r["k"] = hs.state_name.map(norm), r.state_name.map(norm)
hs = r.merge(hs.drop(columns="state_name"), on="k"); hs.drop(columns="k").to_csv(PROC / "state_horticulture.csv", index=False)
fin = h[h.estimate_type == "Final Estimates"].groupby(key).production.first(); fc = {}
for et in ["1st Advance Estimates", "2nd Advance Estimates", "3rd Advance Estimates"]:
    j = pd.concat([h[h.estimate_type == et].groupby(key).production.first().rename("a"), fin.rename("f")], axis=1, join="inner").dropna(); j = j[j.f > 0]
    ny = j.groupby(level="year")[["a", "f"]].sum()
    fc[et.split()[0] + " advance"] = {"median_abs_error_pct": float((abs(j.a - j.f) / j.f).median() * 100), "mean_abs_national_error_pct": float((ny.a / ny.f - 1).abs().mean() * 100)}
gp = out.farm_irr_gap.dropna()
S = {"farm_gap_n": int(len(gp)), "farm_gap_median": float(gp.median()), "farm_gap_pos_share": float((gp > 0).mean()),
     "crop_shift_n": int(out.crop_shift.notna().sum()), "crop_shift_median": float(out.crop_shift.median()),
     "crop_gain": nat.pp.nlargest(8).round(2).to_dict(), "crop_loss": nat.pp.nsmallest(8).round(2).to_dict(),
     "hort_states": int(len(hs)), "hort_rho": float(spearmanr(hs.hort_prod_cagr, hs.mean_dvi)[0]), "hort_unmatched": sorted(set(p.index.map(norm)) - set(hs.state_name.map(norm)))[:10], "forecast": fc}
(PROC / "more_summary.json").write_text(json.dumps(S, indent=1)); print(json.dumps(S, indent=1))
