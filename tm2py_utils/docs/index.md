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

# Launch dashboard
streamlit run dashboard/dashboard_app.py --server.port 8501
```

Or use the deployment script:

```bash
# Generate summaries and launch dashboard
python run_and_deploy_dashboard.py --config validation_config.yaml --launch-dashboard
```

View the live dashboard: [https://tm2-validation-dashboard.streamlit.app/](https://tm2-validation-dashboard.streamlit.app/)

**📚 New to the validation system?** Check out the **[Complete Validation System Guide](validation-system.md)** for step-by-step instructions on:
- Creating summaries from model runs
- Adding observed data (ACS, CTPP, surveys)
- Custom aggregations and binning
- Dashboard visualization
- Deployment options

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

### 🔧 Summary Generation

Config-driven system for generating model validation summaries:

- **Core Summaries** (21) - Essential analysis matching legacy outputs
- **Validation Summaries** (13) - Extended analysis for dashboard
- **Custom Summaries** - Easy to add via YAML configuration

```bash
# Generate all summaries
python -m tm2py_utils.summary.validation.summaries.run_all --config validation_config.yaml

# Generate only core summaries (fast)
# Edit validation_config.yaml: generate_summaries: "core"
python -m tm2py_utils.summary.validation.summaries.run_all --config validation_config.yaml
```

### 🏘️ PopulationSim Integration

Analysis tools for synthetic population outputs:

- Household demographics (size, income, workers)
- Person demographics (age distribution)
- Geographic distribution by county
- Validation against ACS data

## Documentation

- [Installation Guide](install.md)
- [Dashboard Guide](dashboard.md)
- [Summary System](summaries.md)
- [Contributing](contributing.md)
- [Consolidation Proposal](../summary/CONSOLIDATION_PROPOSAL.md) - Plan to consolidate summary systems

## Architecture

```
tm2py_utils/
├── summary/
│   ├── validation/              # Validation dashboard and summaries
│   │   ├── dashboard/           # Dashboard YAML configs and app
│   │   ├── summaries/           # Summary generation scripts
│   │   ├── data_model/          # Data model definitions
│   │   ├── outputs/             # Generated summary CSVs
│   │   └── validation_config.yaml
│   └── core_summaries/          # Legacy summary system (being deprecated)
├── inputs/                      # Input data preparation tools
├── requests/                    # Special analysis requests
└── docs/                        # Documentation (this site)
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
