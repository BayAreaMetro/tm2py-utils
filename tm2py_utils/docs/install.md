# Installation Guide

## Prerequisites

- **Python**: 3.9 or higher
- **Conda**: Anaconda or Miniconda
- **Git**: For cloning the repository

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/BayAreaMetro/tm2py-utils.git
cd tm2py-utils
```

### 2. Create Conda Environment

```bash
# Create environment from environment.yml (if available)
conda env create -f environment.yml

# Or create manually
conda create -n tm2py-utils python=3.9 pandas numpy pyyaml
conda activate tm2py-utils
```

### 3. Install Dependencies

```bash
# Install required packages
pip install -r requirements.txt
```

### 4. Install tm2py-utils

```bash
# Install in development mode
pip install -e .
```

## Verifying Installation

Test that the installation works:

```bash
# Check package is importable
python -c "import tm2py_utils; print('tm2py-utils installed successfully!')"

# List available summaries
cd tm2py_utils/summary/validation
python list_summaries.py
```

## Optional: Set Up Data Paths

Edit `tm2py_utils/summary/validation/validation_config.yaml` to point to your model output directories:

```yaml
input_directories:
  - path: "E:\\model_runs\\2023-tm22-dev-version-05\\ctramp_output"
    name: "2023_version_05"
    display_name: "2023 TM2.2 v05"
```

## Troubleshooting

### Import Errors

If you get `ModuleNotFoundError`, ensure you've activated the conda environment:

```bash
conda activate tm2py-utils
```

### Permission Errors

On Windows, you may need to run PowerShell as Administrator for some operations.

## Next Steps

- [Generate Summaries](generate-summaries.md) - Run the summarizer
- [Summaries Reference](summaries.md) - List of available summaries
- [Configuration](configuration.md) - YAML data model documentation
