# tm2py-utils

**Utilities and analysis tools for Travel Model Two (TM2)**

## Overview

`tm2py-utils` provides a collection of utilities for working with Travel Model Two outputs, including:

- **Validation Dashboard** - Interactive web dashboard for model validation and scenario comparison
- **Summary Generation** - Automated summary statistics from CTRAMP model outputs
- **PopulationSim Integration** - Synthetic population analysis and validation
- **Network Analysis** - Tools for analyzing transportation networks

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/BayAreaMetro/tm2py-utils.git
cd tm2py-utils

# Create conda environment
conda env create -f environment.yml
conda activate tm2py_utils

# Install package
pip install -e .
```

See [Installation Guide](install.md) for detailed instructions.

### Running the Validation Dashboard

```bash
# Navigate to validation directory
cd tm2py_utils/summary/validation

# Generate summaries for a model run
python summarize_model_run.py "C:/path/to/ctramp_output"

# View summaries (use Excel, Python, R, or dashboard tools)
```

**📚 New to the validation system?** Check out:
- **[HOW_TO_SUMMARIZE.md](../summary/validation/HOW_TO_SUMMARIZE.md)** - Complete user guide
- **[README.md](../summary/validation/README.md)** - Toolkit overview  
- **[Summaries Guide](summaries.md)** - System documentation

## Key Features

### 📊 Validation Dashboard

Interactive web-based dashboard for comparing model runs and validating against observed data:

- **Population** - Synthetic population demographics (from PopulationSim)
- **Households** - Auto ownership patterns
- **Activity Patterns** - Daily activity patterns (CDAP)
- **Tours** - Tour frequency and mode choice
- **Trips** - Trip mode and purpose analysis
- **Journey to Work** - Commute patterns
- **Time of Day** - Temporal distribution of travel
- **Trip Characteristics** - Distance and travel time

### 📊 Summary Generation System

Simple, transparent tool for generating validation summaries from CTRAMP model outputs:

- **30 configured summaries** covering households, tours, trips, and activity patterns
- **Automatic validation** with built-in quality checks
- **Config-driven** - Add summaries by editing YAML, no Python coding
- **Fast** - Process full model run in ~10 minutes

```bash
# Generate all summaries for one model run
python summarize_model_run.py "C:/path/to/ctramp_output"

# Custom output location
python summarize_model_run.py "C:/path/to/ctramp_output" --output "my_results"

# Strict validation mode (treat warnings as errors)
python summarize_model_run.py "C:/path/to/ctramp_output" --strict
```

See [Summaries Guide](summaries.md) for complete documentation.

### 🏘️ PopulationSim Integration

Analysis tools for synthetic population outputs:

- Household demographics (size, income, workers)
- Person demographics (age distribution)
- Geographic distribution by county
- Validation against ACS data

## Documentation

- [Installation Guide](install.md)
- [Summaries User Guide](../summary/validation/HOW_TO_SUMMARIZE.md) - **Start here for generating summaries**
- [Summary System Documentation](summaries.md)
- [Toolkit README](../summary/validation/README.md)
- [Contributing](contributing.md)

## Architecture

```
tm2py_utils/
├── summary/
│   ├── validation/                        # NEW: Simple validation toolkit
│   │   ├── summarize_model_run.py        # Main tool - generates summaries
│   │   ├── validate_summaries.py         # Quality checker
│   │   ├── data_model/                   # Configuration files
│   │   │   ├── ctramp_data_model.yaml   # Summary definitions (edit here!)
│   │   │   └── variable_labels.yaml      # Display labels
│   │   ├── outputs/                      # Generated summary CSVs
│   │   ├── HOW_TO_SUMMARIZE.md          # User guide
│   │   ├── README.md                     # Toolkit overview
│   │   └── archived_validation_system/   # Old multi-dataset comparison system
│   └── core_summaries/                   # DEPRECATED (use validation/ instead)
├── inputs/                                # Input data preparation tools
├── requests/                              # Special analysis requests
└── docs/                                  # Documentation (this site)
```

## Related Projects

- [tm2py](https://github.com/BayAreaMetro/tm2py) - Main Travel Model Two implementation
- [PopulationSim](https://github.com/ActivitySim/PopulationSim) - Synthetic population generator
- [Bay Area UrbanSim](https://github.com/BayAreaMetro/bayarea_urbansim) - Land use model

## Support

- **Issues**: [GitHub Issues](https://github.com/BayAreaMetro/tm2py-utils/issues)
- **Discussions**: [GitHub Discussions](https://github.com/BayAreaMetro/tm2py-utils/discussions)
- **MTC Contact**: modeling@bayareametro.gov

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](https://github.com/BayAreaMetro/tm2py-utils/blob/main/LICENSE) file for details.
