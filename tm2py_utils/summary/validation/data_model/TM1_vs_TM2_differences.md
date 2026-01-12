# TM1 vs TM2 CTRAMP Format Differences

## Summary
This document catalogs differences between Travel Model One (TM1) and Travel Model Two (TM2) CTRAMP output formats to ensure the validation system supports both.

---

## 1. Mode Dictionaries ✅ FIXED

### TM2 Format (17 modes)
| Code | Name | Category | Description |
|------|------|----------|-------------|
| 1-8 | SOV_GP, SOV_PAY, SR2_GP, SR2_HOV, SR2_PAY, SR3_GP, SR3_HOV, SR3_PAY | Auto | Various auto occupancy/facility types |
| 9 | WALK | Active | Walk only |
| 10 | BIKE | Active | Bicycle only |
| 11 | WLK_TRN | Transit | Walk to Transit (generic) |
| 12 | PNR_TRN | Transit | Park-and-Ride to Transit |
| 13 | KNRPRV_TRN | Transit | Kiss-and-Ride Private to Transit |
| 14 | KNRTNC_TRN | Transit | Kiss-and-Ride TNC to Transit |
| 15 | TAXI | TNC/Taxi | Taxi |
| 16 | TNC | TNC/Taxi | Uber/Lyft |
| 17 | SCHLBUS | School Bus | School Bus |

### TM1 Format (21 modes)
Extends TM2 with detailed transit submodes:
| Code | Name | Category | Description |
|------|------|----------|-------------|
| 1-17 | *(Same as TM2)* | *(Same)* | *(Same)* |
| 18 | WLK_LOC | Transit | Walk to Local Bus |
| 19 | WLK_LRF | Transit | Walk to Light Rail/Ferry |
| 20 | WLK_EXP | Transit | Walk to Express Bus |
| 21 | WLK_HVY | Transit | Walk to Heavy Rail |

**Status**: ✅ **FIXED** - Added modes 18-21 to `ctramp_data_model.yaml`

---

## 2. Trip Mode Codes 🚨 NEEDS INVESTIGATION

### Issue
TM2 trip documentation shows modes 11-17 as:
- 11: WALK_LOC (Walk to Local Transit)
- 12: WALK_LRF (Walk to Light Rail/Ferry) 
- 13: WALK_EXP (Walk to Express Bus)
- 14: WALK_HVY (Walk to Heavy Rail)
- 15: WALK_COM (Walk to Commuter Rail)
- 16: DRIVE_LOC (Drive to Local Transit)
- 17: DRIVE_LRF (Drive to Light Rail/Ferry)

This **differs from tour modes**! Trips may use more detailed transit codes internally.

**Action Needed**: Verify actual trip_mode codes in survey data vs model data

---

## 3. Geography System Differences 🚨 MAJOR

### TM2 Format
- **Zone System**: MGRA (Micro Geographic Analysis Zone)
- **Zone Count**: ~40,000 zones
- **Field Names**: 
  - Household: `home_mgra`
  - Tour: `orig_mgra`, `dest_mgra`
  - Trip: `orig_mgra`, `dest_mgra`, `parking_mgra`

### TM1 Format  
- **Zone System**: TAZ (Traffic Analysis Zone)
- **Zone Count**: 1,454 zones
- **Field Names**:
  - Household: `home_taz` or `taz`
  - Tour: `orig_taz`, `dest_taz`
  - Trip: `orig_taz`, `dest_taz`

**Status**: ⚠️ **PARTIALLY HANDLED** - Current data model marks `home_mgra` as required but your survey has `taz`. Need to add TM1 alternatives.

---

## 4. Time Period Representation 🚨 MAJOR

### TM2 Format
- **Periods**: 48 half-hour periods (30-minute intervals)
- **Start Time**: 3:00 AM = Period 1
- **Field Names**: `start_period`, `end_period`
- **Range**: 1-48
- **Example**: 8:30 AM = Period 12

### TM1 Format
- **Likely Uses**: Hour of day (0-23)
- **Field Names**: `start_hour`, `end_hour` (observed in your survey data)
- **Range**: 0-23
- **Example**: 8:30 AM = 8 or 8.5

**Status**: ⚠️ **NOT HANDLED** - Current validation expects `start_period`/`end_period`, but your survey has `start_hour`/`end_hour`

---

## 5. Column Naming Conventions

### TM2 Format
- Uses lowercase with underscores: `person_id`, `tour_mode`, `start_period`
- Iteration suffix: `personData_1.csv`, `householdData_3.csv`

### TM1/Survey Format
- May use CamelCase: `PersonData.csv`, `HouseholdData.csv`
- No iteration suffix in survey data

**Status**: ✅ **FIXED** - Updated `find_latest_iteration_file()` to handle both

---

## 6. Sample Rate / Weight Fields

### TM2 Format
- **Field Name**: `sampleRate`
- **Interpretation**: Sampling percentage (0.05 = 5% sample)
- **Usage**: Inverted to get expansion factor (0.05 → 20.0)

### TM1/Survey Format
- **Field Name**: May vary or be absent
- Survey data often has no weights (each record = 1 observation)

**Status**: ✅ **HANDLED** - System continues without weights when missing

---

## 7. Person Type Codes

### TM2 Format (8 types)
1. Full-time worker
2. Part-time worker  
3. University student
4. Non-working adult
5. Retired adult
6. Driving-age student
7. School-age child
8. Preschool child

### TM1 Format
*Needs verification* - Likely similar or identical

**Status**: ⏸️ **NEEDS VERIFICATION**

---

## 8. Tour Purpose Values

### TM2 Format
Uses **text values** (not numeric codes):
- Mandatory: "Work", "School", "University"
- Non-Mandatory: "Escort", "Shop", "Maintenance", "Discretionary", "Visiting", "Eating Out"  
- At-Work: "Work-Based"

### TM1 Format
*Needs verification* - May use different text values or numeric codes

**Status**: ✅ **LIKELY OK** - Your survey data uses text purposes that match

---

## Recommended Actions

### High Priority 🚨
1. **Add TM1 geography field alternatives** (`home_taz`, `orig_taz`, `dest_taz`)
2. **Add TM1 time field alternatives** (`start_hour`, `end_hour`)
3. **Verify trip mode codes** in actual TM1 vs TM2 data

### Medium Priority ⚠️
4. **Document person type differences** between TM1 and TM2
5. **Add flexible geography column mapping** to handle both MAZ and TAZ systems

### Low Priority ℹ️
6. **Create TM1-specific summary templates** if aggregation needs differ
7. **Document known limitations** when comparing TM1 survey to TM2 model outputs

---

## Implementation Strategy

### Option A: Dual Column Mappings (Recommended)
Add alternative column names to `input_schema` in `ctramp_data_model.yaml`:
```yaml
households:
  columns:
    required:
      home_zone: ["home_mgra", "home_taz", "taz"]  # Try all alternatives
```

### Option B: Format Detection
Auto-detect format based on file patterns and columns present, then apply appropriate schema.

### Option C: Explicit Configuration  
Add `--format tm1` or `--format tm2` flag to validation script.

**Recommendation**: Start with **Option A** (most flexible, backward compatible)
