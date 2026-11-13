# Data dictionary: `data/processed/district_index.(parquet|csv)`

One row per soil district (738). Census-derived columns are empty for the districts without a census link; index columns are empty for districts that are not ranked.

| column | type | description |
|---|---|---|
| `state_name` | str | State / UT (soil-data naming) |
| `district_name` | str | District, current name (soil data) |
| `soil_boron` | float64 | Unhealthy % of samples: boron |
| `soil_copper` | float64 | Unhealthy % of samples: copper |
| `soil_electrical_conductivity` | float64 | Unhealthy % of samples: electrical conductivity |
| `soil_iron` | float64 | Unhealthy % of samples: iron |
| `soil_manganese` | float64 | Unhealthy % of samples: manganese |
| `soil_nitrogen` | float64 | Unhealthy % of samples: nitrogen |
| `soil_organic_carbon` | float64 | Unhealthy % of samples: organic carbon |
| `soil_phosphorus` | float64 | Unhealthy % of samples: phosphorus |
| `soil_potassium` | float64 | Unhealthy % of samples: potassium |
| `soil_soil_ph` | float64 | Unhealthy % of samples: soil ph |
| `soil_sulphur` | float64 | Unhealthy % of samples: sulphur |
| `soil_zinc` | float64 | Unhealthy % of samples: zinc |
| `soil_year` | str | Soil year used (latest available for the district) |
| `soil_n_samples` | float64 | Samples tested (maximum over nutrients); districts < 500 are flagged low_sample |
| `soil_macro_stress` | float64 | Mean % unhealthy: N, P, K, organic carbon (Low) |
| `soil_micro_stress` | float64 | Mean % unhealthy: B, Cu, Fe, Mn, S, Zn (Deficient) |
| `soil_chem_stress` | float64 | Mean % unhealthy: acidic pH, saline EC |
| `soil_n_nutrients` | int64 | How many of the 12 parameters have data |
| `soil_stress` | float64 | Mean % unhealthy samples over the 12 parameters (needs >= 9) |
| `xwalk_tier` | str | How the district was matched to the census (1_exact, 2_alias, 3_code, 4_fuzzy) |
| `ag_district` | str | Matched census-era district name |
| `boundary_note` | str | 'rename' or 'approx' for curated alias matches |
| `gca` | float64 | Gross cropped area, hectares, 2015-16 (food + non-food crop totals) |
| `gca_irr` | float64 | Irrigated cropped area, hectares (2015-16) |
| `gca_st` | float64 | Cropped area held by Scheduled Tribe farmers, hectares |
| `gca_sc` | float64 | Cropped area held by Scheduled Caste farmers, hectares |
| `gca_marg` | float64 | Cropped area on marginal holdings, hectares |
| `hold_all` | float64 | Holdings growing food crops (all groups) |
| `hold_marg` | float64 | Marginal holdings growing food crops |
| `hold_st` | float64 | Scheduled Tribe holdings growing food crops |
| `crop_area_listed` | float64 | Hectares across individual crops (denominator for crop shares) |
| `top_crop` | str | Largest individual crop by area (seasonal paddy codes excluded) |
| `top_crop_share` | float64 | Top crop % of listed crop area |
| `crop_hhi` | float64 | Herfindahl index of crop area shares (0-1) |
| `crop_shannon` | float64 | Shannon diversity of crop area shares |
| `crop_n` | float64 | Number of individual crops with area |
| `msp_area_share` | float64 | % of listed crop area under MSP-listed crops (LOWER BOUND) |
| `sugarcane_share` | float64 | Sugarcane % of listed crop area (FRP, not MSP) |
| `cereal_share` | float64 | Cereals % of listed crop area |
| `rice_wheat_share` | float64 | Paddy + wheat % of listed crop area |
| `water_irrigated_pct` | float64 | Irrigated % of gross cropped area |
| `water_stress` | float64 | 100 - irrigated % |
| `eq_st_area_pct` | float64 | Scheduled Tribe % of cropped area |
| `eq_sc_area_pct` | float64 | Scheduled Caste % of cropped area |
| `eq_marginal_area_pct` | float64 | Marginal holdings (< 1 ha) % of cropped area |
| `eq_marginal_hold_pct` | float64 | Marginal % of holdings growing food crops |
| `eq_st_hold_pct` | float64 | Scheduled Tribe % of holdings growing food crops |
| `has_census` | bool | District linked to a 2015-16 census district |
| `low_sample` | bool | Fewer than 500 soil samples |
| `eq_st_sc_area_pct` | float64 | Scheduled Tribe + Scheduled Caste % of cropped area (used in c_equity) |
| `c_soil` | float64 | Component: percentile rank of soil_stress (0-1) |
| `c_water` | float64 | Component: percentile rank of water_stress |
| `c_equity` | float64 | Component: mean percentile rank of (ST+SC area %) and marginal holding % |
| `c_crop` | float64 | Component: percentile rank of crop_hhi |
| `dvi` | float64 | District Vulnerability Index, equal weights (0-1) |
| `dvi_rank` | float64 | Rank by dvi (1 = most vulnerable) |
| `top50_stability` | float64 | Share of 5,000 random weightings in which the district stays in the baseline top 50 |
| `rank_p5` | float64 | 5th percentile rank over random weightings |
| `rank_p95` | float64 | 95th percentile rank over random weightings |
| `hi_soil` | object | Top-quartile flag for soil |
| `hi_water` | object | Top-quartile flag for water |
| `hi_equity` | object | Top-quartile flag for equity |
| `hi_crop` | object | Top-quartile flag for crop |
| `double_burden` | object | c_soil and c_water both >= 0.75 |
| `triple_burden` | object | ... and c_equity >= 0.75 |
