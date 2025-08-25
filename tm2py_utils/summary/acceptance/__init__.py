"""Acceptance criteria module for tm2py model validation.

This module provides functionality to compare simulated model outputs against observed
data and acceptance criteria thresholds. It is used to validate Transportation Model 2
(TM2) runs against real-world observations and established performance standards.

The module consists of four main components:
- Acceptance: Main orchestrator class that coordinates comparisons between simulated and observed data
- Canonical: Handles canonical naming conventions and crosswalk mappings between different data sources
- Observed: Manages observed data from various sources (PeMS, transit surveys, census, etc.)
- Simulated: Processes simulated model outputs from tm2py runs

Example:
    >>> from tm2py_utils.summary.acceptance import Acceptance, Canonical, Observed, Simulated
    >>> 
    >>> # Initialize components
    >>> canonical = Canonical(canonical_file="config/canonical.toml", scenario_file="config/scenario.toml")
    >>> observed = Observed(canonical, observed_file="config/observed.toml")
    >>> simulated = Simulated(canonical, scenario_file="config/scenario.toml", model_file="config/model.toml")
    >>> 
    >>> # Create acceptance criteria comparisons
    >>> acceptance = Acceptance(canonical, simulated, observed, output_file_root="output/acceptance")
    >>> acceptance.make_acceptance(make_transit=True, make_roadway=True, make_other=True)

The module outputs GeoJSON files suitable for visualization in Tableau or other GIS tools,
containing comparisons between observed and simulated metrics with acceptance thresholds.
"""