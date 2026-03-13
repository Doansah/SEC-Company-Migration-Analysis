"""
Identify companies that departed Maryland (for Goal 3 & 4)
Analyzes which companies left when, and where they went
Output: departed_companies_summary.xlsx
"""

import pandas as pd
import numpy as np
import os

# Paths
timeline_sic = "analysis/v2_outputs/01_timeline_with_sic.xlsx"
migrations = "analysis/v2_outputs/02_migrations_detailed.xlsx"
output_file = "analysis/v2_outputs/departed_companies_analysis.xlsx"

# Read data
print("Reading enriched timeline and migrations...")
timeline = pd.read_excel(timeline_sic)
mig = pd.read_excel(migrations)

# Timeline: Get Maryland records (State == 'MD')
print(f"Total timeline records: {len(timeline)}")
md_records = timeline[timeline["State"] == "MD"].copy()
print(f"Maryland-based records: {len(md_records)}")

# Find last Maryland year for each company
md_last_year = md_records.groupby("CIK")["Year"].max().reset_index()
md_last_year.columns = ["CIK", "last_md_year"]

# Find first non-Maryland year for each company (if any)
non_md_records = timeline[timeline["State"] != "MD"].copy()
non_md_first_year = non_md_records.groupby("CIK")["Year"].min().reset_index()
non_md_first_year.columns = ["CIK", "first_non_md_year"]

# Merge to find companies that left Maryland
left_md = md_last_year.merge(non_md_first_year, on="CIK", how="inner")
left_md = left_md[left_md["first_non_md_year"] > left_md["last_md_year"]].copy()
left_md["departure_year"] = left_md["first_non_md_year"]

print(f"\nCompanies that departed Maryland: {len(left_md)}")

# Get additional info about departing companies
departed_ciks = left_md["CIK"].unique()
departed_info = timeline[timeline["CIK"].isin(departed_ciks)].copy()

# For each departed company, get: last MD location, first post-MD location, SIC
# Last Maryland location
md_last = departed_info[departed_info["State"] == "MD"].sort_values(["CIK", "Year"])
md_last = md_last.groupby("CIK").tail(1)
md_last = md_last[["CIK", "Company", "Year", "City", "State", "sector_name"]].copy()
md_last.columns = ["CIK", "Company", "last_md_year", "last_md_city", "last_md_state", "sector"]

# First post-MD location
non_md_first = departed_info[departed_info["State"] != "MD"].sort_values(["CIK", "Year"])
non_md_first = non_md_first.groupby("CIK").head(1)
non_md_first = non_md_first[["CIK", "Year", "City", "State"]].copy()
non_md_first.columns = ["CIK", "departure_year", "first_new_city", "first_new_state"]

# Combine
departed_summary = md_last.merge(non_md_first, on="CIK", how="left")
departed_summary = departed_summary.sort_values("last_md_year", ascending=False)

# Create output directory if needed
os.makedirs("analysis/v2_outputs", exist_ok=True)

# Write to Excel
print(f"\nWriting to {output_file}...")
departed_summary.to_excel(output_file, index=False, engine="openpyxl")
print(f"✓ Successfully created {output_file}")
print(f"  Shape: {departed_summary.shape}")
print(f"  Columns: {departed_summary.columns.tolist()}")

# Summary statistics
print("\n--- Departure Analysis ---")
print(f"Total companies that departed MD: {len(departed_summary)}")
print(f"\nTop sectors of departed companies:")
sector_counts = departed_summary["sector"].value_counts().head(10)
for sector, count in sector_counts.items():
    print(f"  {sector}: {count}")

print(f"\nDeparture timeline (companies by year they left):")
depart_by_year = departed_summary["last_md_year"].value_counts().sort_index(ascending=False).head(10)
for year, count in depart_by_year.items():
    print(f"  {year}: {count} companies")

print(f"\nTop destination states:")
dest_counts = departed_summary["first_new_state"].value_counts().head(10)
for state, count in dest_counts.items():
    print(f"  {state}: {count}")

print(f"\nFirst 5 departed companies:")
print(departed_summary[["Company", "last_md_year", "sector", "first_new_state"]].head())
