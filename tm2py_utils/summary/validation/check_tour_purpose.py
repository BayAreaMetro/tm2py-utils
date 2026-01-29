"""
Quick independent verification of tour frequency by purpose.
Reads the survey data directly and calculates tour counts by purpose.
"""
import pandas as pd
from pathlib import Path

# Survey data location
survey_dir = Path(r"C:\GitHub\travel-diary-survey-tools\projects\bats_2023\output\ctramp")

# Load tours data
tours_file = survey_dir / "indivTourData.csv"
if not tours_file.exists():
    print(f"Error: Tours file not found at {tours_file}")
    exit(1)

print("=" * 80)
print("Independent Tour Purpose Frequency Analysis")
print("=" * 80)
print(f"Source: {tours_file}")
print()

# Read tours
tours = pd.read_csv(tours_file)

print(f"Total tours: {len(tours):,}")
print(f"Columns: {', '.join(tours.columns.tolist())}")
print()

# Check for tour_purpose column
if 'tour_purpose' not in tours.columns:
    print("ERROR: 'tour_purpose' column not found!")
    print(f"Available columns: {tours.columns.tolist()}")
    exit(1)

# Calculate tour counts by purpose
print("=" * 80)
print("Tour Counts by Purpose")
print("=" * 80)

tour_purpose_counts = tours['tour_purpose'].value_counts().sort_index()

# Create summary table
summary = pd.DataFrame({
    'tour_purpose': tour_purpose_counts.index,
    'tours': tour_purpose_counts.values,
    'share': (tour_purpose_counts.values / tour_purpose_counts.sum() * 100).round(1)
})

# Sort by tour count descending
summary = summary.sort_values('tours', ascending=False)

print(summary.to_string(index=False))
print()

# Total
print(f"Total: {summary['tours'].sum():,} tours")
print()

# Show unique values and any unexpected codes
print("=" * 80)
print("Unique Tour Purpose Values")
print("=" * 80)
unique_purposes = sorted(tours['tour_purpose'].unique())
print(f"Count: {len(unique_purposes)}")
print(f"Values: {unique_purposes}")
print()

# Check for nulls or unexpected values
null_count = tours['tour_purpose'].isnull().sum()
if null_count > 0:
    print(f"WARNING: {null_count:,} tours with null purpose")
print()

# Save summary to CSV
output_file = survey_dir / "validation" / "tour_purpose_independent_check.csv"
summary.to_csv(output_file, index=False)
print(f"Summary saved to: {output_file}")
