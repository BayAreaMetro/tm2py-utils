import pandas as pd

# Check current tour mode data
tour_mode = pd.read_csv('tm2py_utils/summary/validation/outputs/dashboard/tour_mode_choice.csv')
print('Current tour modes:')
print(tour_mode['tour_mode_name'].unique())
print(f'Total modes: {len(tour_mode["tour_mode_name"].unique())}')
print()

# Check if aggregated version exists
try:
    tour_agg = pd.read_csv('tm2py_utils/summary/validation/outputs/dashboard/tour_mode_choice_aggregated.csv')
    print('Aggregated tour modes:')
    print(tour_agg['tour_mode_name'].unique())
    print(f'Aggregated modes: {len(tour_agg["tour_mode_name"].unique())}')
    print()
except Exception as e:
    print('No aggregated tour mode file found:', e)

# Check trip modes too
try:
    trip_mode = pd.read_csv('tm2py_utils/summary/validation/outputs/dashboard/trip_mode_choice.csv')
    print('Current trip modes:')
    print(trip_mode['trip_mode_name'].unique())
    print(f'Total modes: {len(trip_mode["trip_mode_name"].unique())}')
    print()
    
    trip_agg = pd.read_csv('tm2py_utils/summary/validation/outputs/dashboard/trip_mode_choice_aggregated.csv')
    print('Aggregated trip modes:')
    print(trip_agg['trip_mode_name'].unique())
    print(f'Aggregated modes: {len(trip_agg["trip_mode_name"].unique())}')
except Exception as e:
    print('Trip mode check failed:', e)