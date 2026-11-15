"""Phase 5a: attach 2011-census district polygons to the index table for mapping.

The polygons are 2011 boundaries, so districts created later have no polygon. Matching is within state:
  1 exact normalised name against the census-era district name (ag_district), then against the soil district name
  2 fuzzy (rapidfuzz token_sort_ratio >= 88), logged for review
Outputs data/processed/district_geo.geojson (simplified) and a coverage report.
"""
from pathlib import Path
import re
import geopandas as gpd
import pandas as pd
from rapidfuzz import fuzz, process

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
SIMPLIFY_DEG = 0.01   # ~1 km; keeps the file small enough to ship with the app


def norm(s) -> str:
    s = str(s).lower().replace("&", "and")
    s = re.sub(r"\bdistrict\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def main():
    g = gpd.read_file(ROOT / "data" / "raw" / "india_districts_2011.geojson")
    g["sk"], g["dk"] = g.st_nm.map(norm), g.district.map(norm)
    d = pd.read_parquet(PROC / "district_index.parquet")
    cl = pd.read_csv(PROC / "district_clusters.csv")[["state_name", "district_name", "cluster", "cluster_name"]]
    d = d.merge(cl, on=["state_name", "district_name"], how="left")
    d = d[d.has_census].copy()                       # polygons only make sense where census-linked
    d["sk"] = d.state_name.map(norm)

    poly_idx, tier = [], []
    used = set()
    for r in d.itertuples():
        cand = g[g.sk == r.sk]
        hit = None
        for name, t in ((r.ag_district, "exact_census_name"), (r.district_name, "exact_soil_name")):
            m = cand[cand.dk == norm(name)]
            if len(m) and m.index[0] not in used:
                hit, ti = m.index[0], t
                break
        if hit is None and len(cand):
            best = process.extractOne(norm(r.ag_district), cand.dk.tolist(), scorer=fuzz.token_sort_ratio)
            if best and best[1] >= 88:
                i = cand[cand.dk == best[0]].index[0]
                if i not in used:
                    hit, ti = i, f"fuzzy_{best[1]:.0f}"
        poly_idx.append(hit); tier.append(ti if hit is not None else None)
        if hit is not None:
            used.add(hit)
    d["poly_idx"], d["geo_match"] = poly_idx, tier

    m = d[d.poly_idx.notna()].copy()
    out = gpd.GeoDataFrame(m.drop(columns=["poly_idx", "sk"]),
                           geometry=g.loc[m.poly_idx.astype(int), "geometry"].values, crs=g.crs)
    out["geometry"] = out.geometry.simplify(SIMPLIFY_DEG, preserve_topology=True)
    out.to_file(PROC / "district_geo.geojson", driver="GeoJSON")

    n = len(d)
    print(f"census-linked districts: {n} | with polygon: {len(m)} ({len(m)/n*100:.1f}%)")
    print(d.geo_match.fillna("none").str.replace(r"fuzzy_\d+", "fuzzy", regex=True).value_counts().to_string())
    ranked = d[d.dvi.notna()]
    print(f"RANKED districts: {len(ranked)} | mapped: {ranked.poly_idx.notna().sum()} "
          f"({ranked.poly_idx.notna().mean()*100:.1f}%)")
    print("\nfuzzy matches to review:")
    print(d[d.geo_match.fillna('').str.startswith('fuzzy')][["state_name", "district_name", "ag_district", "geo_match"]].to_string(index=False))
    miss = d[d.poly_idx.isna()].groupby("state_name").size().sort_values(ascending=False)
    print("\nunmapped by state:", miss.head(12).to_dict())
    print("file size MB:", round((PROC / "district_geo.geojson").stat().st_size / 1e6, 2))


if __name__ == "__main__":
    main()
