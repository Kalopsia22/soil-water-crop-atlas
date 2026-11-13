"""Phase 4b: group districts into profiles with k-means.

Features are percentile-ranked first (robust to the heavy skew in shares), then k-means.
k is chosen from 3..8 using silhouette AND a stability test (adjusted Rand index between fits on
random 80% subsamples). Outputs data/processed/district_clusters.csv, cluster_profiles.csv, cluster_selection.csv.
Cluster NAMES are assigned by hand after reading cluster_profiles.csv (see CLUSTER_NAMES in app/main.py).
"""
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, adjusted_rand_score

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
FEATS = ["soil_macro_stress", "soil_micro_stress", "soil_chem_stress", "water_stress",
         "eq_st_sc_area_pct", "eq_marginal_hold_pct", "crop_hhi", "msp_area_share", "cereal_share"]
SEED = 42


def fit_stability(X, k, n=20):
    rng = np.random.default_rng(SEED)
    ref = KMeans(k, n_init=20, random_state=SEED).fit(X)
    aris = []
    for _ in range(n):
        idx = rng.choice(len(X), int(0.8 * len(X)), replace=False)
        sub = KMeans(k, n_init=10, random_state=int(rng.integers(1e6))).fit(X[idx])
        aris.append(adjusted_rand_score(ref.labels_[idx], sub.labels_))
    return float(np.mean(aris))


def name_clusters(d: pd.DataFrame, feats) -> dict:
    """Deterministic, rule-based names (so labels do not depend on k-means label order).
    Written for k=5 after reading the profiles; each rule picks the cluster whose MEDIAN is most extreme."""
    med = d.groupby("cluster")[feats].median()
    left, names = set(med.index), {}

    def pick(col, name, largest=True):
        c = (med.loc[sorted(left), col].idxmax() if largest else med.loc[sorted(left), col].idxmin())
        names[c] = name; left.discard(c)
    pick("water_stress", "Irrigated rice-wheat plains", largest=False)
    pick("eq_st_sc_area_pct", "Tribal-majority hill & northeast districts")
    pick("crop_hhi", "Rainfed paddy belt (east & centre)")
    pick("soil_micro_stress", "Semi-arid cotton-soybean-millet plateau")
    for c in left:
        names[c] = "Smallholder plantation & mixed-crop districts"
    return names


def main():
    df = pd.read_parquet(PROC / "district_index.parquet")
    d = df[df.dvi.notna()].copy()                 # ranked districts only (soil + census, adequate samples)
    d["eq_st_sc_area_pct"] = d.eq_st_area_pct + d.eq_sc_area_pct
    X = d[FEATS].rank(pct=True).to_numpy()
    rows = []
    for k in range(3, 9):
        km = KMeans(k, n_init=20, random_state=SEED).fit(X)
        rows.append(dict(k=k, silhouette=silhouette_score(X, km.labels_), stability_ari=fit_stability(X, k),
                         smallest_cluster=int(np.bincount(km.labels_).min())))
    sel = pd.DataFrame(rows)
    sel.to_csv(PROC / "cluster_selection.csv", index=False)
    print(sel.round(3).to_string(index=False))

    K = int(__import__("os").environ.get("K", 5))
    km = KMeans(K, n_init=50, random_state=SEED).fit(X)
    d["cluster"] = km.labels_
    names = name_clusters(d, FEATS)
    d["cluster_name"] = d.cluster.map(names)
    d[["state_name", "district_name", "cluster", "cluster_name"]].to_csv(PROC / "district_clusters.csv", index=False)
    prof = d.groupby(["cluster", "cluster_name"]).agg(n=("cluster", "size"),
        **{f: (f, "median") for f in FEATS},
        dvi=("dvi", "median"), gca_median=("gca", "median"))
    prof.round(2).to_csv(PROC / "cluster_profiles.csv")
    print(f"\nProfiles for k={K} (medians):")
    print(prof.round(2).to_string())
    print("\nStates per cluster (top 5):")
    for c, g in d.groupby("cluster"):
        print(c, g.state_name.value_counts().head(5).to_dict(), "| top crops:", g.top_crop.value_counts().head(3).to_dict())


if __name__ == "__main__":
    main()
