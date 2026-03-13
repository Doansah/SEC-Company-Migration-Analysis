import pandas as pd
import os

# Read all dataset sources
timeline = pd.read_excel('analysis/v2_outputs/01_timeline_with_sic.xlsx')
migrations = pd.read_excel('analysis/v2_outputs/02_migrations_detailed.xlsx')
candidates = pd.read_excel('analysis/v2_outputs/attrition_analysis/01_attrition_candidates.xlsx')
classified = pd.read_excel('analysis/v2_outputs/attrition_analysis/03_attrition_classification.xlsx')

print('Consolidating departure data...')

# Create summary by classification type
departures_by_type = []

# 1. CONFIRMED RELOCATIONS from migration data
relocations = migrations[migrations['From_State'] == 'MD'].copy()
for idx, row in relocations.iterrows():
    dest = row['To_State']
    year = int(row['Move_Year'])
    departures_by_type.append({
        'Departure_Type': 'RELOCATION',
        'CIK': row['CIK'],
        'Company': row['Company'],
        'Sector': row['sector_name'],
        'Last_MD_Year': year,
        'Destination_State': dest,
        'Status': 'RELOCATED',
        'Years_Missing': 2025 - year,
        'Notes': 'Moved to ' + str(dest) + ' in ' + str(year)
    })

# 2. TRUE ATTRITIONS (from classified)
attritions = classified[classified['Classification'].isin(['ESTABLISHED_ATTRITION', 'RECENT_ATTRITION'])]
for idx, row in attritions.iterrows():
    departures_by_type.append({
        'Departure_Type': 'ATTRITION',
        'CIK': row['CIK'],
        'Company': row['Company'],
        'Sector': row['Sector'],
        'Last_MD_Year': int(row['Last_MD_Year']),
        'Destination_State': None,
        'Status': row['Classification'],
        'Years_Missing': row['Years_Missing'],
        'Notes': row['Note']
    })

# Convert to DataFrame
departures_consolidated = pd.DataFrame(departures_by_type)
departures_consolidated = departures_consolidated.sort_values(['Last_MD_Year', 'Departure_Type'], ascending=[False, True])

print('Total departures consolidated: ' + str(len(departures_consolidated)))

# Get Maryland companies for context
md_companies = timeline[timeline['State'] == 'MD'].copy()
md_ciks_ever = md_companies['CIK'].unique()
total_md_companies_ever = len(md_ciks_ever)

# Arrivals data
arrivals = migrations[migrations['To_State'] == 'MD'].copy()

print('Relocations: ' + str(len(departures_consolidated[departures_consolidated['Departure_Type'] == 'RELOCATION'])))
print('Attritions: ' + str(len(departures_consolidated[departures_consolidated['Departure_Type'] == 'ATTRITION'])))

# Write comprehensive Excel
output_file = 'analysis/v2_outputs/MARYLAND_DEPARTURES_CONSOLIDATED.xlsx'
print('Writing consolidated summary to ' + output_file + '...')

with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    departures_consolidated.to_excel(writer, sheet_name='All_Departures', index=False)
    
    # Add summary sheet
    summary_stats = pd.DataFrame({
        'Metric': [
            'Total Companies Ever in Maryland',
            'Companies that Departed',
            'Relocations (moved to other state)',
            'Attritions (closed/went private)',
            'Established Attrition (3+ years)',
            'Recent Attrition (1-2 years)',
            'Companies that Arrived',
            'Net Migration (Arrivals - Relocations)',
            'Net Change (Arrivals - All Departures)'
        ],
        'Count': [
            total_md_companies_ever,
            len(departures_consolidated),
            len(departures_consolidated[departures_consolidated['Departure_Type'] == 'RELOCATION']),
            len(departures_consolidated[departures_consolidated['Departure_Type'] == 'ATTRITION']),
            len(attritions[attritions['Classification'] == 'ESTABLISHED_ATTRITION']),
            len(attritions[attritions['Classification'] == 'RECENT_ATTRITION']),
            len(arrivals),
            len(arrivals) - len(relocations),
            len(arrivals) - len(departures_consolidated)
        ]
    })
    summary_stats.to_excel(writer, sheet_name='Summary', index=False)
    
    # Relocations only
    reloc_only = departures_consolidated[departures_consolidated['Departure_Type'] == 'RELOCATION']
    reloc_only.to_excel(writer, sheet_name='Relocations_Only', index=False)
    
    # Attritions only
    attr_only = departures_consolidated[departures_consolidated['Departure_Type'] == 'ATTRITION']
    attr_only.to_excel(writer, sheet_name='Attritions_Only', index=False)
    
    # Sector analysis
    sector_summary = departures_consolidated.groupby(['Sector', 'Departure_Type']).size().unstack(fill_value=0)
    sector_summary.to_excel(writer, sheet_name='By_Sector')
    
    # Timeline analysis
    timeline_summary = departures_consolidated.groupby(['Last_MD_Year', 'Departure_Type']).size().unstack(fill_value=0)
    timeline_summary.to_excel(writer, sheet_name='By_Year')

print('Success! Consolidated file: ' + output_file)
