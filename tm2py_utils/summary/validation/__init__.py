"""
Validation Summary Package

Modular summary generation functions organized by data level:
- household_summary: Auto ownership, household size, income distribution
- worker_summary: Work location, telecommuting, worker demographics  
- tour_summary: Tour frequency, mode choice, timing patterns
- trip_summary: Trip mode, purpose, distance, and generation patterns

Each module provides:
- Individual summary functions for specific analyses
- generate_all_*_summaries() function for complete analysis at that level
"""

from . import household_summary
from . import worker_summary
from . import tour_summary
from . import trip_summary

__all__ = [
    'household_summary',
    'worker_summary', 
    'tour_summary',
    'trip_summary',
]
