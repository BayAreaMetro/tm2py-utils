"""
Create comparison table for tour purposes between survey and model
"""
import pandas as pd

# Load data
survey = pd.read_csv('E:/processed_bats_tm1/summaries/tour_frequency_by_purpose.csv')
model = pd.read_csv('M:/Application/Model One/RTP2025/IncrementalProgress/2023_TM161_IPA_35/OUTPUT/summaries/tour_frequency_by_purpose.csv')

# Rename columns for clarity
survey = survey.rename(columns={'tours': 'survey_tours', 'share': 'survey_share'})
model = model.rename(columns={'tours': 'model_tours', 'share': 'model_share'})

# Merge on tour_purpose (outer join to see all purposes)
comparison = pd.merge(
    survey[['tour_purpose', 'survey_tours', 'survey_share']], 
    model[['tour_purpose', 'model_tours', 'model_share']], 
    on='tour_purpose', 
    how='outer'
)

# Fill NaN with 0
comparison = comparison.fillna(0)

# Calculate differences
comparison['share_diff'] = comparison['model_share'] - comparison['survey_share']
comparison['abs_share_diff'] = comparison['share_diff'].abs()

# Convert shares to percentages for display
comparison['survey_pct'] = (comparison['survey_share'] * 100).round(2)
comparison['model_pct'] = (comparison['model_share'] * 100).round(2)
comparison['diff_pct'] = (comparison['share_diff'] * 100).round(2)

# Sort by absolute difference (largest discrepancies first)
comparison = comparison.sort_values('abs_share_diff', ascending=False)

# Create display table
display = comparison[[
    'tour_purpose', 
    'survey_tours', 'survey_pct',
    'model_tours', 'model_pct',
    'diff_pct'
]].copy()

display.columns = [
    'Tour Purpose',
    'Survey Tours', 'Survey %',
    'Model Tours', 'Model %',
    'Difference %'
]

# Format numbers
display['Survey Tours'] = display['Survey Tours'].apply(lambda x: f"{int(x):,}" if x > 0 else "-")
display['Model Tours'] = display['Model Tours'].apply(lambda x: f"{int(x):,}" if x > 0 else "-")

print("\n" + "="*90)
print("TOUR PURPOSE COMPARISON: Survey vs Model")
print("="*90)
print(display.to_string(index=False))

print("\n" + "="*90)
print("SUMMARY STATISTICS")
print("="*90)
print(f"Survey Total Tours: {survey['survey_tours'].sum():,.0f}")
print(f"Model Total Tours: {model['model_tours'].sum():,.0f}")
print(f"\nPurposes only in Survey: {len(comparison[comparison['model_tours']==0])}")
print(f"Purposes only in Model: {len(comparison[comparison['survey_tours']==0])}")
print(f"Purposes in both: {len(comparison[(comparison['survey_tours']>0) & (comparison['model_tours']>0)])}")

print("\n" + "="*90)
print("LARGEST DISCREPANCIES (>5% difference)")
print("="*90)
large_diffs = comparison[comparison['abs_share_diff'] > 0.05][['tour_purpose', 'survey_pct', 'model_pct', 'diff_pct']]
print(large_diffs.to_string(index=False))

# Save to CSV
output_path = 'E:/processed_bats_tm1/tour_purpose_comparison.csv'
comparison.to_csv(output_path, index=False)
print(f"\n✓ Full comparison saved to: {output_path}")
