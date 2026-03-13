import pandas as pd
import requests
import time
import os

# Paths
candidates_file = "analysis/v2_outputs/attrition_analysis/01_attrition_candidates.xlsx"
output_file = "analysis/v2_outputs/attrition_analysis/02_sec_status_verification.xlsx"

# Read candidates
print("Reading attrition candidates...")
candidates = pd.read_excel(candidates_file)
print(f"Total candidates to verify: {len(candidates)}")

# SEC API base URL
SEC_URL = "https://data.sec.gov/submissions/CIK{}.json"

# Query each CIK
verified = []
failed = []

for idx, row in candidates.iterrows():
    cik = int(row['CIK'])
    company = row['Company']
    
    # Format CIK as 10-digit with leading zeros
    cik_formatted = str(cik).zfill(10)
    url = SEC_URL.format(cik_formatted)
    
    try:
        # Query SEC API
        headers = {'User-Agent': 'GBC Research'}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract company info and filing dates
            company_info = data.get('cik', '')
            filings = data.get('filings', {}).get('recent', {})
            
            accession_numbers = filings.get('accessionNumber', [])
            filing_dates = filings.get('filingDate', [])
            
            if filing_dates:
                latest_filing = filing_dates[0]  # Most recent first
                status = "ACTIVE" if latest_filing else "DELISTED"
            else:
                status = "NO_FILINGS_FOUND"
                latest_filing = None
            
            verified.append({
                "CIK": cik,
                "Company": company,
                "Sector": row['sector'],
                "Last_MD_Year": int(row['last_md_year']),
                "SEC_Status": status,
                "Latest_Filing_Date": latest_filing,
                "Years_Missing": row['years_missing']
            })
        else:
            failed.append({
                "CIK": cik,
                "Company": company,
                "Error": f"HTTP {response.status_code}"
            })
        
        # Rate limiting - be nice to SEC
        time.sleep(0.1)
        
        if (idx + 1) % 10 == 0:
            print(f"  Processed {idx + 1}/{len(candidates)}")
    
    except Exception as e:
        failed.append({
            "CIK": cik,
            "Company": company,
            "Error": str(e)
        })

# Convert to DataFrames
verified_df = pd.DataFrame(verified)
failed_df = pd.DataFrame(failed) if failed else pd.DataFrame()

print(f"\n{'='*60}")
print(f"SEC API VERIFICATION RESULTS")
print(f"{'='*60}")
print(f"Successfully verified: {len(verified_df)}")
print(f"Failed to verify: {len(failed_df)}")

if len(verified_df) > 0:
    print(f"\nStatus breakdown:")
    status_counts = verified_df['SEC_Status'].value_counts()
    for status, count in status_counts.items():
        pct = 100 * count / len(verified_df)
        print(f"  {status:25} {count:4} ({pct:5.1f}%)")
    
    print(f"\nLatest filing dates (for ACTIVE companies):")
    active_df = verified_df[verified_df['SEC_Status'] == 'ACTIVE']
    if len(active_df) > 0:
        latest_by_year = active_df['Latest_Filing_Date'].value_counts().sort_index(ascending=False).head(10)
        for date, count in latest_by_year.items():
            print(f"  {date}: {count} companies")

# Write to Excel
print(f"\nWriting to {output_file}...")
verified_df.to_excel(output_file, index=False, engine="openpyxl", sheet_name="Verified")

if len(failed_df) > 0:
    with pd.ExcelWriter(output_file, engine="openpyxl", mode="a") as writer:
        failed_df.to_excel(writer, sheet_name="Failed", index=False)

print(f"Successfully wrote verification results")
