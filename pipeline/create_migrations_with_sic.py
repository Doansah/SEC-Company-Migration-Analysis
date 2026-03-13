"""
Create migrations with SIC enrichment (Goal 2 Extended Output)
Merges v1 all_hq_migrations_filtered.xlsx with SIC metadata
Output: 02_migrations_detailed.xlsx
"""

import pandas as pd
import os

# Paths
v1_migrations = "archive/v1_outputs/all_hq_migrations_filtered.xlsx"
sic_mapping = "data/sec/external/cik_to_sic_mapping.csv"
output_file = "analysis/v2_outputs/02_migrations_detailed.xlsx"

# Read data
print("Reading v1 migrations...")
migrations = pd.read_excel(v1_migrations)
print(f"Migrations shape: {migrations.shape}")
print(f"Migrations columns: {migrations.columns.tolist()}")

print("\nReading SIC mapping...")
sic_map = pd.read_csv(sic_mapping)

# Merge on CIK
print("\nMerging migrations with SIC mapping...")
enriched = migrations.merge(
    sic_map[["cik", "sic", "sic_description", "sector_name"]],
    left_on="CIK",
    right_on="cik",
    how="left"
)

# Check match rate
matched = enriched["sic"].notna().sum()
total = len(enriched)
print(f"SIC match rate: {matched}/{total} ({100*matched/total:.1f}%)")

# Reorder columns
cols = ["CIK", "Company", "Move_Year"]
location_cols = [c for c in migrations.columns if c not in cols + ["CIK"]]
sic_cols = ["sic", "sic_description", "sector_name"]
enriched = enriched[cols + location_cols + sic_cols]

# Drop redundant cik column if present
if "cik" in enriched.columns:
    enriched = enriched.drop(columns=["cik"])

# Sort by CIK, Move_Year
enriched = enriched.sort_values(["CIK", "Move_Year"])

# Create output directory if needed
os.makedirs("analysis/v2_outputs", exist_ok=True)

# Write to Excel
print(f"\nWriting to {output_file}...")
enriched.to_excel(output_file, index=False, engine="openpyxl")
print(f"✓ Successfully created {output_file}")
print(f"  Shape: {enriched.shape}")
print(f"  Columns: {enriched.columns.tolist()}")

# Show sample of migrations by sector
print("\nTop migration industries (by count):")
sector_counts = enriched["sector_name"].value_counts().head(10)
for sector, count in sector_counts.items():
    print(f"  {sector}: {count}")
