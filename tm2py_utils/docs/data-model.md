# CTRAMP Data Model Reference

This document describes the **required data format** for the validation summary system. All input data must conform to this structure, whether from model outputs or household travel surveys.

## Overview

The CTRAMP (Coordinated Travel-Regional Activity Modeling Platform) data model consists of **four core tables** that represent household travel behavior at different levels of detail:

1. **Households** - Demographics and vehicle ownership
2. **Persons** - Individual characteristics and daily patterns
3. **Tours** - Round-trip journeys from/to home (or workplace)
4. **Trips** - Individual trip segments within tours

These tables have a **hierarchical relationship**: households contain persons, persons make tours, tours consist of trips.

## Core Data Files

### Required Files

The system expects these files in each model output directory:

| File Pattern | Description | Required |
|-------------|-------------|----------|
| `householdData_{iteration}.csv` | Household demographics and vehicle ownership | ✅ |
| `personData_{iteration}.csv` | Person-level attributes and activity patterns | ✅ |
| `indivTourData_{iteration}.csv` | Individual tour patterns (round-trips) | ✅ |
| `indivTripData_{iteration}.csv` | Individual trip segments | ✅ |
| `wsLocResults.csv` | Workplace and school location choices | ⚠️ Optional |

**Note**: `{iteration}` is typically `1` for final model outputs (e.g., `householdData_1.csv`).

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
| `hh_id` | Unique household identifier | 1, 2, 3, ... | Primary key |
| `home_mgra` | Home location MGRA | 1, 2, 3, ..., 1454 | Joins to geography lookup |
| `income` | Income category | 1, 2, 3, 4 | 1=Low, 2=Med-Low, 3=Med-High, 4=High |
| `autos` | Number of vehicles | 0, 1, 2, 3, 4, 5, 6+ | Integer count |
| `size` | Household size (persons) | 1, 2, 3, ..., 15 | Total household members |
| `workers` | Number of workers | 0, 1, 2, ... | Workers ≤ size |
| `sampleRate` | Sample expansion factor | 0.05, 0.5, 1.0 | **Percentage** (0.05 = 5% sample) |

**Optional Columns:**

| Column Name | Description | Example Values |
|------------|-------------|----------------|
| `automated_vehicles` | Number of autonomous vehicles | 0, 1, 2 |
| `transponder` | Has toll transponder | 0, 1 |
| `cdap_pattern` | Coordinated Daily Activity Pattern | "MMNHH" (M/N/H per person) |
| `jtf_choice` | Joint tour frequency | 0, 1, 2, 3 |

**Key Points:**
- `sampleRate` is the **sampling percentage**, not the expansion factor (system inverts it: 0.5 → weight of 2.0)
- `home_mgra` must exist in the geography lookup file to get county/district names
- `income` categories represent quartiles (1=lowest, 4=highest)

**Official Documentation**: https://bayareametro.github.io/tm2py/ctramp-outputs/household/

---

### 2. Persons (`personData_{iteration}.csv`)

Individual characteristics, employment, and daily activity patterns.

**Required Columns:**

| Column Name | Description | Example Values | Notes |
|------------|-------------|----------------|-------|
| `hh_id` | Household identifier | 1, 2, 3, ... | Foreign key to households |
| `person_id` | Unique person identifier | 1, 2, 3, ... | Primary key (globally unique) |
| `person_num` | Person number in household | 1, 2, 3, ... | 1 to household size |
| `age` | Person age in years | 5, 25, 65, ... | Integer |
| `gender` | Gender | 1, 2 | 1=Male, 2=Female |
| `type` | Person type classification | 1-8 | See person type codes below |

**Person Type Codes** (`type`):

| Code | Description |
|------|-------------|
| 1 | Full-time worker |
| 2 | Part-time worker |
| 3 | University student |
| 4 | Non-working adult |
| 5 | Retired adult |
| 6 | Driving-age student |
| 7 | School-age child |
| 8 | Preschool child |

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
| `person_type` | Person type classification | 1-8 | Same as persons.type |
| `tour_id` | Tour sequence for this person | 1, 2, 3 | Primary key (unique per person) |
| `tour_category` | High-level tour classification | "MANDATORY", "INDIVIDUAL_NON_MANDATORY", "AT_WORK" | Text values |
| `tour_purpose` | Specific tour purpose | "Work", "Shop", "Discretionary" | Text values |
| `start_period` | Departure time period | 1-48 | 30-minute intervals (1=3:00-3:30 AM, 14=9:30-10:00 AM) |
| `end_period` | Return time period | 1-48 | Same scale as start_period |

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

**Time Periods** (1-48, 30-minute intervals):
- 1 = 3:00-3:30 AM
- 14 = 9:30-10:00 AM
- 34 = 7:30-8:00 PM
- 48 = 2:30-3:00 AM (next day)

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
| `stop_period` | Departure time period | 1-48 |
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
| 9 | WALK | Walk |
| 10 | BIKE | Bicycle |
| 11 | WLK_TRN | Walk to Transit |
| 12 | PNR_TRN | Park-and-Ride to Transit |
| 13 | KNRPRV_TRN | Kiss-and-Ride (Private vehicle) to Transit |
| 14 | KNRTNC_TRN | Kiss-and-Ride (TNC) to Transit |
| 15 | TAXI | Taxi |
| 16 | TNC | Transportation Network Company (Uber/Lyft) |
| 17 | SCHLBUS | School Bus |

**Common Aggregations:**
- **Auto**: 1-8 (all SOV and shared ride modes)
- **Transit**: 11-14 (all transit access modes)
- **Active**: 9-10 (walk and bike)
- **TNC/Taxi**: 15-16

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

**CRITICAL**: The `sampleRate` field is a **percentage**, not an expansion factor.

- **In CSVs**: `sampleRate = 0.05` means 5% sample
- **Expansion factor**: `1 / sampleRate = 1 / 0.05 = 20.0`
- **Interpretation**: Each record represents 20 actual households/persons/tours/trips

**The system automatically inverts `sampleRate` to calculate weights.**

| Sample Rate | Expansion Factor | Meaning |
|-------------|------------------|---------|
| 1.0 | 1.0 | 100% sample (no expansion) |
| 0.5 | 2.0 | 50% sample (each record = 2 real units) |
| 0.05 | 20.0 | 5% sample (each record = 20 real units) |

**All summaries are weighted** by default using the household `sampleRate` field.

---

## Preparing Travel Survey Data

To compare model outputs with household travel surveys (e.g., NHTS, CHTS), you must **transform survey data to match this exact format**:

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
