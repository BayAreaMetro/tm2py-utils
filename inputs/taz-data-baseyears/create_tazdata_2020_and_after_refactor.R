# Constants and Configurations
USAGE <- "
  Create 202X TAZ data from ACS 5-year data.  
  The year for which to generate the tazdata is passed as an argument to this script.
"
ACS_PUMS_5YEAR_LATEST <- 2022
ACS_PUMS_1YEAR_LATEST <- 2023
LODES_YEAR_LATEST <- 2022
EMPRES_LODES_WEIGHT <- 0.5
USPS_PER_THOUSAND_JOBS <- 1.83
USE_TIDYCENSUS_CACHING <- TRUE


# Libraries
suppressMessages(library(tidyverse))
library(tidycensus)
library(readxl)
library(argparser)

USERPROFILE <- gsub("\\\\","/", Sys.getenv("USERPROFILE"))
BOX_TM <- file.path(USERPROFILE, "Box", "Modeling and Surveys")
if (Sys.getenv("USERNAME") %in% c("lzorn")) {
  BOX_TM <- file.path("E://Box/Modeling and Surveys")
} else if (Sys.getenv("USERNAME") %in% c("lzorn")) {
  BOX_TM <- file.path("C:/Box/Modeling and Surveys")
}
PBA_TAZ_2015 <- file.path(BOX_TM, "Share Data", "plan-bay-area-2050", "tazdata", "PBA50_FinalBlueprintLandUse_TAZdata.xlsx")

# Helper Functions
log_message <- function(message) {
  print(paste(Sys.time(), "-", message))
}

write_output <- function(data, year, filename, description) {
  output_file <- file.path(year, filename)
  write.csv(data, output_file, row.names = FALSE, quote = TRUE)
  log_message(paste("Wrote", description, "to", output_file))
}

load_data <- function(year) {
  log_message("Loading data...")
  PBA_TAZ_2015       <- file.path(BOX_TM, "Share Data", "plan-bay-area-2050", "tazdata","PBA50_FinalBlueprintLandUse_TAZdata.xlsx")
TM1                <- file.path(".")
emp_wage_salary    <- read.csv(file.path(TM1,LODES_YEAR,paste0("lodes_wac_employment_",LODES_YEAR,".csv")),header = T)
emp_self_employed  <- read.csv(file.path(TM1,argv$year,paste0("taz_self_employed_workers_",argv$year,".csv")),header = T)
lehd_lodes         <- read.csv(file.path("M://Data/Census/LEHD/Origin-Destination Employment Statistics (LODES)",
                      sprintf("LODES_Bay_Area_county_%d.csv", LODES_YEAR)), header=T) %>% tibble()
TAZ_SD_COUNTY      <- read.csv(file.path("..","geographies","taz-superdistrict-county.csv"), header=T) %>% 
  rename(County_Name=COUNTY_NAME, DISTRICT=SD, DISTRICT_NAME=SD_NAME) %>% select(-SD_NUM_NAME, -COUNTY_NUM_NAME)
}

process_employment_data <- function(emp_wage_salary, emp_self_employed, lehd_lodes, taz_sd_county, year) {
  log_message("Processing employment data...")
  emp_self_employed_w <- emp_self_employed %>%
    select(-c(X)) %>%
    pivot_wider(names_from = industry, values_from = value, values_fill = 0) %>%
    mutate(TOTEMP = rowSums(select(., -zone_id))) %>%
    arrange(zone_id) %>%
    rename(c("TAZ1454" = "zone_id")) %>%
    rename_all(toupper)

  lehd_lodes <- lehd_lodes %>%
    select(-w_state, -h_state) %>%
    rename(TOTEMP = Total_Workers) %>%
    group_by(w_county, h_county) %>%
    summarise(TOTEMP = sum(TOTEMP), .groups = 'drop') %>%
    mutate(TOTEMP = as.integer(round(TOTEMP * (1.0 + USPS_PER_THOUSAND_JOBS / 1000.0))))

  emp_self_employed_county <- left_join(
    emp_self_employed_w,
    select(taz_sd_county, ZONE, County_Name),
    by = c("TAZ1454" = "ZONE")
  ) %>%
    group_by(County_Name) %>%
    summarise(TOTEMP_self = sum(TOTEMP), .groups = 'drop') %>%
    rename(h_county = County_Name) %>%
    mutate(w_county = h_county)

  lehd_lodes <- left_join(lehd_lodes, emp_self_employed_county, by = c("h_county", "w_county")) %>%
    mutate(TOTEMP_self = replace_na(TOTEMP_self, 0)) %>%
    mutate(TOTEMP = TOTEMP + TOTEMP_self) %>%
    select(-TOTEMP_self)

  employment <- bind_rows(emp_wage_salary, emp_self_employed_w, .id = 'src') %>%
    group_by(TAZ1454) %>%
    summarize_if(is.numeric, sum, na.rm = FALSE)

  list(employment = employment, lehd_lodes = lehd_lodes)
}

process_census_data <- function(year, state_code, baycounties, censuskey) {
  log_message("Processing census data...")
  ACS_tract_raw <- tidycensus::get_acs(
    geography = "tract", variables = ACS_tract_variables,
    state = state_code, county = baycounties,
    year = year,
    output = "wide",
    survey = "acs5",
    cache_table = USE_TIDYCENSUS_CACHING,
    key = censuskey
  )

  ACS_BG_raw <- tidycensus::get_acs(
    geography = "block group", variables = ACS_BG_variables,
    state = state_code, county = baycounties,
    year = year,
    output = "wide",
    survey = "acs5",
    cache_table = USE_TIDYCENSUS_CACHING,
    key = censuskey
  )

  DHC_tract_raw <- tidycensus::get_decennial(
    geography = "tract", variables = DHC_tract_variables,
    state = state_code, county = baycounties,
    year = 2020,
    output = "wide",
    sumfile = "dhc",
    cache_table = USE_TIDYCENSUS_CACHING,
    key = censuskey
  )

  list(ACS_tract_raw = ACS_tract_raw, ACS_BG_raw = ACS_BG_raw, DHC_tract_raw = DHC_tract_raw)
}

export_long_format <- function(data, year, filename, description) {
  long_data <- data %>%
    mutate(Year = year) %>%
    gather(
      Variable, Value,
      TOTHH, HHPOP, TOTPOP, EMPRES, SFDU, MFDU, HHINCQ1, HHINCQ2, HHINCQ3, HHINCQ4,
      SHPOP62P, TOTEMP, AGE0004, AGE0519, AGE2044, AGE4564, AGE65P, RETEMPN, FPSEMPN,
      HEREMPN, AGREMPN, MWTEMPN, OTHEMPN, PRKCST, OPRKCST, HSENROLL, COLLFTE, COLLPTE, gqpop
    )
  write_output(long_data, year, filename, description)
}

# Main Script
main <- function() {
  argv <- list(year = 2023)
  stopifnot(argv$year %in% c(2020, 2021, 2023))
  set.seed(argv$year)

  data <- load_data(argv$year)
  employment_data <- process_employment_data(data$emp_wage_salary, data$emp_self_employed, data$lehd_lodes, data$taz_sd_county, argv$year)
  census_data <- process_census_data(argv$year, state_code, baycounties, censuskey)

  export_long_format(
    employment_data$employment,
    argv$year,
    sprintf("TAZ1454_%d_long.csv", argv$year),
    "Employment data in long format"
  )
}

# Run the script
main()