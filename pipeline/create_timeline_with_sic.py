"""
Create timeline with SIC enrichment (Goal 2 Final Output)
Merges v1 company_hq_timeline_filtered.xlsx with SIC metadata
Output: 01_timeline_with_sic.xlsx
"""

import pandas as pd
import os

# Paths
v1_timeline = "archive/v1_outputs/company_hq_timeline_filtered.xlsx"
sic_mapping = "data/sec/external/cik_to_sic_mapping.csv"
output_file = "analysis/v2_outputs/01_timeline_with_sic.xlsx"

# Read data
print("Reading v1 timeline...")
timeline = pd.read_excel(v1_timeline)
print(f"Timeline shape: {timeline.shape}")
print(f"Timeline columns: {timeline.columns.tolist()}")

print("\nReading SIC mapping...")
sic_map = pd.read_csv(sic_mapping)
print(f"SIC mapping shape: {sic_map.shape}")
print(f"SIC mapping columns: {sic_map.columns.tolist()}")

# Merge on CIK
print("\nMerging timeline with SIC mapping...")
enriched = timeline.merge(
    sic_map[["cik", "sic", "sic_description", "sector_name"]],
    left_on="CIK",
    right_on="cik",
    how="left"
)

# Check match rate
matched = enriched["sic"].notna().sum()
total = len(enriched)
print(f"SIC match rate: {matched}/{total} ({100*matched/total:.1f}%)")

# Reorder columns for clarity
cols = ["CIK", "Company", "Year", "City", "State"]
sic_cols = ["sic", "sic_description", "sector_name"]
remaining = [c for c in enriched.columns if c not in cols + sic_cols + ["cik"]]
enriched = enriched[cols + sic_cols + remaining]

# Drop redundant cik column if present
if "cik" in enriched.columns:
    enriched = enriched.drop(columns=["cik"])

# Sort by CIK, Year
enriched = enriched.sort_values(["CIK", "Year"])

# Create output directory if needed
os.makedirs("analysis/v2_outputs", exist_ok=True)

# Write to Excel
print(f"\nWriting to {output_file}...")
enriched.to_excel(output_file, index=False, engine="openpyxl")
print(f"✓ Successfully created {output_file}")
print(f"  Shape: {enriched.shape}")
print(f"  Columns: {enriched.columns.tolist()}")
