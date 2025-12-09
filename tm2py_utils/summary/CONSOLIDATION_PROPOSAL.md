# Proposal: Consolidate Summary Systems

## Current Situation

We currently have **two parallel systems** doing essentially the same work:

### System 1: `core_summaries/core_summaries.py`
- **1000+ line monolithic script**
- Reads raw model outputs (trips, tours, households, persons)
- Combines individual + joint records
- Generates aggregated CSVs (TripSummaryByMode, AutomobileOwnership, etc.)
- Outputs to `{scenario}/core_summaries/` folder
- **Used by:** `tm2_mode_analysis.py` for Excel/PNG reports

### System 2: `validation/summaries/`
- **Modular approach** across multiple files:
  - `trip_summary.py` - Trip aggregations
  - `tour_summary.py` - Tour aggregations  
  - `household_summary.py` - Household demographics
  - `worker_summary.py` - Work location choice
  - `config_driven_summaries.py` - Generic config-based summaries
- **Config-driven** via `validation_config.yaml`
- Outputs to `validation/outputs/` folder
- **Used by:** Streamlit validation dashboard (https://tm2-validation-dashboard.streamlit.app/)

### The Problem: Duplication

Both systems:
- Read the same raw CSV files (`indivTripData_1.csv`, `jointTourData_1.csv`, etc.)
- Perform the same data transformations (combine joint records, apply mode labels, merge household attributes)
- Generate similar aggregations (mode share, purpose distribution, auto ownership)
- Write similar output CSVs with slightly different column names

This creates:
- **Maintenance burden** - Bug fixes and enhancements must be applied twice
- **User confusion** - Which system should I run? Which outputs should I use?
- **Data inconsistencies** - Slight differences in logic can produce different results
- **Wasted computation** - Processing the same data twice takes 2x the time

## Proposed Solution: Consolidate on Validation System

**Recommendation:** Deprecate `core_summaries.py`, extend validation system to meet all needs.

### Why Keep Validation System?

1. **Better Architecture**
   - Modular design (separate files by domain) vs monolithic script
   - Config-driven summaries (no code changes needed for new summaries)
   - Clear separation of concerns (data loading, processing, aggregation)

2. **More Flexible**
   - YAML configuration allows non-programmers to add summaries
   - Binning specifications defined once, applied consistently
   - Easy to add/remove summaries without editing Python code
   - **NEW: Summary type filtering** - Select "core" vs "validation" summaries

3. **Already Has Rich Features**
   - Automatic sample rate weighting
   - Share calculations (within-group percentages)
   - Multiple aggregation types (count, mean, sum, etc.)
   - Support for multiple scenarios/datasets
   - Standardized column naming via `ctramp_data_model.yaml`

4. **Active Development**
   - Recently integrated PopulationSim summaries
   - Dashboard actively used for stakeholder presentations
   - More extensible for future needs

### NEW: Summary Type Filtering

Each summary is now tagged as either **"core"** or **"validation"**:

```yaml
custom_summaries:
  - name: "auto_ownership_regional"
    summary_type: "core"  # Essential, matches core_summaries.py output
    ...
  
  - name: "auto_ownership_by_household_size"
    summary_type: "validation"  # Extended analysis for dashboard
    ...
```

Users can control what gets generated:

```yaml
# Generate only core summaries (fast, essential analysis)
generate_summaries: "core"

# Generate only validation summaries (dashboard-focused)
generate_summaries: "validation"

# Generate everything (default)
generate_summaries: "all"
```

**Current summary breakdown:**
- **21 core summaries** - Essential analysis matching core_summaries.py outputs
- **13 validation summaries** - Extended analysis for dashboard/validation
- **Total: 34 summaries**

Core summaries now include:
- Auto ownership (regional, by income)
- Tour summaries (frequency, mode, timing)
- Trip summaries (mode, purpose, distance, travel time)
- Activity patterns / CDAP (5 breakdowns: overall, by person type, age, county, auto ownership)
- Journey to work (overall and by mode)

Use `python list_summaries.py` to see full breakdown.

### Quick Start: Using Summary Type Filtering

Before consolidation, you can already use the validation system's filtering feature:

```bash
# See what summaries are configured
cd tm2py_utils/summary/validation
python list_summaries.py

# Generate only core summaries (matches core_summaries.py output)
# Edit validation_config.yaml: generate_summaries: "core"
python -m tm2py_utils.summary.validation.summaries.run_all --config validation_config.yaml

# Generate only validation summaries (dashboard-specific)
# Edit validation_config.yaml: generate_summaries: "validation"
python -m tm2py_utils.summary.validation.summaries.run_all --config validation_config.yaml

# Generate all summaries (default)
# Edit validation_config.yaml: generate_summaries: "all"
python -m tm2py_utils.summary.validation.summaries.run_all --config validation_config.yaml
```

This lets you experiment with consolidation gradually:
1. Run validation system with `generate_summaries: "core"` 
2. Compare outputs with core_summaries.py outputs
3. Verify they match (within tolerance)
4. Once validated, switch to validation system exclusively

## Implementation Plan

#### Phase 1: Extend Validation System (No Disruption)

Add missing summaries from core_summaries to validation config:

```yaml
custom_summaries:
  # Time of Day Analysis
  - name: "tour_time_of_day"
    description: "Tour start/end time distribution"
    data_source: "tours"
    group_by: ["tour_purpose", "tour_mode", "start_period", "end_period"]
    
  # Trip Distance Analysis  
  - name: "trip_distance_by_mode_purpose"
    description: "Average trip distance by mode and purpose"
    data_source: "trips"
    group_by: ["trip_mode", "tour_purpose", "income_category_bin"]
    aggregations:
      trips: "count"
      avg_distance: {"column": "trip_distance_miles", "agg": "mean"}
    
  # Active Time Analysis
  - name: "active_transport_time"
    description: "Time spent walking/biking"
    data_source: "trips"
    group_by: ["income_category_bin"]
    filters:
      trip_mode: [9, 10]  # Walk and Bike
    aggregations:
      trips: "count"
      total_minutes: {"column": "trip_time", "agg": "sum"}
```

**Result:** Validation system produces all CSVs that core_summaries produces.

#### Phase 2: Dual Output Mode (Backward Compatibility)

Configure validation system to write outputs to both locations:

```yaml
# validation_config.yaml
output_directory: "validation/outputs"

# Also write to core_summaries location for backward compatibility
write_core_summaries: true
core_summaries_aliases:
  tour_time_of_day: "TimeOfDay.csv"
  trip_distance_by_mode_purpose: "TripDistance.csv"
  auto_ownership_regional: "AutomobileOwnership.csv"
```

**Result:** Existing scripts/tools that expect files in `core_summaries/` continue working.

#### Phase 3: Update Consumers

Update `tm2_mode_analysis.py` and other scripts to read from validation outputs:

```python
# Old:
data_dir = Path(model_run) / "core_summaries"

# New:
data_dir = Path(model_run) / "validation" / "outputs"
```

**Result:** All consumers use single source of truth.

#### Phase 4: Deprecate core_summaries.py

Add deprecation warning to script:

```python
if __name__ == "__main__":
    warnings.warn(
        "core_summaries.py is deprecated. "
        "Please use validation/summaries/run_all.py instead. "
        "See CONSOLIDATION_PROPOSAL.md for details.",
        DeprecationWarning
    )
    main()
```

**Result:** Clear migration path communicated.

## Benefits

### For Users
- **Single command** to generate all summaries: `python -m tm2py_utils.summary.validation.summaries.run_all`
- **Consistent outputs** - Same aggregation logic across all tools
- **Easier to extend** - Add YAML config instead of editing Python code
- **Better documentation** - Config file is self-documenting

### For Developers
- **Less code to maintain** - One system instead of two
- **Easier testing** - Modular functions easier to unit test
- **Clearer responsibilities** - Each module has focused purpose
- **Faster development** - Config-driven means less boilerplate

### For The Project
- **Reduced technical debt** - Eliminate duplicate code paths
- **Improved quality** - Single implementation means consistent QA
- **Better scalability** - Config system handles growth better than monolithic script
- **Knowledge consolidation** - Team expertise focused on one system

## Risks & Mitigations

### Risk: Breaking existing workflows
**Mitigation:** Phase 2 (dual output) maintains backward compatibility. Existing paths continue working during transition.

### Risk: Missing functionality
**Mitigation:** Phase 1 ensures validation system has all core_summaries capabilities before deprecation. Side-by-side comparison validates equivalence.

### Risk: Performance regression
**Mitigation:** Validation system already processes same data. Performance should be comparable. Can be benchmarked before cutover.

### Risk: Adoption resistance
**Mitigation:** 
- Gradual rollout (4 phases) allows learning and adjustment
- Documentation and training provided
- Support period where both systems available
- Clear benefits communicated (less confusion, single source of truth)

## Timeline

- **Week 1-2:** Implement Phase 1 (extend validation config)
- **Week 3:** Validate outputs match core_summaries (compare CSVs)
- **Week 4:** Implement Phase 2 (dual output mode)
- **Week 5-6:** Update consuming scripts (Phase 3)
- **Week 7:** Add deprecation warnings (Phase 4)
- **Week 8+:** Monitor usage, provide support, eventual removal

## Success Metrics

- ✅ All summaries from core_summaries available via validation system
- ✅ Output CSVs match within acceptable tolerance (<0.1% difference)
- ✅ Existing workflows (dashboard, tm2_mode_analysis) work with new outputs
- ✅ Runtime performance within 10% of current total time (might even be faster with single run)
- ✅ Zero regressions in downstream tools/reports

## Recommendation

**Proceed with consolidation.** The validation system is better architected and more maintainable. The phased approach minimizes risk while delivering immediate benefits (reduced confusion, single source of truth). The config-driven design will make the system easier to extend as model validation needs evolve.

---

**Questions or concerns?** Please discuss before implementation begins.
