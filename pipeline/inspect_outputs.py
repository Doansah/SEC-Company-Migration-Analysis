import pandas as pd

print('=== TIMELINE FILE ===')
df1 = pd.read_excel('company_hq_timeline_filtered.xlsx')
print(f'Shape: {df1.shape}')
print(f'Columns: {list(df1.columns)}')
print(f'Data types:\n{df1.dtypes}')
print(f'\nFirst 5 rows:\n{df1.head()}')
print(f'\nYear range: {df1["Year"].min()} to {df1["Year"].max()}')
print()

print('=== MIGRATIONS ALL ===')
df2 = pd.read_excel('all_hq_migrations_filtered.xlsx')
print(f'Shape: {df2.shape}')
print(f'Columns: {list(df2.columns)}')
print(f'Data types:\n{df2.dtypes}')
print(f'\nFirst 5 rows:\n{df2.head()}')
print()

print('=== MIGRATIONS MD ===')
df3 = pd.read_excel('maryland_hq_migrations_filtered.xlsx')
print(f'Shape: {df3.shape}')
print(f'Columns: {list(df3.columns)}')
if len(df3) > 0:
    print(f'Data types:\n{df3.dtypes}')
    print(f'\nFirst 5 rows:\n{df3.head()}')
else:
    print('(No migrations to/from Maryland)')
