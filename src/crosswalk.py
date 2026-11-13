"""Phase 2: district crosswalk between the Soil Health data (anchor, current boundaries)
and the AgCensus tehsil data (2015-16 and 2010-11 boundaries).

Matching is always WITHIN a state. Tiers, in order of confidence:
  1 exact   normalised name equal
  2 alias   curated rename / spelling table (src/district_aliases.csv)
  3 code    same district_code (only if that code is unique in the census file) AND names broadly similar
  4 fuzzy   rapidfuzz score >= FUZZY_MIN, best match, reported for review
Unmatched soil districts are almost entirely districts created after the census; they are kept
(soil-only features still work) but get no census-linked features.
AgCensus district codes are NOT used as a primary key: several are reused for different
districts in the same state and some districts appear under two codes.

Usage: python src/crosswalk.py [--review]
Outputs data/processed/district_crosswalk_{2015_16,2010_11}.csv and prints a match report.
"""
from pathlib import Path
import re
import sys
import duckdb
import pandas as pd
from rapidfuzz import fuzz, process

ROOT = Path(__file__).resolve().parents[1]
INTERIM, PROC = ROOT / "data" / "interim", ROOT / "data" / "processed"
PROC.mkdir(parents=True, exist_ok=True)
ALIASES = ROOT / "src" / "district_aliases.csv"
FUZZY_MIN = 86


def norm(s: str) -> str:
    s = s.lower().replace("&", "and")
    s = re.sub(r"\bdistrict\b|\bdist\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def load():
    con = duckdb.connect()
    soil = con.execute(f"""SELECT DISTINCT state_name, district_name, district_code
                           FROM '{INTERIM}/soil.parquet'""").df()
    ag = con.execute(f"""SELECT DISTINCT year, state_name, district_name, district_code
                         FROM '{INTERIM}/agcensus_tehsil.parquet'""").df()
    return soil, ag


def match_year(soil: pd.DataFrame, ag: pd.DataFrame, aliases: pd.DataFrame) -> pd.DataFrame:
    # collapse census duplicates: same (state, normalised name) under several codes = one district
    ag = ag.assign(k=ag.district_name.map(norm))
    code_counts = ag.groupby(["state_name", "district_code"]).k.nunique()
    unique_codes = set(code_counts[code_counts == 1].index)
    ag_names = ag.groupby(["state_name", "k"]).agg(
        ag_name=("district_name", "first"),
        codes=("district_code", lambda x: set(x))).reset_index()

    alias = {(r.state_name, norm(r.soil_name)): norm(r.ag_name) for r in aliases.itertuples()}
    alias_kind = {(r.state_name, norm(r.soil_name)): r.kind for r in aliases.itertuples()}
    rows = []
    for r in soil.itertuples():
        sk = norm(r.district_name)
        cands = ag_names[ag_names.state_name == r.state_name]
        res = dict(state_name=r.state_name, soil_district=r.district_name, soil_code=r.district_code,
                   ag_district=None, tier="unmatched", score=None)
        hit = cands[cands.k == sk]
        if len(hit):
            res.update(ag_district=hit.ag_name.iloc[0], tier="1_exact", score=100)
        elif (r.state_name, sk) in alias and len(cands[cands.k == alias[(r.state_name, sk)]]):
            h = cands[cands.k == alias[(r.state_name, sk)]]
            res.update(ag_district=h.ag_name.iloc[0], tier="2_alias", score=100,
                       boundary_note=alias_kind[(r.state_name, sk)])
        else:
            ch = cands[cands.codes.map(lambda c: r.district_code in c) &
                       cands.codes.map(lambda c: any((r.state_name, x) in unique_codes for x in c))]
            if len(ch) == 1:
                sc = fuzz.token_sort_ratio(sk, ch.k.iloc[0])
                if sc >= 50:
                    res.update(ag_district=ch.ag_name.iloc[0], tier="3_code", score=sc)
            if res["tier"] == "unmatched" and len(cands):
                best = process.extractOne(sk, cands.k.tolist(), scorer=fuzz.token_sort_ratio)
                if best and best[1] >= FUZZY_MIN:
                    res.update(ag_district=cands[cands.k == best[0]].ag_name.iloc[0],
                               tier="4_fuzzy", score=best[1])
        rows.append(res)
    df = pd.DataFrame(rows)
    if "boundary_note" not in df:
        df["boundary_note"] = None
    return df


def main(review=False):
    soil, ag = load()
    aliases = pd.read_csv(ALIASES) if ALIASES.exists() else pd.DataFrame(columns=["state_name", "soil_name", "ag_name"])
    out = {}
    for yr in ["2015-16", "2010-11"]:
        xw = match_year(soil, ag[ag.year == yr], aliases)
        out[yr] = xw
        xw.to_csv(PROC / f"district_crosswalk_{yr.replace('-', '_')}.csv", index=False)
        n = len(xw)
        print(f"\n=== Soil -> AgCensus {yr}: {n} soil districts")
        print((xw.tier.value_counts().sort_index() / n * 100).round(1).astype(str) + "%  " +
              xw.tier.value_counts().sort_index().astype(str))
        print(f"matched: {(xw.tier != 'unmatched').mean()*100:.1f}%")
        # one-to-one check: several soil districts mapping to the same census district
        dup = xw[xw.ag_district.notna()].groupby(["state_name", "ag_district"]).size()
        print(f"census districts claimed by >1 soil district: {(dup > 1).sum()}")
    if review:
        xw = out["2015-16"]
        print("\n--- REVIEW: tier 3/4 matches (2015-16)")
        print(xw[xw.tier.isin(["3_code", "4_fuzzy"])].sort_values(["state_name", "score"]).to_string(index=False))
        print("\n--- REVIEW: unmatched (2015-16)")
        print(xw[xw.tier == "unmatched"].sort_values("state_name")[["state_name", "soil_district", "soil_code"]].to_string(index=False))
        print("\n--- REVIEW: many-to-one (2015-16)")
        d = xw[xw.ag_district.notna()]
        print(d[d.duplicated(["state_name", "ag_district"], keep=False)].sort_values(["state_name", "ag_district"]).to_string(index=False))


if __name__ == "__main__":
    main("--review" in sys.argv)
