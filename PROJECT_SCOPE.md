# Project Scope: Soil, Water and Crop Mismatch Atlas

## 1. Problem statement

India's agricultural policy is usually discussed by crop or by state. Farmers experience it at the level of a district or village: what their soil lacks, whether they can irrigate, and what the market and government support for their crop looks like.

**Core question:** Where do a district's soil health, irrigation access and cropping pattern work against each other, and which farmers are most exposed?

Example of a "mismatch": a district dominated by nitrogen-hungry paddy, on soil where most samples are nitrogen-low, with little irrigation and a high share of marginal or Scheduled Tribe farmers.

## 2. Audience

| Audience | What they get |
|---|---|
| Policy analysts and NGOs | A ranked list of districts for targeted soil-health and irrigation support |
| Agri-input companies | Where micronutrient and nitrogen demand gaps are largest |
| Researchers and journalists | A documented, reproducible district-level dataset |
| Recruiters / hiring managers | Evidence of data engineering, analysis and communication |

## 3. Objectives

1. Build a clean, documented district-level dataset that joins soil, irrigation, farm structure and crop mix.
2. Define a transparent District Vulnerability Index and test how sensitive rankings are to its weights.
3. Group districts into interpretable profiles using clustering.
4. Publish an interactive app and a short written analysis.
5. Document data limitations honestly, including what the data cannot support.

## 4. Data sources

| Dataset | Grain | Years | Rows (approx.) | Role |
|---|---|---|---|---|
| Soil Nutrient Analysis (Soil Health Card) | Village x nutrient x level | 2023-24, 2024-25 | 10.9M | Soil stress features |
| Tehsil-level AgCensus Crop | Tehsil x social group x farm size x crop | 2010-11, 2015-16 | 6.5M | Irrigation, equity, crop mix at district level |
| State-level AgCensus Crop | State x social group x farm size x crop | 2010-11, 2015-16 | 165K | Validation of the tehsil file |
| Minimum Support Prices | Crop x year | 1998-99 to 2026-27 | 845 | Policy-support flag for dominant crops |
| Horticulture Area & Production | State x crop x year x estimate stage | 2011-12 to 2025-26 | 135K | Optional context: horticulture share by state |

Sources are the Ministry of Agriculture & Farmers Welfare portals named in each dataset's codebook.

## 5. Methodology

### 5.1 Data engineering
- Convert the two ~1 GB CSVs to Parquet. Query with DuckDB or Polars rather than loading into memory.
- Aggregate soil data from village to district and tehsil data to district.
- Build a **district crosswalk** between soil and AgCensus. District names and codes may differ and districts were split between census years, so this step needs fuzzy matching plus manual review. Report the match rate.
- Exclude "Total ..." aggregate rows when ranking individual crops, to avoid double counting.

### 5.2 Feature definitions

**Soil stress** (share of samples in the unhealthy category, per district):

| Nutrient | Counted as unhealthy |
|---|---|
| Nitrogen, Phosphorus, Potassium, Organic Carbon | Low |
| Boron, Copper, Iron, Manganese, Sulphur, Zinc | Deficient |
| Soil pH | Acidic (alkaline reported separately) |
| Electrical Conductivity | Saline |

**Water stress:** `1 - irrigated area / total area` (AgCensus, 2015-16).

**Equity exposure:** share of area and holdings with Scheduled Tribe farmers and with marginal holdings (< 1 ha).

**Crop exposure:** dominant crops by area, a diversity measure, and whether the dominant crops carry an MSP.

### 5.3 Vulnerability index
- Normalise each component to 0-1, then combine as a weighted average.
- Start with equal weights. Run a sensitivity analysis over alternative weightings and report how stable the top-N districts are.
- Keep the index simple and explainable. Avoid a black-box score.

### 5.4 Clustering
- Cluster districts on the standardised features (for example k-means or hierarchical clustering).
- Choose k using silhouette score and interpretability, and give each cluster a plain-language name.

### 5.5 Optional modelling
- Test which district features are associated with micronutrient deficiency.
- Claims stay associational. The data cannot support causal conclusions.

## 6. Deliverables

1. Reproducible pipeline (scripts or notebooks) from raw CSV to district dataset.
2. District dataset in Parquet and CSV, with a data dictionary.
3. Streamlit app: district map, filters, per-district profile, index weight sliders.
4. README and a limitations section.
5. Written analysis of about 1,000 words for a non-technical reader.

## 7. Out of scope

- Market prices, farmer income or profitability (no such data here).
- Causal claims about soil, yield or policy effects.
- Farm-level or village-level mapping across datasets (soil is village-level but AgCensus is tehsil-level, so joins stop at district).
- Forecasting future soil health.

## 8. Known data risks

| Risk | Mitigation |
|---|---|
| 2010-11 state file lacks 7 states (UP, MP, Rajasthan, Karnataka, Tamil Nadu, Tripura, Puducherry) | Use 2015-16 as the primary year. Compare across years only on common states. |
| Tehsil and state totals disagree in 2010-11 (differences up to about 50% in some states) | Use 2015-16 for district features. Report the reconciliation. |
| Soil coverage grew from 29 to 32 states and sample counts doubled between years | Use shares rather than counts. Treat year-on-year change with caution. |
| National and state soil shares are weighted by sample count, which is skewed by a few states | Report district-level values and sample sizes. Flag districts with few samples. |
| Soil (2023-25) and AgCensus (2010-16) are years apart | State clearly that the project matches structure, not the same moment. |
| Some AgCensus crop codes have no name; "Paddy" and "Kharif Paddy" may overlap | Exclude unnamed codes. Test the paddy overlap before using it. |
| District boundaries changed between census years | Crosswalk step, with manual review of unmatched districts. |

## 9. Milestones and status

| Phase | Output | Status |
|---|---|---|
| 1. Ingest | Parquet files, schema checks, row-count reconciliation | Done: all 5 files reconcile exactly |
| 2. Crosswalk | District mapping with a reported match rate | Done: 93.6% (691 of 738) matched to the 2015-16 census |
| 3. Features | District feature table and data dictionary | Done |
| 4. Index and clusters | Index with sensitivity analysis, named cluster profiles | Done: 668 ranked, 5 profiles |
| 5. App | Streamlit map and district profiles | Done, runs locally; not deployed |
| 6. Write-up | README finalised, analysis written, app deployed | README done; long-form write-up and deployment remaining |

## 10. Success criteria

- The crosswalk match rate is reported, and unmatched districts are listed and explained.
- Index rankings are tested for sensitivity, and the result is stated.
- Every number in the README is reproducible from the repo.
- The app is live and loads without needing the raw data.
- Limitations are as prominent as findings.
