"""
Update CIK-to-SIC mapping with comprehensive industry lookup
"""

import pandas as pd

# Read the current mapping and new lookup
mapping = pd.read_csv('data/sec/external/cik_to_sic_mapping.csv')
sic_lookup = pd.read_csv('data/sec/external/sic_industry_names.csv')

print(f'Current mapping rows: {len(mapping)}')
print(f'SIC lookup rows: {len(sic_lookup)}')
print(f'Unique SICs in mapping: {mapping["sic"].nunique()}')

# Merge with updated lookup, dropping old columns
mapping = mapping[['cik', 'name', 'sic']].drop_duplicates()
enriched = mapping.merge(sic_lookup[['sic', 'sic_description', 'sector_name', 'sic_2digit']], on='sic', how='left')

# Check for unmapped
unmapped = enriched[enriched['sic_description'].isna()]
print(f'Unmapped SICs: {len(unmapped)}')
if len(unmapped) > 0:
    print(f'Unique unmapped codes: {unmapped["sic"].nunique()}')
    print('Sample unmapped:', unmapped['sic'].unique()[:10])

# Fill unmapped
enriched['sic'] = enriched['sic'].astype(str)
enriched['sector_name'] = enriched['sector_name'].fillna('Other')
enriched['sic_description'] = enriched['sic_description'].fillna('Unclassified - ' + enriched['sic'])
enriched['sic_2digit'] = enriched['sic_2digit'].fillna(enriched['sic'].str[:2])

enriched = enriched.sort_values('cik')
enriched.to_csv('data/sec/external/cik_to_sic_mapping.csv', index=False)

print(f'\n✅ Updated CIK-to-SIC mapping saved')
print(f'Rows: {len(enriched)}')
print(f'Columns: {list(enriched.columns)}')
print(f'\nSector distribution:')
print(enriched['sector_name'].value_counts().to_string())
