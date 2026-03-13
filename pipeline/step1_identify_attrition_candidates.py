import pandas as pd
import os

# Paths
timeline_sic = "analysis/v2_outputs/01_timeline_with_sic.xlsx"
output_file = "analysis/v2_outputs/attrition_analysis/01_attrition_candidates.xlsx"

# Create output directory
os.makedirs("analysis/v2_outputs/attrition_analysis", exist_ok=True)

# Read timeline
print("Reading timeline...")
timeline = pd.read_excel(timeline_sic)
print(f"Total records: {len(timeline)}")

# Step 1: Find all Maryland companies (ever appeared in MD)
md_companies = timeline[timeline["State"] == "MD"].copy()
md_ciks = md_companies["CIK"].unique()
print(f"Total companies ever in Maryland: {len(md_ciks)}")

# Step 2: For each Maryland company, find its last year in Maryland
md_last_year = md_companies.groupby("CIK")["Year"].max().reset_index()
md_last_year.columns = ["CIK", "last_md_year"]

# Step 3: For each Maryland company, check if it appears ANYWHERE after leaving MD
all_company_records = timeline[timeline["CIK"].isin(md_ciks)].copy()

# Identify gap candidates
gap_candidates = []

for cik in md_ciks:
    company_records = all_company_records[all_company_records["CIK"] == cik]
    
    # Get last year in MD
    last_md = company_records[company_records["State"] == "MD"]["Year"].max()
    
    # Check if company appears after last MD year
    records_after = company_records[company_records["Year"] > last_md]
    
    if len(records_after) == 0:
        # This is a gap candidate - disappeared after last MD appearance
        company_name = company_records.iloc[0]["Company"]
        sector = company_records.iloc[0]["sector_name"]
        sic = company_records.iloc[0]["sic"]
        
        gap_candidates.append({
            "CIK": cik,
            "Company": company_name,
            "last_md_year": int(last_md),
            "sector": sector,
            "sic": int(sic) if pd.notna(sic) else None,
            "years_missing": 2025 - int(last_md)
        })

gap_df = pd.DataFrame(gap_candidates)
gap_df = gap_df.sort_values("last_md_year", ascending=False)

print("="*60)
print("ATTRITION ANALYSIS - STEP 1: IDENTIFY CANDIDATES")
print("="*60)
print(f"Gap Candidates Found: {len(gap_df)}")
print(f"Percentage of MD companies: {100*len(gap_df)/len(md_ciks):.1f}%")

# Analysis by sector
print(f"\nAttrition by sector:")
sector_counts = gap_df["sector"].value_counts()
for sector, count in sector_counts.items():
    pct = 100 * count / len(gap_df)
    print(f"  {sector:20} {count:4} ({pct:5.1f}%)")

# Analysis by timeframe
print(f"\nAttrition timeline (when last appeared in Maryland):")
timeline_counts = gap_df["last_md_year"].value_counts().sort_index(ascending=False)
for year, count in timeline_counts.head(15).items():
    years_ago = 2025 - year
    print(f"  {int(year)} (disappeared {years_ago} years ago): {count} companies")

# Write to Excel
print(f"\nWriting to {output_file}...")
gap_df.to_excel(output_file, index=False, engine="openpyxl")

print(f"\nSuccessfully identified {len(gap_df)} attrition candidates")
print(f"\nSample candidates (most recent):")
for idx, row in gap_df.head(10).iterrows():
    print(f"  CIK {row['CIK']}: {row['Company'][:40]:40} | {int(row['last_md_year'])} | {row['sector']}")
