"""
Verify SIC enrichment of Maryland companies
"""

import pandas as pd

# Load the data files
cik_mapping = pd.read_csv('data/sec/external/cik_to_sic_mapping.csv')
sic_lookup = pd.read_csv('data/sec/external/sic_industry_names.csv')

# Check Maryland companies in archive
maryland_archive = pd.read_excel('archive/v1_analysis/maryland_ciks.xlsx', sheet_name=0, engine='openpyxl')
print('Maryland CIKs from archive:')
print(f'  Count: {len(maryland_archive)}')
print(f'  Columns: {list(maryland_archive.columns)}')

# Cross-reference with SIC mapping
maryland_with_sic = maryland_archive.merge(cik_mapping[['cik', 'sic', 'sic_description', 'sector_name']], 
                                            left_on='CIK', right_on='cik', how='left')

print(f'\nMaryland companies matched with SIC codes:')
print(f'  Total: {len(maryland_with_sic)}')
print(f'  With SIC match: {maryland_with_sic["sic"].notna().sum()}')
print(f'  Without SIC match: {maryland_with_sic["sic"].isna().sum()}')

print(f'\nTop 15 industries in Maryland (by company count):')
print(maryland_with_sic['sector_name'].value_counts().head(15).to_string())

print(f'\nSample Maryland companies with SIC classification:')
print(maryland_with_sic[['CIK', 'sector_name', 'sic_description']].drop_duplicates('CIK').head(20).to_string())
