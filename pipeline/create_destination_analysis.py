"""
Destination analysis of Maryland corporate relocations (Goal 4 Part 2)
Analyzes where Maryland companies relocate to
Output: 05_destination_analysis.xlsx
"""

import pandas as pd
import os

# Paths
timeline_sic = "analysis/v2_outputs/01_timeline_with_sic.xlsx"
migrations = "analysis/v2_outputs/02_migrations_detailed.xlsx"
output_file = "analysis/v2_outputs/05_destination_analysis.xlsx"

# Read data
print("Reading migrations...")
mig = pd.read_excel(migrations)

# Create output directory if needed
os.makedirs("analysis/v2_outputs", exist_ok=True)

# Analysis 1: Where do companies leaving Maryland go?
print("\nAnalysis 1: Top destination states for companies leaving Maryland")
md_departures = mig[mig["From_State"] == "MD"].copy()
print(f"Total companies leaving Maryland: {len(md_departures)}")

destinations = md_departures["To_State"].value_counts().reset_index()
destinations.columns = ["destination_state", "company_count"]
destinations = destinations.sort_values("company_count", ascending=False)

print("\nTop 10 destination states:")
print(destinations.head(10))

# Analysis 2: Sector-specific destinations
print("\n\nAnalysis 2: Top destinations by sector (companies leaving MD)")
sector_dest = md_departures.groupby(["sector_name", "To_State"]).size().reset_index(name="count")
sector_dest = sector_dest.sort_values(["sector_name", "count"], ascending=[True, False])

# Get top 3 destinations per sector
top_per_sector = sector_dest.groupby("sector_name").head(3).reset_index(drop=True)
print("Top 3 destinations per sector:")
for sector in top_per_sector["sector_name"].unique():
    print(f"\n{sector}:")
    sector_data = top_per_sector[top_per_sector["sector_name"] == sector]
    for idx, row in sector_data.iterrows():
        print(f"  → {row['To_State']}: {row['count']}")

# Analysis 3: Companies arriving in Maryland
print("\n\nAnalysis 3: Where do companies relocating to Maryland come from?")
md_arrivals = mig[mig["To_State"] == "MD"].copy()
print(f"Total companies relocating to Maryland: {len(md_arrivals)}")

origins = md_arrivals["From_State"].value_counts().reset_index()
origins.columns = ["origin_state", "company_count"]
origins = origins.sort_values("company_count", ascending=False)

print("\nTop 10 origin states:")
print(origins.head(10))

# Analysis 4: Summary statistics
print("\n\n=== DESTINATION ANALYSIS SUMMARY ===")
print(f"\nMovements OUT of Maryland: {len(md_departures)}")
print(f"Movements INTO Maryland: {len(md_arrivals)}")
print(f"Net migration: {len(md_arrivals) - len(md_departures)}")

# Combine analyses into single Excel output
print(f"\nWriting comprehensive analysis to {output_file}...")

with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
    destinations.to_excel(writer, sheet_name="Destinations_from_MD", index=False)
    origins.to_excel(writer, sheet_name="Origins_to_MD", index=False)
    sector_dest.to_excel(writer, sheet_name="Destinations_by_Sector", index=False)
    md_departures.to_excel(writer, sheet_name="Companies_Leaving_MD", index=False)
    md_arrivals.to_excel(writer, sheet_name="Companies_Entering_MD", index=False)

print(f"✓ Successfully created {output_file}")
print(f"  Sheets: Destinations_from_MD, Origins_to_MD, Destinations_by_Sector, Companies_Leaving_MD, Companies_Entering_MD")

# Print detailed summary
print("\n=== DESTINATION GEOGRAPHY SUMMARY ===")
print("\nTop 10 exodus destinations from Maryland:")
for idx, row in destinations.head(10).iterrows():
    print(f"  {row['destination_state']:3} ← {row['company_count']:3} companies")

print("\nTop 10 origin states for companies moving to Maryland:")
for idx, row in origins.head(10).iterrows():
    print(f"  {row['origin_state']:3} → {row['company_count']:3} companies")
