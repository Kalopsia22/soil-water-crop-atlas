"""Data-integrity and logic tests. Run:  pytest -q   (after running the pipeline)"""
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
INTERIM, PROC = ROOT / "data" / "interim", ROOT / "data" / "processed"
EXPECTED_ROWS = {"soil": 10_853_209, "agcensus_tehsil": 6_495_760, "agcensus_state": 165_560,
                 "msp": 845, "horticulture": 134_919}

needs_interim = pytest.mark.skipif(not (INTERIM / "soil.parquet").exists(), reason="run src/ingest.py first")
needs_proc = pytest.mark.skipif(not (PROC / "district_index.parquet").exists(), reason="run the pipeline first")


@needs_interim
@pytest.mark.parametrize("name,n", EXPECTED_ROWS.items())
def test_ingest_row_counts(name, n):
    got = duckdb.connect().execute(f"SELECT count(*) FROM '{INTERIM}/{name}.parquet'").fetchone()[0]
    assert got == n


@needs_interim
def test_seasonal_paddy_codes_are_components_of_paddy():
    """Guards the decision to drop codes 111/121/131 from crop-mix features (they double count code 101)."""
    q = f"""SELECT sum(CASE WHEN crop_code=101 THEN total_ar END) p,
                   sum(CASE WHEN crop_code IN (111,121,131) THEN total_ar END) s
            FROM '{INTERIM}/agcensus_tehsil.parquet' WHERE year='2015-16'"""
    p, s = duckdb.connect().execute(q).fetchone()
    assert abs(p - s) / p < 0.01


@needs_proc
def test_crosswalk_quality():
    x = pd.read_csv(PROC / "district_crosswalk_2015_16.csv")
    assert not x.duplicated(["state_name", "soil_district"]).any()
    assert (x.tier != "unmatched").mean() >= 0.90
    m = x[x.ag_district.notna()]
    assert not m.duplicated(["state_name", "ag_district"]).any(), "a census district is claimed twice"


@needs_proc
def test_feature_ranges():
    d = pd.read_parquet(PROC / "district_features.parquet")
    for c in ["water_irrigated_pct", "eq_st_area_pct", "eq_sc_area_pct", "eq_marginal_area_pct",
              "eq_marginal_hold_pct", "msp_area_share", "top_crop_share"]:
        assert d[c].dropna().between(0, 100.0001).all(), c
    assert d.crop_hhi.dropna().between(0, 1).all()
    soil_cols = [c for c in d.columns if c.startswith("soil_") and c.endswith(("nitrogen", "zinc", "boron", "soil_ph"))]
    for c in soil_cols:
        assert d[c].dropna().between(0, 100).all(), c
    assert d.loc[d.soil_stress.notna(), "soil_n_nutrients"].min() >= 9
    assert d.has_census.sum() == d.gca.notna().sum()


@needs_proc
def test_index_logic():
    d = pd.read_parquet(PROC / "district_index.parquet")
    r = d[d.dvi.notna()]
    comp = r[["c_soil", "c_water", "c_equity", "c_crop"]]
    assert comp.min().min() > 0 and comp.max().max() <= 1
    assert np.allclose(r.dvi, comp.mean(axis=1))                       # equal weights
    scaled = (comp * np.array([2, 2, 2, 2])).sum(axis=1) / 8             # weight scale invariance
    assert np.allclose(scaled, r.dvi)
    assert not r.low_sample.any()
    assert r.top50_stability.between(0, 1).all()
    assert (r.rank_p5 <= r.rank_p95).all()
    assert r.dvi_rank.min() == 1 and r.dvi_rank.max() <= len(r)


@needs_proc
def test_clusters_cover_ranked_districts():
    d = pd.read_parquet(PROC / "district_index.parquet")
    c = pd.read_csv(PROC / "district_clusters.csv")
    ranked = d[d.dvi.notna()][["state_name", "district_name"]]
    assert len(ranked.merge(c, on=["state_name", "district_name"])) == len(ranked)
    assert c.cluster_name.nunique() == 5
