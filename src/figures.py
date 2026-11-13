"""Static figures for the README / write-up -> docs/figures/*.png"""
from pathlib import Path
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC, FIG = ROOT / "data" / "processed", ROOT / "docs" / "figures"
FIG.mkdir(parents=True, exist_ok=True)


def main():
    g = gpd.read_file(PROC / "district_geo.geojson")
    # 1. index map
    fig, ax = plt.subplots(figsize=(7, 8))
    g.plot(column="dvi", cmap="YlOrRd", legend=True, ax=ax, linewidth=0.1, edgecolor="grey",
           missing_kwds={"color": "#dddddd"}, legend_kwds={"shrink": 0.6, "label": "Vulnerability index (equal weights)"})
    ax.set_title("District Vulnerability Index (higher = more exposed)"); ax.axis("off")
    fig.text(0.02, 0.02, "Grey = no census link / too few soil samples / no 2011 polygon", fontsize=7)
    fig.savefig(FIG / "dvi_map.png", dpi=130, bbox_inches="tight"); plt.close(fig)

    # 2. cluster map
    fig, ax = plt.subplots(figsize=(8, 8))
    g.plot(column="cluster_name", categorical=True, cmap="Set2", legend=True, ax=ax, linewidth=0.1, edgecolor="grey",
           missing_kwds={"color": "#dddddd"}, legend_kwds={"loc": "lower left", "fontsize": 7, "frameon": False})
    ax.set_title("District profiles (k-means, k = 5)"); ax.axis("off")
    fig.savefig(FIG / "cluster_map.png", dpi=130, bbox_inches="tight"); plt.close(fig)

    # 3. rank robustness for the top 25 (equal-weight baseline, 5th-95th percentile rank over 5,000 random weightings)
    d = pd.read_parquet(PROC / "district_index.parquet")
    t = d[d.dvi.notna()].nlargest(25, "dvi").iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, 7))
    y = range(len(t))
    ax.hlines(y, t.rank_p5, t.rank_p95, color="#888", lw=3, label="5th-95th percentile rank")
    ax.scatter(t.dvi_rank, y, color="#c0392b", zorder=3, label="baseline rank (equal weights)")
    ax.set_yticks(list(y)); ax.set_yticklabels(t.district_name + ", " + t.state_name.str[:3], fontsize=8)
    ax.set_xlabel("Rank (1 = most vulnerable)"); ax.set_title("How much do the top 25 move when weights change?")
    ax.legend(frameon=False, fontsize=8); ax.grid(axis="x", alpha=0.3)
    fig.savefig(FIG / "rank_robustness.png", dpi=130, bbox_inches="tight"); plt.close(fig)
    print("figures written:", sorted(p.name for p in FIG.glob("*.png")))


if __name__ == "__main__":
    main()
