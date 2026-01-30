# Summary Design System Plan

## Overview

This document outlines the design principles, architecture decisions, and implementation strategy for the tm2py-utils summary validation system. It serves as the foundational guide for combining core summaries with validation capabilities while maintaining flexibility and maintainability.

## Core Design Principles

### 1. Modularity and Selective Execution

**Principle**: Summaries should be independently executable and selectively runnable.

- **Run standalone**: Summaries can be executed against old model runs without rerunning the model
- **Modular selection**: Users can run only one summary or any combination they need
- **Configuration-driven**: Summary selection specified in `scenario_config` via `final_components` array

**Example**:
```toml
# Run only essential summaries
final_components = ["post_processor", "network_summary"]

# Add core summaries
final_components = ["post_processor", "network_summary", "core_summary"]

# Run everything for major validation
final_components = ["post_processor", "network_summary", "rtp_summary", "calibration_summary"]
```

**Implementation Requirements**:
- Each summary type is self-contained
- Command-line option to run against processed survey data
- Can run across multiple historical model runs

### 2. Summary Tiering System

**Principle**: Different summary types have different stability and execution requirements.

**Summary Tiers**:

| Tier | Type | Characteristics | Configuration |
|------|------|-----------------|---------------|
| **Always Run** | Core Summaries | Stable, infrequently updated, essential validation | Always executed, not configurable |
| **Configurable** | RTP Metrics | Often changing, project-specific | User-selectable via scenario_config |
| **Configurable** | TIP Metrics | Project-specific transportation improvements | User-selectable via scenario_config |
| **Configurable** | Calibration Summaries | Detailed validation against observed data | User-selectable via scenario_config |

**Guiding Questions**:
- What is configurable via scenario_config and what is always run?
- Core summary should always run - how do we enforce this?

### 3. Data Model Separation

**Principle**: Data models live in tm2py and are imported, not redefined in summary code.

**Architecture**:
- Data models reside in tm2py data models folder
- Summary system pivots off known data model and acceptable values
- No hardcoded values or schema definitions in summary code
- Fixed schemas ensure consistency

**Data Models to Implement**:
- ✅ CTRAMP data model
- ✅ CTRAMP extended data model
- ⏳ Population synthesizer data model (pending)

**Benefits**:
- Single source of truth for data structures
- Easier to maintain and update schemas
- Automatic validation against known models

### 4. Shared Utilities and Code Reuse

**Principle**: Common operations are extracted into reusable utility functions.

**Implementation**:
- Create `summary_utils.py` (or similar) for shared functions
- Common operations include:
  - Binning continuous variables
  - Calculating weighted averages
  - Aggregating by geography or demographic groups
  - Applying standard filters

**Benefits**:
- Reduced code duplication
- Consistent behavior across summaries
- Easier testing and debugging
- Single place to fix bugs or add features

### 5. Multi-Environment Compatibility

**Principle**: Code should work with the tm2py environment when possible, with graceful fallbacks.

**Strategy**:
- **Primary**: Write code compatible with tm2py environment so it can live in tm2py
- **Fallback**: Create controller script that switches environments
  - Runs the model in tm2py environment
  - Switches to summary environment
  - Runs summaries
- **Current**: Code can remain in tm2py-utils during development

**Benefits**:
- Future integration with tm2py workflow
- Flexibility during development
- Clear migration path

### 6. Maintainability and Accessibility

**Principle**: Code should be easy to understand and maintain by a wide audience.

**Requirements**:
- Clear file organization - easy to find where to update code
- Comprehensive inline documentation
- Examples for adding new summaries
- Consistent patterns across all summary types
- Well-documented extension points

**Target Audience**:
- Transportation planners (light coding experience)
- Data analysts (moderate Python skills)
- Software developers (maintaining the system)

### 7. Flexible Data Sources

**Principle**: Summaries should work with both model outputs and external data sources.

**Data Source Types**:
- **Model Outputs**: CTRAMP household/person/tour/trip data
- **Survey Data**: Household travel surveys formatted to match model output structure
- **External Data**: ACS, CTPP - match format of system outputs for calibration/validation

**Implementation**:
- Command-line option to specify data source type
- Adapters to normalize different input formats
- Common output format regardless of input source

### 8. Output Standardization

**Principle**: All outputs follow consistent format for downstream integration.

**Standards**:
- **Format**: CSV tables labeled with model run identifier
- **Combinability**: CSV tables can be combined across model runs
- **Visualization Ready**: Outputs designed for external visualization systems (Tableau, etc.)
- **Metadata**: Include run information, timestamps, configuration used

**File Naming**: `{summary_type}_{model_run_id}_{timestamp}.csv`

## System Architecture Idea Needs More Thinking Before we implement

### Component Organization

```
tm2py (upstream dependency)
├── data_models/
│   ├── ctramp_data_model.py
│   ├── ctramp_extended_data_model.py
│   └── population_synthesizer_data_model.py
└── (other tm2py components)

tm2py-utils (summary system)
├── summary/
│   ├── core_summaries/        # Always-run summaries
│   ├── validation/             # Validation code being developed
│   ├── summary_utils.py        # Shared utility functions
│   ├── data_readers.py         # Import and validation
│   ├── summary_base.py         # Base classes
│   └── output_writers.py       # Standardized output
└── config/
    └── {scenario}/scenario_config.toml
```

### Core Components

#### 1. Data Readers
- **Purpose**: Load and validate model outputs and external data
- **Design**: Abstract base class with implementations for different sources
- **Key Features**: 
  - Automatic iteration detection
  - Schema validation against tm2py data models
  - Support for CTRAMP outputs, survey data, ACS/CTPP
  - Error handling with clear messages

#### 2. Summary Utilities (`summary_utils.py`)
- **Purpose**: Shared functions used across all summary types
- **Functions**:
  - Bin continuous variables (distance, time, etc.)
  - Calculate weighted averages
  - Aggregate by geography/demographics
  - Apply standard filters
  - Format output tables
- **Design**: Pure functions, well-tested, documented

#### 3. Summary Generators
- **Purpose**: Transform raw data into validation summaries
- **Design**: 
  - Base class defining standard interface
  - Plugin-based registry for different summary types
  - Tier-based execution (always-run vs. configurable)
- **Types**:
  - Core Summaries (always executed)
  - RTP Metrics (configurable)
  - TIP Metrics (configurable)
  - Calibration Summaries (configurable)

#### 4. Configuration System
- **Purpose**: Control which summaries run and with what parameters
- **Design**: TOML-based with scenario-specific overrides
- **Key Elements**:
  - `final_components`: Array of summaries to execute
  - Summary-specific parameters
  - Data source specifications
  - Output locations

#### 5. Output Writers
- **Purpose**: Standardize output format across all summaries
- **Design**: Consistent CSV format with metadata
- **Features**: 
  - Model run labeling
  - Timestamp inclusion
  - Ready for cross-run comparison
  - Visualization system compatibility

### Data Flow

```
┌─────────────────────────────────────────────┐
│  Data Sources                                │
│  ├── CTRAMP Outputs                         │
│  ├── Survey Data                            │
│  └── External Data (ACS, CTPP)              │
└──────────────────┬──────────────────────────┘
                   ↓
           ┌───────────────┐
           │ Data Readers  │ ← tm2py Data Models
           └───────┬───────┘
                   ↓
           ┌───────────────┐
           │ Data Validation│
           └───────┬───────┘
                   ↓
      ┌────────────────────────┐
      │  Summary Selection     │ ← scenario_config.toml
      │  (final_components)    │
      └────────┬───────────────┘
               ↓
    ┌──────────────────────┐
    │  Always-Run Tier     │
    │  (Core Summaries)    │
## Open Questions

These questions need resolution to finalize the design:

### Integration Strategy
- **Q**: How can we combine the `core_summaries` code and the `validation` code we started?
- **Consideration**: Lisa says this is a trivial problem - what's the simplest merge strategy?
- **Next Step**: Map existing functionality and identify overlaps

### Configuration Boundaries
- **Q**: What is configurable via scenario_config and what is always run?
- **Current Thinking**: Core summaries always run, others are configurable
- **Need to Define**: Exact list of core vs. configurable summaries

### Enriched Output
- **Q**: Should CTRAMP write out parking costs and skims as enriched outputs?
- **Consideration**: Makes data available for special analyses
- **Trade-off**: Larger output files vs. easier analysis
- **Next Step**: Define enriched output schema and opt-in mechanism

### Visualization Integration
- **Q**: How do we build the comparison/visualization system?
- **Current Thinking**: Tableau as preferred platform
- **Ownership**: Melody to take lead on Tableau integration
- **Requirement**: Balance automation with transparency
- **Challenge**: Avoid opaque pipeline, maintain auditability

### Population Synthesizer Integration
- **Q**: How do we add data models from the population synthesizer?
- **Status**: Needs implementation
- **Location**: Should live in tm2py data models folder
- **Next Step**: Define PopSyn output schema

### Environment Management
- **Q**: Can we make everything work in tm2py environment?
- **Fallback**: Controller script that switches environments
- **Current**: Code lives in tm2py-utils
- **Decision Needed**: Timeline for tm2py integration

## Implementation Roadmap

### Phase 1: Foundation (Current)
- ✅ Document design principles
- ⏳ Merge core_summaries and validation code
- ⏳ Create `summary_utils.py` with shared functions
- ⏳ Establish summary tier system
- ⏳ Import tm2py data models

### Phase 2: Core Functionality
- ⏳ Implement always-run core summaries
- ⏳ Build configurable summary selection
- ⏳ Add command-line options for different data sources
- ⏳ Standardize CSV output format
- ⏳ Create scenario_config templates

### Phase 3: Extended Capabilities
- ⏳ Support for survey data inputs
- ⏳ ACS/CTPP format matching
- ⏳ Enriched output options
- ⏳ Multi-run comparison utilities
- ⏳ Population synthesizer integration

### Phase 4: Integration & Deployment
- ⏳ Tableau visualization templates
- ⏳ Controller script for environment switching
- ⏳ Migration to tm2py environment
- ⏳ Full documentation and examples
- ⏳ User training and rollout

## Next Steps

### Immediate Actions
1. **Code Consolidation**: Merge core_summaries and validation code paths
2. **Shared Utilities**: Extract common functions to `summary_utils.py`
3. **Data Model Import**: Set up imports from tm2py data models
4. **Tier Definition**: Finalize which summaries are always-run vs. configurable

### Short-Term Goals
1. **Configuration System**: Implement `final_components` array processing
2. **Output Standardization**: Ensure all summaries produce compatible CSV format
3. **Documentation**: Create examples for adding new summaries
4. **Testing**: Build test suite for shared utilities

### Medium-Term Goals
1. **Survey Data Support**: Implement adapters for household survey data
2. **Visualization Prototype**: Work with Melody on Tableau integration
3. **Enriched Outputs**: Define and implement optional enriched output schema
4. **PopSyn Integration**: Add population synthesizer data model support

## Version History

| Version | Date | Major Changes |
|---------|------|---------------|
| 0.2 | Dec 2025 | Reorganized with principles from team discussion, added open questions and roadmap |
| 0.1 | Dec 2025 | Initial design system documentation |

## References

- [Generate Summaries Guide](generate-summaries.md)
- [Custom Summaries](custom-summaries.md)
- [Configuration](configuration.md)
- [Data Model](data-model.md)
- [How to Summarize](../summary/validation/HOW_TO_SUMMARIZE.md)
- Summary output files: `{summary_name}_{scenario_id}.csv`
- Configuration files: `{purpose}_config.toml`
- Example: `auto_ownership_2015_base.csv`, `scenario_config.toml`

### Column Naming
- Lowercase with underscores: `tour_mode`, `trip_distance`
- Categorical suffixes: `_cat` for categories, `_grp` for groups
- Count columns: `n_*` prefix (e.g., `n_tours`, `n_trips`)
- Share columns: `share_*` prefix or `*_pct` suffix

### Code Naming
- Classes: PascalCase (e.g., `TourModeSummary`)
- Functions: snake_case (e.g., `calculate_mode_share`)
- Constants: UPPER_SNAKE_CASE (e.g., `DEFAULT_ITERATION`)

## Extension Points

### Adding New Summaries

1. Create summary class inheriting from `BaseSummary`
2. Implement required methods: `load_data()`, `calculate()`, `format_output()`
3. Register in summary registry
4. Add configuration template
5. Update documentation

### Custom Aggregations

1. Define aggregation function with standard signature
2. Add to aggregation registry
3. Reference in configuration files
4. Document in custom summaries guide

### New Data Sources

1. Create reader class inheriting from `BaseDataReader`
2. Implement schema validation
3. Add to data source registry
4. Update data model documentation

## Quality Standards

### Code Quality
- Type hints for all function signatures
- Docstrings following NumPy style
- Unit test coverage > 80%
- Linting with flake8/black

### Documentation Quality
- Every summary has usage examples
- Configuration options fully documented
- Troubleshooting guide for common errors
- Changelog maintained for breaking changes

### Performance Benchmarks
- Process 1M household records in < 2 minutes
- Memory usage < 4GB for typical regional model
- Individual summaries complete in < 30 seconds

## Future Directions

### Near-Term Enhancements
- Parallel processing for multiple summaries
- Interactive visualization dashboard
- Automated comparison with observed data
- Summary templates for common validation tasks

### Long-Term Vision
- Real-time validation during model runs
- Machine learning-based anomaly detection
- Integration with calibration workflows
- Web-based validation report generator

## Version History

| Version | Date | Major Changes |
|---------|------|---------------|
| 0.1 | TBD | Initial design system documentation |

## References

- [Generate Summaries Guide](generate-summaries.md)
- [Custom Summaries](custom-summaries.md)
- [Configuration](configuration.md)
- [Data Model](data-model.md)
