"""Phase 1: convert raw CSVs to Parquet using DuckDB (streaming, low memory).

Usage: python src/ingest.py
Writes data/interim/<name>.parquet and prints a row-count reconciliation.
"""
from pathlib import Path
import subprocess
import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "interim"
OUT.mkdir(parents=True, exist_ok=True)

# Explicit types where inference would be risky (codes with leading zeros etc.)
SOURCES = {
    "soil": ("soil-nutrient-analysis.csv", {
        "state_code": "VARCHAR", "district_code": "VARCHAR", "block_code": "VARCHAR",
        "village_code": "VARCHAR", "value": "BIGINT"}),
    "agcensus_tehsil": ("tehsil-level-agcensus-crop.csv", {
        "state_code": "VARCHAR", "district_code": "VARCHAR", "tehsil_code": "VARCHAR",
        "crop_code": "INTEGER", "hold_no": "BIGINT"}),
    "agcensus_state": ("state-level-agcensus-crop.csv", {
        "state_code": "VARCHAR", "crop_code": "INTEGER", "hold_no": "BIGINT"}),
    "msp": ("minimum-support-prices.csv", {}),
    "horticulture": ("area-and-production-statistics.csv", {"state_code": "VARCHAR"}),
}


def csv_rows(path: Path) -> int:
    """Independent row count (wc -l minus header). Fine here: no embedded newlines in these files."""
    n = int(subprocess.check_output(["wc", "-l", str(path)]).split()[0])
    return n - 1


def main():
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='2GB'")
    for name, (fname, types) in SOURCES.items():
        src, dst = RAW / fname, OUT / f"{name}.parquet"
        tdef = ", ".join(f"'{c}': '{t}'" for c, t in types.items())
        types_arg = f", types={{{tdef}}}" if types else ""
        con.execute(f"""
            COPY (SELECT * FROM read_csv('{src}', header=true, quote='"', escape='"', strict_mode=true{types_arg}))
            TO '{dst}' (FORMAT PARQUET, COMPRESSION ZSTD)""")
        n_pq = con.execute(f"SELECT count(*) FROM '{dst}'").fetchone()[0]
        n_csv = csv_rows(src)
        flag = "OK" if n_pq == n_csv else "MISMATCH"
        print(f"{name:16s} csv={n_csv:>10,}  parquet={n_pq:>10,}  "
              f"{src.stat().st_size/1e6:8.1f}MB -> {dst.stat().st_size/1e6:7.1f}MB  {flag}")


if __name__ == "__main__":
    main()
