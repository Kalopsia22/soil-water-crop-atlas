"""Phase 3: build the district feature table.

Anchor = soil districts (current boundaries). Census features come via the 2015-16 crosswalk.
Output: data/processed/district_features.parquet + .csv

Feature groups
  soil_*     share of soil samples in the unhealthy class, per nutrient (latest year available per district)
  water      irrigated share of gross cropped area
  equity     ST / SC share of cropped area, marginal-holding share of holdings and area
  crop       concentration (HHI, top-crop share), diversity (Shannon), MSP-listed area share
"""
from pathlib import Path
import re
import numpy as np
import pandas as pd
import duckdb

ROOT = Path(__file__).resolve().parents[1]
INTERIM, PROC = ROOT / "data" / "interim", ROOT / "data" / "processed"

# nutrient -> level counted as "unhealthy"
BAD = {"Nitrogen": "Low", "Phosphorus": "Low", "Potassium": "Low", "Organic Carbon": "Low",
       "Boron": "Deficient", "Copper": "Deficient", "Iron": "Deficient", "Manganese": "Deficient",
       "Sulphur": "Deficient", "Zinc": "Deficient", "Soil Ph": "Acidic",
       "Electrical Conductivity": "Saline"}
GROUPS = {"macro": ["Nitrogen", "Phosphorus", "Potassium", "Organic Carbon"],
          "micro": ["Boron", "Copper", "Iron", "Manganese", "Sulphur", "Zinc"],
          "chem": ["Soil Ph", "Electrical Conductivity"]}

# AgCensus crop codes of crops that carry an MSP (Arhar/Tur, Mustard, Sesamum have no separate census
# code, so MSP coverage is a LOWER BOUND). Sugarcane has an FRP rather than an MSP -> kept separate.
MSP_CODES = [101, 102, 103, 104, 105, 106, 107, 201, 203, 204, 205, 1001, 1006, 1007, 1008, 1009, 1010, 1101, 1102]
# Seasonal paddy codes are COMPONENTS of Paddy (101): 111 + 121 + 131 == 101 (verified nationally)
DOUBLE_COUNT_CODES = [111, 121, 131]


def norm(s: str) -> str:
    s = s.lower().replace("&", "and")
    s = re.sub(r"\bdistrict\b|\bdist\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def soil_features(con) -> pd.DataFrame:
    vals = ",".join(f"('{n}','{l}')" for n, l in BAD.items())
    df = con.execute(f"""
        WITH bad(nutrient_name, bad_level) AS (VALUES {vals}),
        d AS (
          SELECT s.year, s.state_name, s.district_name, s.nutrient_name,
                 SUM(s.value) AS total,
                 SUM(CASE WHEN s.nutrient_level = b.bad_level THEN s.value ELSE 0 END) AS bad
          FROM '{INTERIM}/soil.parquet' s JOIN bad b USING (nutrient_name)
          GROUP BY ALL)
        SELECT * FROM d""").df()
    # latest year available per district
    latest = df.groupby(["state_name", "district_name"]).year.transform("max")
    df = df[df.year == latest]
    df["pct"] = np.where(df.total > 0, df.bad / df.total * 100, np.nan)
    wide = df.pivot_table(index=["state_name", "district_name"], columns="nutrient_name", values="pct")
    wide.columns = ["soil_" + c.lower().replace(" ", "_") for c in wide.columns]
    meta = df.groupby(["state_name", "district_name"]).agg(
        soil_year=("year", "first"), soil_n_samples=("total", "max"))
    out = wide.join(meta).reset_index()
    for g, cols in GROUPS.items():
        cc = ["soil_" + c.lower().replace(" ", "_") for c in cols]
        out[f"soil_{g}_stress"] = out[cc].mean(axis=1, skipna=True)
    allc = ["soil_" + c.lower().replace(" ", "_") for c in BAD]
    out["soil_n_nutrients"] = out[allc].notna().sum(axis=1)
    out["soil_stress"] = out[allc].mean(axis=1, skipna=True)
    out.loc[out.soil_n_nutrients < 9, "soil_stress"] = np.nan  # need >= 9 of 12 nutrients
    return out


def census_features(con) -> pd.DataFrame:
    T = f"'{INTERIM}/agcensus_tehsil.parquet'"
    base = con.execute(f"""
        SELECT state_name, district_name,
          SUM(CASE WHEN crop_code IN (999,1999) THEN total_ar END)                       AS gca,
          SUM(CASE WHEN crop_code IN (999,1999) THEN irr_ar END)                         AS gca_irr,
          SUM(CASE WHEN crop_code IN (999,1999) AND social_group='Scheduled Tribe' THEN total_ar END)  AS gca_st,
          SUM(CASE WHEN crop_code IN (999,1999) AND social_group='Scheduled Caste' THEN total_ar END)  AS gca_sc,
          SUM(CASE WHEN crop_code IN (999,1999) AND farm_size_category='Marginal' THEN total_ar END)   AS gca_marg,
          SUM(CASE WHEN crop_code = 999 THEN hold_no END)                                AS hold_all,
          SUM(CASE WHEN crop_code = 999 AND farm_size_category='Marginal' THEN hold_no END) AS hold_marg,
          SUM(CASE WHEN crop_code = 999 AND social_group='Scheduled Tribe' THEN hold_no END) AS hold_st
        FROM {T} WHERE year='2015-16' GROUP BY ALL""").df()
    crops = con.execute(f"""
        SELECT state_name, district_name, crop_code, crop_name, SUM(total_ar) AS ar
        FROM {T}
        WHERE year='2015-16' AND crop_name IS NOT NULL AND crop_code % 100 != 99
          AND crop_code NOT IN ({','.join(map(str, DOUBLE_COUNT_CODES))}) AND crop_code != 8888
        GROUP BY ALL HAVING SUM(total_ar) > 0""").df()
    # merge duplicate district rows (same district under several census codes)
    for d in (base, crops):
        d["k"] = d.district_name.map(norm)
    base = base.groupby(["state_name", "k"], as_index=False).agg(
        ag_district=("district_name", "first"), **{c: (c, "sum") for c in base.columns
                                                  if c not in ("state_name", "district_name", "k")})
    crops = crops.groupby(["state_name", "k", "crop_code", "crop_name"], as_index=False).ar.sum()

    def crop_stats(g):
        a = g.ar.to_numpy(); tot = a.sum(); p = a / tot
        top = g.loc[g.ar.idxmax()]
        return pd.Series({
            "crop_area_listed": tot,
            "top_crop": top.crop_name, "top_crop_share": top.ar / tot * 100,
            "crop_hhi": float((p ** 2).sum()),
            "crop_shannon": float(-(p * np.log(p)).sum()),
            "crop_n": len(g),
            "msp_area_share": g.loc[g.crop_code.isin(MSP_CODES), "ar"].sum() / tot * 100,
            "sugarcane_share": g.loc[g.crop_code == 401, "ar"].sum() / tot * 100,
            "cereal_share": g.loc[g.crop_code.between(101, 188), "ar"].sum() / tot * 100,
            "rice_wheat_share": g.loc[g.crop_code.isin([101, 106]), "ar"].sum() / tot * 100,
        })
    cs = crops.groupby(["state_name", "k"]).apply(crop_stats, include_groups=False).reset_index()
    df = base.merge(cs, on=["state_name", "k"], how="left")
    df["water_irrigated_pct"] = df.gca_irr / df.gca * 100
    df["water_stress"] = 100 - df.water_irrigated_pct
    df["eq_st_area_pct"] = df.gca_st / df.gca * 100
    df["eq_sc_area_pct"] = df.gca_sc / df.gca * 100
    df["eq_marginal_area_pct"] = df.gca_marg / df.gca * 100
    df["eq_marginal_hold_pct"] = df.hold_marg / df.hold_all * 100
    df["eq_st_hold_pct"] = df.hold_st / df.hold_all * 100
    return df


def main():
    con = duckdb.connect()
    soil = soil_features(con)
    cen = census_features(con)
    xw = pd.read_csv(PROC / "district_crosswalk_2015_16.csv")
    xw["k"] = xw.ag_district.fillna("").map(norm)
    df = soil.merge(xw[["state_name", "soil_district", "tier", "ag_district", "boundary_note", "k"]],
                    left_on=["state_name", "district_name"], right_on=["state_name", "soil_district"], how="left")
    cen = cen.drop(columns=["ag_district"])
    df = df.merge(cen, on=["state_name", "k"], how="left").drop(columns=["soil_district", "k"])
    df = df.rename(columns={"tier": "xwalk_tier"})
    df["has_census"] = df.gca.notna()
    df.to_parquet(PROC / "district_features.parquet", index=False)
    df.to_csv(PROC / "district_features.csv", index=False)
    print(f"districts: {len(df)} | with census features: {df.has_census.sum()} | "
          f"soil_stress available: {df.soil_stress.notna().sum()}")
    print("both soil+census:", (df.has_census & df.soil_stress.notna()).sum())


if __name__ == "__main__":
    main()
