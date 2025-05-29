# TAZ Data Integration & Scaling Pipeline

This pipeline transforms raw Census and LODES data into a set of Traffic Analysis Zone (TAZ)–level socioeconomic targets, ensuring that each TAZ’s totals roll up exactly to known county‐level benchmarks. It consists of four major phases:

## 1. Data Fetch & Preparation

1. **Block‐level population** (PL):

   * Retrieve total population (`P1_001N`) for every Census block via the `dec/pl` API.
   * Construct 15‑digit block GEOIDs, derive block‐group (12‑digit) and tract (11‑digit) keys.

2. **ACS block‐group variables**:

   * Pull a suite of detailed household and demographic variables at the block‐group level (e.g. age, tenure, race, household income quartiles).

3. **ACS tract variables**:

   * Fetch tract‑level summaries (e.g. households by number of workers, presence of children).

4. **Decennial DHC tract data**:

   * Download decennial group‑quarters counts (institutional vs. non‑institutional, by sex and age group).
   * Append a `county_fips` and `County_Name` column for aggregation.

At the end of this phase we have a unified block‐to‐tract–level data workspace.

## 2. TAZ‐Level Summaries

5. **Block shares**: compute each block’s share of its block‐group total for key variables.

6. **Working data**: merge block shares with tract‐level ACS & DHC to create person‑level working records.

7. **Household income**: derive household‐income category counts per block, then allocate to block‐groups and TAZs.

8. **Summarize to TAZ**:

   * **Step 8**: using block‐to‐TAZ crosswalk, aggregate household‐income counts to each TAZ.
   * **Step 9**: using tract‐to‐TAZ crosswalk, aggregate ACS tract variables to each TAZ.

9. **Raw census counts**: carry through raw totals (population, households, GQ) to TAZ in preparation for county alignment.

## 3. County Targets & Scaling

10. **Integrate employment**:

    * Load LODES workplace (WAC) data and self‐employment CSV.
    * Sum `emp_lodes` and `emp_self` to get `EMPRES` (employed residents) and `TOTEMP` (total workers) per TAZ.

11. **Build county targets** (`build_county_targets()`):

    * Aggregate TAZ‐level `TOTPOP`, `TOTHH`, `HHPOP`, `gqpop`, `EMPRES`, and `TOTEMP` up to each county.
    * Optionally override totals using ACS 1‑Year PUMS estimates (with retry logic and institutional GQ adjustment).
    * Integrate LODES home‑county workplace flows to reweight `EMPRES_target` by a user‐specified blend weight.

12. **Compute scale factors** (`step11_compute_scale_factors()`):

    * For each TAZ, calculate `scale_factor = county_target / county_base` (on `EMPRES`).
    * Handle zero‐base counties gracefully.

13. **Apply scaling** (`step12_apply_scaling()`):

    * Multiply raw TAZ employment fields (`emp_lodes`, `emp_self`) by `scale_factor` to exactly match county targets when summed.

## 4. Push County Targets Back to TAZ

14. **Distribute county targets** (`apply_county_targets_to_taz()`):

    * Sequentially adjust TAZ‐level partial variables so that, when re‐aggregated:

      * Employed residents  = county `EMPRES_target`
      * Total households   = county `TOTHH_target`
      * Population by age  = county `TOTPOP_target`
      * Population by race  = county `TOTPOP_target`
      * Housing units       = county `TOTHH_target`
      * Tenure breakdown    = county `TOTHH_target`
      * Households with kids= county `TOTHH_target`
      * Income quartiles    = county `TOTHH_target`
      * Household size      = county `TOTHH_target`
      * Household workers   = county `TOTHH_target`
    * Employ `update_tazdata_to_county_target` for proportional allocation of multi‐category fields, followed by `make_hhsizes_consistent_with_population` to reconcile rounding or weighting discrepancies.

## 5. Final Steps

15. **Join land‐use attributes** (`step13_join_pba2015()`): attach PBA2015 geography and land‐use data to each TAZ.

16. **Write outputs** (`step14_write_outputs()`): export final TAZ dataset and diagnostics.

---

This modular design makes it easy to swap in new geographies (e.g. smaller MAZ units) or alternate data vintages: just update the crosswalks and target‐building functions, and the rest of the workflow remains unchanged.
