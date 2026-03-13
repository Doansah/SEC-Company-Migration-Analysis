"""
Industry trends analysis (Goal 4 Part 1)
Analyzes Maryland corporate movement by industry sector
Output: 04_industry_trends.xlsx
"""

import pandas as pd
import os

# Paths
timeline_sic = "analysis/v2_outputs/01_timeline_with_sic.xlsx"
migrations = "analysis/v2_outputs/02_migrations_detailed.xlsx"
output_file = "analysis/v2_outputs/04_industry_trends.xlsx"

# Read data
print("Reading timeline and migrations with SIC...")
timeline = pd.read_excel(timeline_sic)
mig = pd.read_excel(migrations)

# Create output directory if needed
os.makedirs("analysis/v2_outputs", exist_ok=True)

# Analysis 1: Company count by sector over time (Maryland)
print("\nAnalysis 1: Maryland companies by sector over time")
md_timeline = timeline[timeline["State"] == "MD"].copy()
sector_time = md_timeline.groupby(["Year", "sector_name"]).size().reset_index(name="company_count")
sector_time = sector_time.sort_values(["Year", "company_count"], ascending=[True, False])

# Pivot for easier viewing
sector_pivot = sector_time.pivot(index="Year", columns="sector_name", values="company_count").fillna(0).astype(int)
print(f"Maryland companies by sector by year:")
print(sector_pivot.tail(5))

# Analysis 2: Migration patterns by sector
print("\n\nAnalysis 2: Migration by sector")
mig_sector = mig.groupby("sector_name").agg({
    "CIK": "count",
    "From_State": lambda x: (x == "MD").sum(),
    "To_State": lambda x: (x == "MD").sum()
}).reset_index()
mig_sector.columns = ["sector_name", "total_migrations", "from_md", "to_md"]
mig_sector["net_migration"] = mig_sector["to_md"] - mig_sector["from_md"]
mig_sector = mig_sector.sort_values("total_migrations", ascending=False)

print("Total migrations by sector:")
print(mig_sector)

# Analysis 3: Maryland-specific departures and arrivals
print("\n\nAnalysis 3: Maryland-specific flows by sector")
md_flows = mig[(mig["From_State"] == "MD") | (mig["To_State"] == "MD")].copy()
md_departure = md_flows[md_flows["From_State"] == "MD"].groupby("sector_name").size().reset_index(name="departures")
md_arrival = md_flows[md_flows["To_State"] == "MD"].groupby("sector_name").size().reset_index(name="arrivals")

md_net = md_departure.merge(md_arrival, on="sector_name", how="outer").fillna(0).astype({"departures": int, "arrivals": int})
md_net["net_flow"] = md_net["arrivals"] - md_net["departures"]
md_net = md_net.sort_values("net_flow", ascending=False)

print("Maryland flows by sector (arrivals - departures):")
print(md_net)

# Combine analyses into single Excel output
print(f"\nWriting comprehensive analysis to {output_file}...")

with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
    sector_pivot.to_excel(writer, sheet_name="MD_Companies_by_Year")
    mig_sector.to_excel(writer, sheet_name="All_Migrations_by_Sector", index=False)
    md_net.to_excel(writer, sheet_name="MD_Net_Flows", index=False)
    sector_time.to_excel(writer, sheet_name="MD_by_Sector_Details", index=False)

print(f"✓ Successfully created {output_file}")
print(f"  Sheets: MD_Companies_by_Year, All_Migrations_by_Sector, MD_Net_Flows, MD_by_Sector_Details")

# Print summary
print("\n=== INDUSTRY TRENDS SUMMARY ===")
print("\nMaryland Net Migration by Sector (2015-2025):")
for idx, row in md_net.iterrows():
    sector = row["sector_name"]
    net = row["net_flow"]
    arrivals = row["arrivals"]
    departures = row["departures"]
    symbol = "↑" if net >= 0 else "↓"
    print(f"  {symbol} {sector:20} | Arrivals: {arrivals:3.0f} | Departures: {departures:3.0f} | Net: {net:+4.0f}")
