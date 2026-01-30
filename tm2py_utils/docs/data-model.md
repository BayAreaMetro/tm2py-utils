# CTRAMP Data Model Reference

This document describes the **data formats** supported by the validation summary system. The system supports multiple model formats (TM1, TM2) and survey data through configuration files.

## Overview

The CTRAMP (Coordinated Travel-Regional Activity Modeling Platform) data model consists of **four core tables** that represent household travel behavior at different levels of detail:

1. **Households** - Demographics and vehicle ownership
2. **Persons** - Individual characteristics and daily patterns
3. **Tours** - Round-trip journeys from/to home (or workplace)
4. **Trips** - Individual trip segments within tours

These tables have a **hierarchical relationship**: households contain persons, persons make tours, tours consist of trips.

## Data Model Configuration

The system uses **YAML configuration files** to adapt to different data formats. The config file specifies:

- **Metadata**: Model type (TM1/TM2/survey), version, description
- **File patterns**: Expected filenames (e.g., `personData_1.csv` vs `personData.csv`)
- **Column mappings**: How to standardize column names
- **Value labels**: Decode numeric codes to readable labels
- **Geography system**: TAZ (TM1) vs MGRA (TM2)
- **Mode definitions**: 21 modes (TM1) vs 17 modes (TM2)

**Available configs:**

- `ctramp_data_model.yaml` (default) - **TM1 format**, also compatible with BATS survey data
- `tm2_data_model.yaml` - TM2 format with MGRA geography and 48 time periods
- `survey_data_model.yaml` - Specialized for travel survey data

**Usage:**
```bash
# TM1 or survey (default)
python summarize_model_run.py "path/to/output"

# TM2 (explicit config)
python summarize_model_run.py "path/to/output" --config data_model/tm2_data_model.yaml
```

## Core Data Files

### TM1 Format (Default)

Expected files for TM1 models and BATS survey:

| File Pattern | Description | Required |
|-------------|-------------|----------|
| `householdData_{iteration}.csv` | Household demographics and vehicle ownership | ✅ |
| `personData_{iteration}.csv` | Person-level attributes and activity patterns | ✅ |
| `indivTourData_{iteration}.csv` | Individual tour patterns (round-trips) | ✅ |
| `indivTripData_{iteration}.csv` | Individual trip segments | ✅ |
| `wsLocResults.csv` | Workplace and school location choices | ⚠️ Optional |

**TM1-specific features:**
- Geography: **TAZ** (Traffic Analysis Zones, ~1,454 zones)
- Time: **Hour of day** (0-23) in `start_hour`, `end_hour`
- Modes: **21 transportation modes** (includes detailed transit submodes)
- File pattern: May use `_final` suffix instead of iteration number

### TM2 Format

Expected files for TM2 models (when using `--config data_model/tm2_data_model.yaml`):

| File Pattern | Description | Required |
|-------------|-------------|----------|
| `householdData_{iteration}.csv` | Same structure, different geography | ✅ |
| `personData_{iteration}.csv` | Same structure | ✅ |
| `indivTourData_{iteration}.csv` | Different time/geography columns | ✅ |
| `indivTripData_{iteration}.csv` | Different time/geography columns | ✅ |

**TM2-specific features:**
- Geography: **MGRA** (Micro Geographic Analysis Zones, ~40,000 zones)
- Time: **Half-hour periods** (1-48) in `start_period`, `end_period`
- Modes: **17 transportation modes** (consolidated transit modes)

**Note**: `{iteration}` is typically `1` for final model outputs (e.g., `householdData_1.csv`). The system auto-detects the highest iteration if multiple exist.

### Geography Reference File

The system also requires a **geography lookup file** to map zones to counties/districts:

- **File**: `tm2py_utils/inputs/maz_taz/mazs_tazs_county_tract_PUMA_2.5.csv`
- **Purpose**: Joins home_mgra to county names and planning districts
- **Key columns**: `MAZ_SEQ`, `county_name`, `DistName`

This file is **not** in the model output directory - it's a static reference file in the workspace.

## Table Schemas

### 1. Households (`householdData_{iteration}.csv`)

Household-level demographics, location, and vehicle ownership.

**Required Columns:**

| Column Name | Description | Example Values | Notes |
|------------|-------------|----------------|-------|
| `hh_id` | Unique household identifier | 1562223, 1580323, ... | Primary key |
| `home_mgra` | Home location MGRA | 3, 4, 5, ..., 1454 | Joins to geography lookup |
| `income` | Annual household income (dollars) | 140705, 125256, 772355 | Continuous dollar amount |
| `autos` | Number of vehicles | 0, 1, 2, 3, 4, 5, 6+ | Integer count |
| `size` | Household size (persons) | 1, 2, 3, ..., 15 | Total household members |
| `workers` | Number of workers | 0, 1, 2, ... | Workers ≤ size |
| `sampleRate` | Sample expansion factor | 0.01, 0.05, 0.5, 1.0 | **Decimal fraction** (0.01 = 1% sample) |

**Optional Columns:**

| Column Name | Description | Example Values |
|------------|-------------|----------------|
| `automated_vehicles` | Number of autonomous vehicles | 0, 1, 2 |
| `transponder` | Has toll transponder | 0, 1 |
| `cdap_pattern` | Coordinated Daily Activity Pattern | "MMNHH" (M/N/H per person) |
| `jtf_choice` | Joint tour frequency | 0, 1, 2, 3 |

**Key Points:**
- `sampleRate` is the **sampling fraction**, not the expansion factor (system inverts it: 0.01 → weight of 100.0)
- `home_mgra` must exist in the geography lookup file to get county/district names
- `income` is continuous in dollars, not categorical (binning must be done in postprocessing or summary config)

**Official Documentation**: https://bayareametro.github.io/tm2py/ctramp-outputs/household/

---

### 2. Persons (`personData_{iteration}.csv`)

Individual characteristics, employment, and daily activity patterns.

**Required Columns:**

| Column Name | Description | Example Values | Notes |
|------------|-------------|----------------|-------|
| `hh_id` | Household identifier | 1562223, 1580323, ... | Foreign key to households |
| `person_id` | Unique person identifier | 3806279, 3841021, ... | Primary key (globally unique) |
| `person_num` | Person number in household | 1, 2, 3, ... | 1 to household size |
| `age` | Person age in years | 9, 12, 39, 47, 51 | Integer |
| `gender` | Gender | "m", "f" | **Text values**: "m"=Male, "f"=Female |
| `type` | Person type classification | **Text values** | See person type values below |

**Person Type Values** (`type`) - **Text Strings**:

| Value | Description |
|------|-------------|
| "Full-time worker" | Full-time worker |
| "Part-time worker" | Part-time worker |
| "University student" | University student |
| "Non-worker" | Non-working adult |
| "Retired" | Retired adult |
| "Student of driving age" | Driving-age student (high school) |
| "Student of non-driving age" | School-age child (K-8) |
| "Child too young for school" | Preschool child |

**Optional but Common Columns:**

| Column Name | Description | Example Values |
|------------|-------------|----------------|
| `cdap` | Coordinated Daily Activity Pattern | "M", "N", "H" |
| `value_of_time` | Value of time ($/hour) | 12.50, 25.00 |
| `telecommute` | Telecommute choice | 0, 1 |
| `transit_subsidy_choice` | Has transit subsidy | 0, 1 |
| `transit_pass_choice` | Transit pass type | 0, 1, 2 |
| `fp_choice` | Free parking at work | 0, 1 |
| `sampleRate` | Sample expansion factor | 0.05, 0.5, 1.0 |

**CDAP Codes**:
- `M` = Mandatory (work/school tour)
- `N` = Non-mandatory (shopping, discretionary, etc.)
- `H` = Home (no out-of-home activity)

**Official Documentation**: https://bayareametro.github.io/tm2py/ctramp-outputs/person/

---

### 3. Individual Tours (`indivTourData_{iteration}.csv`)

Round-trip journeys from home (or workplace) to a destination and back.

**Required Columns:**

| Column Name | Description | Example Values | Notes |
|------------|-------------|----------------|-------|
| `hh_id` | Household identifier | 1, 2, 3, ... | Foreign key |
| `person_id` | Person identifier | 1, 2, 3, ... | Foreign key |
| `person_num` | Person number in household | 1, 2, 3 | - |
| `person_type` | Person type classification | Text values | Same as persons.type |
| `tour_id` | Tour sequence for this person | 0, 1, 2, 3 | Primary key (0-indexed, unique per person) |
| `tour_category` | High-level tour classification | "MANDATORY", "INDIVIDUAL_NON_MANDATORY", "AT_WORK" | Text values |
| `tour_purpose` | Specific tour purpose | "Work", "Shop", "Discretionary" | Text values |
| `start_period` | Departure time period | 1-40 | 30-minute intervals (1=5:00-5:30 AM, 7=8:00-8:30 AM) |
| `end_period` | Return time period | 1-40 | Same scale as start_period |

**Tour Purpose Values** (text strings in data):
- `Work` - Work tour
- `School` - K-12 school tour
- `University` - University/college tour
- `Escort` - Escort someone (pick-up/drop-off)
- `Shop` - Shopping
- `Maintenance` - Personal business
- `Eating Out` - Dining
- `Visiting` - Social/visiting
- `Discretionary` - Recreation/leisure
- `Work-Based` - At-work subtour

**Optional but Common Columns:**

| Column Name | Description | Example Values |
|------------|-------------|----------------|
| `orig_mgra` | Origin MGRA | 100, 200 (home or workplace) |
| `dest_mgra` | Destination MGRA | 150, 250 |
| `tour_mode` | Primary tour mode | 1-17 (see mode codes) |
| `tour_distance` | Round-trip distance (miles) | 5.2, 12.8 |
| `tour_time` | Round-trip time (minutes) | 45, 90 |
| `num_ob_stops` | Outbound intermediate stops | 0, 1, 2, 3 |
| `num_ib_stops` | Inbound intermediate stops | 0, 1, 2, 3 |
| `sampleRate` | Sample expansion factor | 0.05, 0.5, 1.0 |

**Time Periods** (1-40, 30-minute intervals starting at 5:00 AM):
- 1 = 5:00-5:30 AM
- 7 = 8:00-8:30 AM (typical morning commute)
- 13 = 11:00-11:30 AM
- 25 = 5:00-5:30 PM (typical evening commute)
- 40 = 3:00-3:30 AM (next day)

**Official Documentation**: https://bayareametro.github.io/tm2py/ctramp-outputs/individual-tours/

---

### 4. Individual Trips (`indivTripData_{iteration}.csv`)

Individual trip segments (one-way movements) that make up tours.

**Required Columns:**

| Column Name | Description | Example Values | Notes |
|------------|-------------|----------------|-------|
| `hh_id` | Household identifier | 1, 2, 3, ... | Foreign key |
| `person_id` | Person identifier | 1, 2, 3, ... | Foreign key |
| `person_num` | Person number in household | 1, 2, 3 | - |
| `tour_id` | Tour identifier | 1, 2, 3 | Foreign key to tours |

**Optional but Common Columns:**

| Column Name | Description | Example Values |
|------------|-------------|----------------|
| `stop_id` | Trip sequence within tour | -1 (direct), 0, 1, 2 |
| `inbound` | Trip direction | 0 (outbound), 1 (inbound) |
| `tour_purpose` | Parent tour purpose | "Work", "Shop", etc. |
| `orig_purpose` | Origin activity purpose | "Home", "Work", "Shop" |
| `dest_purpose` | Destination activity purpose | "Work", "Shop", "Home" |
| `orig_mgra` | Origin MGRA | 100, 200 |
| `dest_mgra` | Destination MGRA | 150, 250 |
| `trip_dist` | Trip distance (miles) | 2.5, 5.0 |
| `stop_period` | Departure time period | 1-40 |
| `trip_mode` | Trip transportation mode | 1-17 (see mode codes) |
| `tour_mode` | Parent tour mode | 1-17 |
| `sampleRate` | Sample expansion factor | 0.05, 0.5, 1.0 |

**Stop ID Interpretation**:
- `-1` = Direct trip (no intermediate stops)
- `0`, `1`, `2`, ... = Intermediate stop sequence

**Official Documentation**: https://bayareametro.github.io/tm2py/ctramp-outputs/individual-trips/

---

### 5. Workplace/School Location (Optional)

Location choice results for work and school.

**File**: `wsLocResults.csv` (no iteration number)

**Key Columns:**

| Column Name | Description | Example Values |
|------------|-------------|----------------|
| `HHID` | Household identifier | 1, 2, 3 |
| `PersonID` | Person identifier | 1, 2, 3 |
| `WorkLocation` | Work MGRA | 0 (no work), 100, 200 |
| `SchoolLocation` | School MGRA | 0 (no school), 150, 250 |
| `WorkLocationDistance` | Home to work distance | 0.0, 5.2, 12.8 |
| `SchoolLocationDistance` | Home to school distance | 0.0, 2.5, 8.0 |

**Official Documentation**: https://bayareametro.github.io/tm2py/ctramp-outputs/workplace-school-location/

---

## Transportation Mode Codes

The 17-mode standard used for `tour_mode` and `trip_mode`:

| Code | Mode Name | Description |
|------|-----------|-------------|
| 1 | SOV_GP | Single Occupant Vehicle - General Purpose lanes |
| 2 | SOV_PAY | Single Occupant Vehicle - Express/Toll lanes |
| 3 | SR2_GP | Shared Ride 2 - General Purpose |
| 4 | SR2_HOV | Shared Ride 2 - HOV lanes |
| 5 | SR2_PAY | Shared Ride 2 - Express/Toll |
| 6 | SR3_GP | Shared Ride 3+ - General Purpose |
| 7 | SR3_HOV | Shared Ride 3+ - HOV lanes |
| 8 | SR3_PAY | Shared Ride 3+ - Express/Toll |
| 9 | WALK_TRN | Walk to Transit |
| 10 | PNR_TRN | Park-and-Ride to Transit |
| 11 | KNR_TRN | Kiss-and-Ride to Transit |
| 12 | TNC_TRN | TNC to Transit |
| 13 | WALK | Walk |
| 14 | BIKE | Bicycle |
| 15 | TAXI | Taxi |
| 16 | TNC_SINGLE | TNC Single (Uber/Lyft alone) |
| 17 | TNC_SHARED | TNC Shared (UberPool/Lyft Shared) |

**Common Aggregations:**
- **Auto**: 1-8 (all SOV and shared ride modes)
- **Transit**: 9-12 (all transit access modes)
- **Active**: 13-14 (walk and bike)
- **TNC/Taxi**: 15-17 (taxi and TNC modes)

---

## Data Relationships

```
households (hh_id)
    ↓
persons (hh_id, person_id)
    ↓
tours (person_id, tour_id)
    ↓
trips (tour_id, trip_id/stop_id)
```

**Join Keys:**
- `households.hh_id` → `persons.hh_id`
- `persons.person_id` → `tours.person_id`
- `tours.tour_id` → `trips.tour_id`
- `households.home_mgra` → `geography.MAZ_SEQ` (for county/district)

---

## Sample Expansion (Weighting)

**CRITICAL**: The `sampleRate` field is a **decimal fraction**, not an expansion factor.

- **In CSVs**: `sampleRate = 0.01` means 1% sample (typical for full region model)
- **Expansion factor**: `1 / sampleRate = 1 / 0.01 = 100.0`
- **Interpretation**: Each record represents 100 actual households/persons/tours/trips

**The system automatically inverts `sampleRate` to calculate weights.**

**Common Values:**
- `0.01` = 1% sample (expansion factor 100) - typical for full model runs
- `0.05` = 5% sample (expansion factor 20) - smaller test runs
- `0.50` = 50% sample (expansion factor 2) - quick tests
- `1.00` = 100% sample (expansion factor 1) - no sampling

| Sample Rate | Expansion Factor | Meaning |
|-------------|------------------|---------|
| 1.0 | 1.0 | 100% sample (no expansion) |
| 0.5 | 2.0 | 50% sample (each record = 2 real units) |
| 0.05 | 20.0 | 5% sample (each record = 20 real units) |

**All summaries are weighted** by default using the household `sampleRate` field.

---

## Preparing Travel Survey Data

To validate model outputs with household travel surveys (e.g., NHTS, CHTS), you must **transform survey data to match this exact format**:

### Required Steps:

1. **Match column names exactly** - Use `hh_id`, `person_id`, `tour_mode`, etc. (not survey-specific names)

2. **Align geography** - Map survey zones/TAZs to MGRAs used by the model

3. **Standardize codes**:
   - Person types → 1-8 codes
   - Tour purposes → "Work", "Shop", etc. (text values)
   - Transportation modes → 1-17 numeric codes
   - Time periods → 1-48 (30-minute intervals)

4. **Add required fields**:
   - `sampleRate` - Survey expansion factor (as percentage if >1, invert if needed)
   - Geography lookup - Ensure survey zones map to counties/districts

5. **Create hierarchy**:
   - Household file with unique `hh_id`
   - Person file with `person_id` linked to `hh_id`
   - Tour/trip files linked to `person_id` and `tour_id`

### Example Transformation:

**Survey Format** (before):
```
household_id,num_autos,hh_size,region
1001,2,3,"San Francisco"
```

**CTRAMP Format** (after):
```
hh_id,autos,size,home_mgra,income,workers,sampleRate
1,2,3,450,3,2,0.01
```

**Key Differences:**
- Survey IDs → Sequential IDs starting from 1
- Region name → `home_mgra` (numeric zone)
- Add missing fields: `income`, `workers`, `sampleRate`
- Column names match CTRAMP exactly

---

## Data Validation

The system expects:

✅ **Valid relationships**: Every person has a household, every tour has a person  
✅ **Consistent geography**: All MGRAs exist in geography lookup  
✅ **Valid codes**: Person types 1-8, modes 1-17, etc.  
✅ **Required columns present**: See schemas above  
✅ **Numeric types correct**: IDs as integers, rates as floats  

❌ **The system does NOT**:
- Check for logical errors (e.g., 8-year-old full-time worker)
- Validate tour/trip sequences
- Verify mode choice feasibility
- Standardize survey data formats

---

## Configuration

The data model is defined in `ctramp_data_model.yaml` which maps:

1. **Input schema** - CSV column names → Internal field names
2. **Value mappings** - Numeric codes → Human-readable labels
3. **Aggregation specs** - How to group categories (e.g., 4+ person households)
4. **Weight fields** - Which columns contain expansion factors

**To customize**: Edit `ctramp_data_model.yaml` if your model uses different column names or codes.

---

## Official TM2 Documentation

Complete CTRAMP data specifications:

- **Overview**: https://bayareametro.github.io/tm2py/ctramp-outputs/
- **Households**: https://bayareametro.github.io/tm2py/ctramp-outputs/household/
- **Persons**: https://bayareametro.github.io/tm2py/ctramp-outputs/person/
- **Tours**: https://bayareametro.github.io/tm2py/ctramp-outputs/individual-tours/
- **Trips**: https://bayareametro.github.io/tm2py/ctramp-outputs/individual-trips/
- **Data Dictionaries**: https://bayareametro.github.io/tm2py/ctramp-outputs/data-dictionaries/

---

## Next Steps

- **[Generate Summaries](generate-summaries.md)** - Run the system on model outputs
- **[Custom Summaries](custom-summaries.md)** - Create new aggregations
- **[External Data](external-data.md)** - Integrate ACS/CTPP/survey data
- **[Validation System Overview](validation-system.md)** - Return to main guide
