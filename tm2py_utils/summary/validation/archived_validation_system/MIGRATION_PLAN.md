# Migration Plan: Hardcoded → Config-Driven Summaries

## Goal
Replace all hardcoded summary modules with config-driven summaries defined in `validation_config.yaml`.

## Strategy
Migrate one summary at a time, verify identical outputs, then proceed.

---

## Current State Analysis

### Hardcoded Summaries (OLD)

**household_summary.py** - 3 summary types:
1. `auto_ownership_regional` - Already in config ✅
2. `auto_ownership_by_income` - Already in config ✅  
3. `household_size` - Not in config ❌
4. `income_distribution` - Not in config ❌

**worker_summary.py** - Check needed

**tour_summary.py** - Check needed

**trip_summary.py** - Check needed

### Config-Driven Summaries (NEW)

Currently in `validation_config.yaml`:
- Auto ownership (6 variants) ✅
- CDAP (2 active, 3 disabled)
- Household size (multiple variants)
- Population/persons by age
- Tours (multiple)
- Trips (multiple)
- Time of day

---

## Phase 1: Household Summaries

### Step 1.1: Test Auto Ownership (Already Configured)

**Hypothesis:** Auto ownership summaries are being generated TWICE - once by hardcoded module, once by config.

**Test:**
```bash
# Check outputs for duplicates
ls outputs/dashboard/auto_ownership*.csv | measure
```

**Actions:**
1. ✅ Verify config summaries exist in validation_config.yaml
2. ⏳ Generate summaries with BOTH systems enabled
3. ⏳ Compare outputs (old vs new)
4. ⏳ If identical, disable hardcoded generation
5. ⏳ Test that config-only works

### Step 1.2: Migrate Household Size Summary

**Current hardcoded logic:**
```python
# household_summary.py line ~90
generate_household_size_summary()
  - Groups by: num_persons
  - Weight: sample_rate
  - Count: households
```

**New config entry needed:**
```yaml
- name: "household_size_regional"
  summary_type: "core"
  description: "Household size distribution"
  data_source: "households"
  group_by: "num_persons"
  weight_field: "sample_rate"
  count_name: "households"
```

**Test steps:**
1. ⏳ Add config entry
2. ⏳ Generate with both systems
3. ⏳ Compare CSV outputs byte-by-byte
4. ⏳ If identical, mark hardcoded for removal

### Step 1.3: Migrate Income Summary

**Current hardcoded logic:**
```python
# household_summary.py line ~120
generate_income_summary()
  - Groups by: income_category / income_category_bin
  - Weight: sample_rate
  - Count: households
```

**New config entry needed:**
```yaml
- name: "households_by_income"
  summary_type: "core"
  description: "Household income distribution"
  data_source: "households"
  group_by: "income_category_bin"
  weight_field: "sample_rate"
  count_name: "households"
```

**Test steps:**
1. ⏳ Add config entry
2. ⏳ Generate with both systems
3. ⏳ Compare outputs
4. ⏳ If identical, mark for removal

### Step 1.4: Disable Hardcoded Household Summaries

Once all household summaries verified:

**In `run_all.py` line ~535:**
```python
# BEFORE:
if SummaryType.AUTO_OWNERSHIP in self.config.enabled_summaries:
    all_summaries.update(household_summary.generate_all_household_summaries(...))

# AFTER:
# Disabled - now using config-driven summaries
# if SummaryType.AUTO_OWNERSHIP in self.config.enabled_summaries:
#     all_summaries.update(household_summary.generate_all_household_summaries(...))
```

**Test:** Regenerate all, verify no household summaries missing.

---

## Phase 2: Worker/Person Summaries

### Step 2.1: Analyze worker_summary.py

**TODO:** List all summaries generated

### Step 2.2-2.N: Migrate each summary

Same process as Phase 1

---

## Phase 3: Tour Summaries

### Step 3.1: Analyze tour_summary.py

**Known summaries:**
- Tour frequency by purpose
- Tour mode choice (overall and by purpose)
- Tour timing (start/end periods)
- Tour distance/duration

### Step 3.2-3.N: Migrate each summary

Same process as Phase 1

---

## Phase 4: Trip Summaries

### Step 4.1: Analyze trip_summary.py

**Known summaries:**
- Trip mode choice
- Trip purpose
- Trip timing
- Trip distance/duration
- Trip generation

### Step 4.2-4.N: Migrate each summary

Same process as Phase 1

---

## Phase 5: Final Cleanup

### Actions:
1. ⏳ Remove `SummaryType` enum (no longer needed)
2. ⏳ Remove `enabled_summaries` config (all are custom_summaries now)
3. ⏳ Delete hardcoded summary files:
   - `household_summary.py`
   - `worker_summary.py`
   - `tour_summary.py`
   - `trip_summary.py`
4. ⏳ Update imports in `run_all.py`
5. ⏳ Update documentation
6. ⏳ Add note to `custom_summary_template.yaml` explaining migration

---

## Testing Checklist

For each migrated summary:
- [ ] Config entry added to validation_config.yaml
- [ ] Generated with both old and new systems
- [ ] CSV outputs compared (ideally identical)
- [ ] Column names match
- [ ] Row counts match
- [ ] Values match (allowing for floating point precision)
- [ ] Dashboard still displays correctly
- [ ] Hardcoded function commented out
- [ ] Full regeneration works without errors

---

## Benefits After Migration

✅ **Single source of truth** - All summaries in validation_config.yaml
✅ **No Python coding required** - Analysts can add summaries via YAML
✅ **Easier maintenance** - One system instead of two
✅ **Consistent behavior** - All summaries use same logic
✅ **Better documentation** - Summary definitions are self-documenting
✅ **Reduced code** - Delete ~1000+ lines of hardcoded summary functions

---

## Risks & Mitigation

**Risk:** Config-driven system missing features needed by hardcoded summaries
**Mitigation:** Enhance config-driven system as needed during migration

**Risk:** Outputs don't match exactly
**Mitigation:** Investigate differences, update config or fix bugs

**Risk:** Breaking existing dashboards
**Mitigation:** Test each dashboard after migration, keep filenames identical

---

## Next Steps

**START HERE:**
1. Run Step 1.1 - Test current auto ownership duplicates
2. Compare outputs from both systems
3. Document any differences
4. Proceed with disabling hardcoded once verified
