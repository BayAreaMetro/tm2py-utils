"""
TM2.2 Validation System

Organized validation framework for comparing multiple TM2.2 model runs.

Structure:
- summaries/: Summary generation code
- data_model/: Data model configuration and column mappings
- dashboard/: Interactive Streamlit dashboard
- outputs/: Generated summary files and dashboard data
"""

__all__ = [
    'household_summary',
    'worker_summary', 
    'tour_summary',
    'trip_summary',
]
