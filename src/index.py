"""Phase 4: District Vulnerability Index (DVI) + sensitivity analysis.

Components (each = percentile rank among districts, 0..1, higher = more exposed):
  soil    mean share of unhealthy soil samples across the 12 tested parameters
  water   1 - irrigated share of gross cropped area
  equity  mean of (Scheduled Tribe + Scheduled Caste share of cropped area) and (marginal-holding share of holdings)
  crop    crop concentration (Herfindahl index over area shares of individual crops)

DVI = weighted mean of components; default weights are equal (0.25 each).
Equity is a measure of WHO is exposed, not of how weak a district is; weights are user-adjustable in the app.

Sensitivity: 5,000 random weight vectors ~ Dirichlet(1,1,1,1). For each district we record how often
it stays inside the baseline top-50, plus rank-correlation of every draw with the baseline.
Outputs: data/processed/district_index.parquet/.csv and data/processed/index_summary.json
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
COMPONENTS = ["soil", "water", "equity", "crop"]
MIN_SAMPLES = 500   # districts with fewer soil samples are flagged low-confidence and excluded from rankings
TOP_N = 50
N_DRAWS = 5000
SEED = 42


def pct_rank(s: pd.Series) -> pd.Series:
    return s.rank(pct=True, method="average")


def build_components(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["eq_st_sc_area_pct"] = df.eq_st_area_pct + df.eq_sc_area_pct
    df["c_soil"] = pct_rank(df.soil_stress)
    df["c_water"] = pct_rank(df.water_stress)
    df["c_equity"] = (pct_rank(df.eq_st_sc_area_pct) + pct_rank(df.eq_marginal_hold_pct)) / 2
    df["c_crop"] = pct_rank(df.crop_hhi)
    return df


def dvi(df: pd.DataFrame, w) -> pd.Series:
    w = np.asarray(w, float)
    w = w / w.sum()
    return (df[[f"c_{c}" for c in COMPONENTS]].to_numpy() * w).sum(axis=1)


def main():
    df = pd.read_parquet(PROC / "district_features.parquet")
    df["low_sample"] = df.soil_n_samples < MIN_SAMPLES
    elig = df[df.has_census & df.soil_stress.notna() & ~df.low_sample].copy()
    # ranks are computed among eligible districts so percentiles are comparable
    elig = build_components(elig)
    elig["dvi"] = dvi(elig, [1, 1, 1, 1])
    elig["dvi_rank"] = elig.dvi.rank(ascending=False, method="min").astype(int)

    # sensitivity
    rng = np.random.default_rng(SEED)
    W = rng.dirichlet(np.ones(4), N_DRAWS)
    C = elig[[f"c_{c}" for c in COMPONENTS]].to_numpy()
    scores = C @ W.T                                   # districts x draws
    ranks = (-scores).argsort(axis=0).argsort(axis=0) + 1
    base_top = (elig.dvi_rank <= TOP_N).to_numpy()
    in_top = ranks <= TOP_N
    elig["top50_stability"] = in_top.mean(axis=1)       # share of draws in top-50
    overlap = (in_top[base_top, :].sum(axis=0)) / TOP_N  # per draw: share of baseline top-50 retained
    rho = np.array([spearmanr(elig.dvi, scores[:, j])[0] for j in range(0, N_DRAWS, 10)])
    elig["rank_p5"] = np.percentile(ranks, 5, axis=1).astype(int)
    elig["rank_p95"] = np.percentile(ranks, 95, axis=1).astype(int)

    # corner case: how much of the baseline top-N survives if ALL weight goes to a single component
    base_idx = set(elig.nlargest(TOP_N, "dvi").index)
    single = {c: len(base_idx & set(elig.nlargest(TOP_N, f"c_{c}").index)) / TOP_N for c in COMPONENTS}

    # mismatch flags (>= 75th percentile on the components)
    for c in COMPONENTS:
        elig[f"hi_{c}"] = elig[f"c_{c}"] >= 0.75
    elig["double_burden"] = elig.hi_soil & elig.hi_water
    elig["triple_burden"] = elig.hi_soil & elig.hi_water & elig.hi_equity

    comp_corr = elig[[f"c_{c}" for c in COMPONENTS]].corr(method="spearman").round(2)

    out = df.merge(elig[["state_name", "district_name"] + [c for c in elig.columns if c not in df.columns]],
                   on=["state_name", "district_name"], how="left")
    out.to_parquet(PROC / "district_index.parquet", index=False)
    out.to_csv(PROC / "district_index.csv", index=False)

    summary = {
        "n_districts_total": int(len(df)),
        "n_with_census": int(df.has_census.sum()),
        "n_low_sample_excluded": int((df.has_census & df.soil_stress.notna() & df.low_sample).sum()),
        "n_ranked": int(len(elig)),
        "weights_baseline": "equal (0.25 each)",
        "sensitivity": {
            "draws": N_DRAWS, "top_n": TOP_N,
            "median_top50_overlap_with_baseline": float(np.median(overlap)),
            "p5_top50_overlap": float(np.percentile(overlap, 5)),
            "median_spearman_rho_vs_baseline": float(np.median(rho)),
            "min_spearman_rho_vs_baseline": float(rho.min()),
            "districts_in_top50_in_90pct_of_draws": int((elig.top50_stability >= 0.9).sum()),
            "districts_in_top50_in_50pct_of_draws": int((elig.top50_stability >= 0.5).sum()),
            "baseline_top50_overlap_if_single_component": single,
        },
        "component_spearman_corr": comp_corr.to_dict(),
        "n_double_burden": int(elig.double_burden.sum()),
        "n_triple_burden": int(elig.triple_burden.sum()),
    }
    (PROC / "index_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print("\nTop 15 districts (baseline DVI):")
    cols = ["state_name", "district_name", "dvi", "c_soil", "c_water", "c_equity", "c_crop", "top50_stability", "top_crop"]
    print(elig.nlargest(15, "dvi")[cols].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
