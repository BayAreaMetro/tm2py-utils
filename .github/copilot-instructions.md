# Copilot Instructions for tm2py-utils

## Project Overview
- **tm2py-utils** provides utilities for post-processing, summarization, and analysis of outputs from the Travel Model Two (TM2) and ActivitySim models.
- This repo is **decoupled from the main model runner** ([tm2py](https://github.com/BayAreaMetro/tm2py)) to allow rapid utility development and avoid EMME dependencies.
- Utilities are organized by function: archiving, summary/validation, data conversion, and more.

## Key Components & Structure
- `tm2py_utils/cli.py`: Main CLI entry point. Subcommands (e.g., `archive`) are dispatched here.
- `tm2py_utils/misc/archive.py`: Implements model run archiving using 7-Zip. Uses `bin/7z.exe` (Windows-only).
- `tm2py_utils/summary/`: Core summary and validation system for CTRAMP/ActivitySim outputs. See `summary/README.md` for architecture and workflow details.
- `tm2py_utils/config/`: Example and scenario-specific TOML configs for model runs and summaries.
- `tm2py_utils/bin/`: Contains required binaries (e.g., 7z.exe).

## Developer Workflows
- **Environment**: Requires Python 3.11+. Use `conda` for environment management. Each subdir may have its own `requirements.txt`.
- **Build/Install**: Install dependencies with `pip install -r requirements.txt` at the root or subdir as needed.
- **CLI Usage**: Run utilities via the CLI, e.g., `python -m tm2py_utils.cli archive <model_dir> <archive_dir> [-n name]`.
- **Summary/Validation**: See `tm2py_utils/summary/README.md` for running validation suites and analysis scripts. Example:
  - `python -m tm2py_utils.summary.validation.run_all_validation_summaries --config my_config.yaml`
- **Testing**: Run `python test_summary_system.py` in `summary/` for validation system tests.

## Project Conventions
- **No EMME dependencies**: All EMME-dependent code belongs in `tm2py`, not here.
- **Config-driven**: Use TOML/YAML for scenario and analysis configuration. Avoid hardcoding paths/parameters.
- **Pydantic models**: Used for type-safe data validation in summary/validation scripts.
- **Directory structure**: Utilities and scripts are grouped by function and scenario. Each scenario/config is isolated in its own folder.
- **Windows-first**: Some utilities (e.g., archiving) require Windows binaries.

## Integration Points
- **ActivitySim**: Many summary/validation scripts expect ActivitySim outputs and config structures.
- **SimWrapper**: Optional integration for dashboarding/visualization in `summary/validation/simwrapper_demo.py`.

## Examples
- Archive a model run: `python -m tm2py_utils.cli archive path/to/model path/to/archive -n run_name`
- Run validation: `python -m tm2py_utils.summary.validation.run_all_validation_summaries --config config.yaml`

## References
- See `tm2py_utils/summary/README.md` for detailed summary/validation architecture and usage patterns.
- See `tm2py_utils/config/` for example configs.
- See `pyproject.toml` for dependencies and build info.

---

**Update this file if you add new major utilities, workflows, or conventions.**
