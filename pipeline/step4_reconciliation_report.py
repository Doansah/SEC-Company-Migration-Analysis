import pandas as pd
import os

# Paths
classification_file = "analysis/v2_outputs/attrition_analysis/03_attrition_classification.xlsx"
output_file = "analysis/v2_outputs/attrition_analysis/04_final_attrition_reconciliation.xlsx"

# Read data
classified = pd.read_excel(classification_file)

# Group by classification
true_relocations = classified[classified['Classification'] == 'RELOCATED']
recent_disappearance = classified[classified['Classification'] == 'RECENT_DISAPPEARANCE']
established = classified[classified['Classification'] == 'ESTABLISHED_ATTRITION']
recent_attrition = classified[classified['Classification'] == 'RECENT_ATTRITION']
unclear = classified[classified['Classification'] == 'UNCLEAR_MIGRATION']

# Create summary
summary_data = {
    'Category': [
        'True Relocations (moved to other state)',
        'True Attrition - Established (3+ years)',
        'True Attrition - Recent (1-2 years)',
        'Data Lag (2025 disappearances)',
        'Unclear Status (possible arrivals)'
    ],
    'Count': [
        len(true_relocations),
        len(established),
        len(recent_attrition),
        len(recent_disappearance),
        len(unclear)
    ]
}

summary_df = pd.DataFrame(summary_data)

print("Writing to Excel...")
with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    summary_df.to_excel(writer, sheet_name='Summary', index=False)
    classified.to_excel(writer, sheet_name='Detailed', index=False)

print(f"Success! File created: {output_file}")
