
import os
import logging
from pathlib import Path
import pandas as pd
import yaml

# Load configuration\ nCONFIG_PATH = Path(__file__).parent / 'config.yaml'
CONFIG_PATH = Path(__file__).parent / 'config.yaml'
with CONFIG_PATH.open() as f:
    cfg = yaml.safe_load(f)
PATHS = cfg['paths']


import os
import pandas as pd


def write_out_all(
    df_taz: pd.DataFrame,
    PBA_base: pd.DataFrame,
    baseline_year: int,
    target_year: int

):
    """
    1) Pull selected PBA blueprint cols and merge onto df_taz
    2) Write baseline-year district summary from PBA_base
    3) Write target-year outputs (district, land-use, popsims, long) from the joined frame
    """

    taz_sd_county_csv= PATHS["taz_sd_county_csv"]
    # a) Select & join blueprint fields (mirroring R’s select + left_join)
    # Define the blueprint columns, excluding the join key 'ZONE'
    joiner_cols = [
        "SD", "TOTACRE", "RESACRE", "CIACRE",
        "SFDU", "MFDU", "PRKCST", "OPRKCST", "AREATYPE",
        "HSENROLL", "COLLFTE", "COLLPTE",
        "TOPOLOGY", "TERMINAL", "ZERO", "DISTRICT"
    ]
    if "gqpop" not in PBA_base.columns:
        PBA_base = PBA_base.assign(
            gqpop=lambda d: d["TOTPOP"].astype(int) - d["HHPOP"].astype(int)
        )
    # Include gqpop in joiner
    joiner_cols.append("gqpop")

    # Subset once, including ZONE exactly once
    PBA_sub = PBA_base[["ZONE"] + joiner_cols].copy()
    PBA_sub = PBA_sub.drop_duplicates(subset=["ZONE"])
    PBA_sub["taz"] = PBA_sub["ZONE"].astype(str)

    # Prepare df_taz and detect its key
    df_taz = df_taz.copy()
    if 'TAZ1454' in df_taz.columns:
        df_taz['taz'] = df_taz['TAZ1454'].astype(str)
    elif 'ZONE' in df_taz.columns:
        df_taz['taz'] = df_taz['ZONE'].astype(str)
    else:
        raise KeyError("Could not find 'TAZ1454' or 'ZONE' in df_taz")

    # Merge blueprint onto df_taz
    taz_joined = df_taz.merge(
        PBA_sub.drop(columns=["ZONE"]),
        on="taz",
        how="left"
    )

    # Drop any merge artifacts
    for col in ("taz_x", "taz_y"):
        if col in taz_joined.columns:
            taz_joined = taz_joined.drop(columns=[col])

    # b) Baseline-year district summary from raw PBA_base
    summary_cols = [
        "TOTHH", "HHPOP", "TOTPOP", "EMPRES", "SFDU", "MFDU",
        "HHINCQ1", "HHINCQ2", "HHINCQ3", "HHINCQ4", "TOTEMP",
        "AGE0004", "AGE0519", "AGE2044", "AGE4564", "AGE65P",
        "RETEMPN", "FPSEMPN", "HEREMPN", "AGREMPN", "MWTEMPN", "OTHEMPN",
        "HSENROLL", "COLLFTE", "COLLPTE"
    ]
    existing_base = [c for c in summary_cols if c in PBA_base.columns]
    # convert existing_base columns to numeric to avoid string concatenation
    PBA_base_num = PBA_base.copy()
    PBA_base_num[existing_base] = PBA_base_num[existing_base].apply(
        pd.to_numeric, errors='coerce'
    )
    df_base_summary = (
        PBA_base_num.groupby("DISTRICT", as_index=False)[existing_base]
                  .sum()
                  .assign(
                      gqpop=lambda d: (
                          d["TOTPOP"].astype(float) - d["HHPOP"].astype('float')
                      )
                  )
    )
    os.makedirs(str(baseline_year), exist_ok=True)
    base_path = os.path.join(
        str(baseline_year), f"TAZ1454 {baseline_year} District Summary.csv"
    )
    df_base_summary.to_csv(base_path, index=False, quoting=1)
    print(f"Wrote {base_path}")

    # c) Target-year district summary from joined frame
    existing_target = [c for c in summary_cols if c in taz_joined.columns]
    df_target_summary = (
        taz_joined.groupby("DISTRICT", as_index=False)[existing_target]
                  .sum()
                  .assign(
                      gqpop=lambda d: (
                          d["TOTPOP"].astype(int) - d["HHPOP"].astype(int)
                      )
                  )
    )
    os.makedirs(str(target_year), exist_ok=True)
    target_path = os.path.join(
        str(target_year), f"TAZ1454 {target_year} District Summary.csv"
    )
    df_target_summary.to_csv(target_path, index=False, quoting=1)
    print(f"Wrote {target_path}")

    # d) Land-use CSV (target year)
    if "ZONE" not in taz_joined.columns:
    # copy your taz key back into a ZONE column
        taz_joined["ZONE"] = taz_joined["taz"].astype(str)
    taz_joined["ZONE"] = taz_joined["taz"].astype(str)
    landuse_cols = ["ZONE"] + joiner_cols + ["TOTHH", "HHPOP", "TOTPOP", "EMPRES", "SHPOP62P"]
    landuse_existing = [c for c in landuse_cols if c in taz_joined.columns]
    df_landuse = taz_joined[landuse_existing].copy()
    df_landuse["hhlds"] = df_landuse["TOTHH"]
    landuse_path = os.path.join(
        str(target_year), f"TAZ1454 {target_year} Land Use.csv"
    )
    df_landuse.to_csv(landuse_path, index=False, quoting=1)
    print(f"Wrote {landuse_path}")

    # e) Popsim variables (TAZ, region, county)
    df_renamed = taz_joined.rename(columns={
    "ZONE": "TAZ",
    "GQPOP": "gq_tot_pop"
    })

    pops_vars = [
        "TAZ", "TOTHH", "TOTPOP", "hh_own", "hh_rent", "hh_size_1",
        "hh_size_2", "hh_size_3", "hh_size_4_plus", "hh_wrks_0",
        "hh_wrks_1", "hh_wrks_2", "hh_wrks_3_plus", "hh_kids_no",
        "hh_kids_yes", "HHINCQ1", "HHINCQ2", "HHINCQ3", "HHINCQ4",
        "AGE0004", "AGE0519", "AGE2044", "AGE4564", "AGE65P",
        "gq_tot_pop",  # note we use the renamed name here
        "gq_type_univ", "gq_type_mil", "gq_type_othnon"
    ]

    # 3) Filter to only the columns that actually exist
    available = [c for c in pops_vars if c in df_renamed.columns]

    # 4) Slice & write out
    df_popsim = df_renamed.loc[:, available].copy()
    pops_path = os.path.join(
        str(target_year), f"TAZ1454 {target_year} Popsim Vars.csv"
    )
    df_popsim.to_csv(pops_path, index=False, quoting=1)
    print(f"Wrote {pops_path}")
    # region
    df_region = (
        df_popsim.assign(REGION=1)
                 .groupby("REGION", as_index=False)["gq_tot_pop"]
                 .sum()
                 .rename(columns={"gq_tot_pop": "gq_num_hh_region"})
    )
    region_path = os.path.join(
        str(target_year), f"TAZ1454 {target_year} Popsim Vars Region.csv"
    )
    df_region.to_csv(region_path, index=False, quoting=1)
    print(f"Wrote {region_path}")

    # f) County popsims
    occ_cols = [
        "pers_occ_management", "pers_occ_professional", "pers_occ_services",
        "pers_occ_retail", "pers_occ_manual", "pers_occ_military"
    ]

    if "County_Name" in taz_joined.columns:
        taz_joined["COUNTY"] = taz_joined["County_Name"]
    df_county = (
        taz_joined.groupby("COUNTY", as_index=False)
                  [[c for c in occ_cols if c in taz_joined.columns]]
                  .sum()
    )
    county_path = os.path.join(
        str(target_year), f"TAZ1454 {target_year} Popsim Vars County.csv"
    )
    df_county.to_csv(county_path, index=False, quoting=1)
    print(f"Wrote {county_path}")

    # g) Long-format outputs (baseline & target)
    taz_sd = pd.read_csv(taz_sd_county_csv)
    id_vars = ["ZONE", "SD", "COUNTY", "SD_NAME", "COUNTY_NAME", "Year"]

    
    PBA_base["ZONE"] = PBA_base["ZONE"].astype(str)
    taz_sd["ZONE"] = taz_sd["ZONE"].astype(str)

    # 2) pick off the right columns from taz_sd
    lookup = taz_sd[["ZONE", "SD_NAME", "COUNTY_NAME"]]


    # 3) build your long table
    df_base_long = (
        PBA_base
        .assign(
            Year=baseline_year,
            gqpop=lambda d: d["TOTPOP"].astype(int) - d["HHPOP"].astype(int)
        )
        .merge(lookup, on="ZONE", how="left")
        .melt(
            id_vars=id_vars,
            value_vars=[c for c in summary_cols + ["gqpop"] if c in PBA_base.columns],
            var_name="Variable",
            value_name="Value"
        )
    )

    # 4) write it out
    base_long_path = os.path.join(
        str(baseline_year), f"TAZ1454_{baseline_year}_long.csv"
    )
    df_base_long.to_csv(base_long_path, index=False, quoting=1)
    print(f"Wrote {base_long_path}")