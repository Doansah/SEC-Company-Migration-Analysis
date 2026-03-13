import pandas as pd
import os

# Paths
candidates_file = "analysis/v2_outputs/attrition_analysis/01_attrition_candidates.xlsx"
migration_file = "analysis/v2_outputs/02_migrations_detailed.xlsx"
output_file = "analysis/v2_outputs/attrition_analysis/03_attrition_classification.xlsx"

# Create output directory
os.makedirs("analysis/v2_outputs/attrition_analysis", exist_ok=True)

# Read candidates and migrations
print("Reading data...")
candidates = pd.read_excel(candidates_file)
migrations = pd.read_excel(migration_file)

print(f"Attrition candidates: {len(candidates)}")
print(f"Migration records: {len(migrations)}")

# Classify each candidate
classified = []

for idx, row in candidates.iterrows():
    cik = int(row['CIK'])
    company = row['Company']
    sector = row['sector']
    last_md_year = int(row['last_md_year'])
    years_missing = row['years_missing']
    
    # Check if this company appears in migration records
    in_migrations = cik in migrations['CIK'].values
    
    # Classify based on evidence
    if in_migrations:
        # Found in migrations - but check direction
        mig_records = migrations[migrations['CIK'] == cik]
        
        # Get last migration for this company
        last_mig = mig_records.iloc[-1]  # Last record chronologically
        
        if last_mig['From_State'] == 'MD':
            classification = "RELOCATED"
            destination = last_mig['To_State']
            move_year = int(last_mig['Move_Year'])
            note = f"Moved to {destination} in {move_year}"
        else:
            classification = "UNCLEAR_MIGRATION"
            destination = None
            move_year = None
            note = "Migration record exists but not from Maryland"
    else:
        # Not in migrations - company disappeared
        # Classify by recency and sector vulnerability
        
        if years_missing == 0:
            # Disappeared in 2025 - likely data lag or very recent
            classification = "RECENT_DISAPPEARANCE"
            note = "Vanished in 2025 (possible data lag)"
        elif years_missing <= 2:
            # Disappeared 1-2 years ago
            classification = "RECENT_ATTRITION"
            note = f"No SEC filings for {years_missing} years"
        else:
            # Disappeared 3+ years ago
            classification = "ESTABLISHED_ATTRITION"
            note = f"Inactive in SEC system for {years_missing} years"
        
        destination = None
        move_year = None
    
    classified.append({
        "CIK": cik,
        "Company": company,
        "Sector": sector,
        "Last_MD_Year": last_md_year,
        "Classification": classification,
        "Years_Missing": years_missing,
        "Destination": destination,
        "Move_Year": move_year,
        "Note": note
    })

classified_df = pd.DataFrame(classified)

# Summary statistics
print(f"\n{'='*70}")
print(f"ATTRITION CLASSIFICATION ANALYSIS")
print(f"{'='*70}")

print(f"\nClassification Summary:")
class_counts = classified_df['Classification'].value_counts()
for classification, count in class_counts.items():
    pct = 100 * count / len(classified_df)
    print(f"  {classification:25} {count:4} ({pct:5.1f}%)")

print(f"\nBy Sector:")
sector_summary = classified_df.groupby(['Sector', 'Classification']).size().unstack(fill_value=0)
print(sector_summary)

print(f"\nBy Year of Disappearance:")
year_summary = classified_df.groupby('Last_MD_Year')['Classification'].value_counts().unstack(fill_value=0)
print(year_summary)

# Export key statistics CSV
summary_stats = {
    "Total_Attrition_Candidates": len(classified_df),
    "Relocated": len(classified_df[classified_df['Classification'] == 'RELOCATED']),
    "Recent_Disappearance_2025": len(classified_df[classified_df['Classification'] == 'RECENT_DISAPPEARANCE']),
    "Recent_Attrition_1_2yrs": len(classified_df[classified_df['Classification'] == 'RECENT_ATTRITION']),
    "Established_Attrition_3plus": len(classified_df[classified_df['Classification'] == 'ESTABLISHED_ATTRITION']),
    "Unclear_Migration": len(classified_df[classified_df['Classification'] == 'UNCLEAR_MIGRATION'])
}

# Write to Excel
print(f"\nWriting to {output_file}...")
classified_df.to_excel(output_file, index=False, engine="openpyxl", sheet_name="Classification")

print(f"\n✓ Successfully classified {len(classified_df)} companies")
print(f"\n=== KEY FINDINGS ===")
print(f"Relocated to other states:        {summary_stats['Relocated']:4}")
print(f"Recent disappearance (2025):      {summary_stats['Recent_Disappearance_2025']:4}")
print(f"Recent attrition (1-2 years):     {summary_stats['Recent_Attrition_1_2yrs']:4}")
print(f"Established attrition (3+ years): {summary_stats['Established_Attrition_3plus']:4}")
print(f"Unclear migration records:        {summary_stats['Unclear_Migration']:4}")
print(f"\nTOTAL DEPARTURES FROM MARYLAND:   {len(classified_df):4}")
print(f"TRUE RELOCATIONS:                 {summary_stats['Relocated']:4}")
print(f"TRUE ATTRITIONS:                  {len(classified_df) - summary_stats['Relocated']:4}")
