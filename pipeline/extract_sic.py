"""
SIC Code Extraction & Enhancement Module
Extracts SIC codes from SEC quarterly files and creates lookup tables
"""

import pandas as pd
import os
from pathlib import Path

def extract_sic_from_quarterly_files(data_dir: str) -> pd.DataFrame:
    """
    Extract CIK -> SIC code mapping from all quarterly sub.txt files
    Keeps most recent SIC code per CIK (latest filing date)
    
    Args:
        data_dir: Path to quarterly_raw_data directory
        
    Returns:
        DataFrame with: cik, name, sic, period (most recent filing)
    """
    records = []
    
    # Find all sub.txt files
    quarterly_dirs = sorted(Path(data_dir).glob("*/sub.txt"))
    print(f"Found {len(quarterly_dirs)} quarterly sub.txt files")
    
    for file_path in quarterly_dirs:
        try:
            df = pd.read_csv(
                file_path,
                sep="\t",
                dtype=str,
                usecols=["cik", "name", "sic", "period"],
                engine="python",
            )
            # Filter out empty SIC codes
            df = df[df["sic"].notna() & (df["sic"] != "")]
            if not df.empty:
                records.append(df)
                print(f"✓ {file_path.parent.name}: {len(df)} records")
        except Exception as e:
            print(f"⚠ {file_path.parent.name}: Skipped - {str(e)[:50]}")
    
    if not records:
        raise RuntimeError("No SIC data found in any quarterly files")
    
    # Combine all records
    combined = pd.concat(records, ignore_index=True)
    print(f"\nTotal records: {len(combined)}")
    
    # Keep most recent SIC per CIK (by filing period, latest first)
    combined = combined.sort_values(["cik", "period"], ascending=[True, False])
    sic_mapping = combined.drop_duplicates(subset=["cik"], keep="first")
    
    print(f"Unique CIKs with SIC codes: {len(sic_mapping)}")
    print(f"Unique SIC codes: {sic_mapping['sic'].nunique()}")
    
    return sic_mapping[["cik", "name", "sic"]].sort_values("cik")


def create_sic_industry_lookup() -> pd.DataFrame:
    """
    Create comprehensive SIC code to industry mapping
    Based on standard SIC classification (4-digit codes)
    
    Returns:
        DataFrame with: sic, sic_description, sic_2digit, sector_name
    """
    
    # Standard SIC code ranges and descriptions
    sic_data = [
        # Agriculture, Forestry, Fishing (0100-0999)
        ("0100", "Agricultural Production", "01", "Agriculture"),
        ("0200", "Agricultural Services", "02", "Agriculture"),
        ("0700", "Agricultural Services", "07", "Agriculture"),
        ("0900", "Fishing, Hunting, Trapping", "09", "Agriculture"),
        
        # Mining (1000-1499)
        ("1000", "Metal Mining", "10", "Mining"),
        ("1200", "Coal Mining", "12", "Mining"),
        ("1300", "Oil & Gas Extraction", "13", "Mining"),
        ("1400", "Nonmetallic Minerals Extraction", "14", "Mining"),
        
        # Construction (1500-1799)
        ("1500", "Building Construction", "15", "Construction"),
        ("1600", "Heavy Construction", "16", "Construction"),
        ("1700", "Special Trade Contractors", "17", "Construction"),
        
        # Manufacturing (2000-3999)
        ("2000", "Food & Kindred Products", "20", "Manufacturing"),
        ("2100", "Tobacco Products", "21", "Manufacturing"),
        ("2200", "Textile Mill Products", "22", "Manufacturing"),
        ("2300", "Apparel & Other Fiber Products", "23", "Manufacturing"),
        ("2400", "Lumber & Wood Products", "24", "Manufacturing"),
        ("2500", "Furniture & Fixtures", "25", "Manufacturing"),
        ("2600", "Paper & Allied Products", "26", "Manufacturing"),
        ("2700", "Printing & Publishing", "27", "Manufacturing"),
        ("2800", "Chemicals & Allied Products", "28", "Manufacturing"),
        ("2900", "Petroleum & Coal Products", "29", "Manufacturing"),
        ("3000", "Rubber & Misc Plastics", "30", "Manufacturing"),
        ("3100", "Leather & Leather Products", "31", "Manufacturing"),
        ("3200", "Stone, Clay, Glass Products", "32", "Manufacturing"),
        ("3300", "Primary Metal Industries", "33", "Manufacturing"),
        ("3400", "Fabricated Metal Products", "34", "Manufacturing"),
        ("3500", "Industrial Machinery & Equipment", "35", "Manufacturing"),
        ("3600", "Electronic Equipment", "36", "Manufacturing"),
        ("3700", "Transportation Equipment", "37", "Manufacturing"),
        ("3800", "Measuring Instruments", "38", "Manufacturing"),
        ("3900", "Miscellaneous Manufacturing", "39", "Manufacturing"),
        
        # Transportation, Warehouse (4000-4799)
        ("4000", "Railroad Transportation", "40", "Transportation"),
        ("4100", "Local Passenger Transit", "41", "Transportation"),
        ("4200", "Trucking & Warehouse", "42", "Transportation"),
        ("4300", "U.S. Postal Service", "43", "Transportation"),
        ("4400", "Water Transportation", "44", "Transportation"),
        ("4500", "Air Transportation", "45", "Transportation"),
        ("4600", "Pipelines", "46", "Transportation"),
        ("4700", "Transportation Services", "47", "Transportation"),
        
        # Communications, Electric, Gas (4800-4999)
        ("4800", "Communications", "48", "Utilities"),
        ("4900", "Electric, Gas, Sanitary", "49", "Utilities"),
        
        # Wholesale Trade (5000-5199)
        ("5000", "Wholesale Trade - Durable", "50", "Wholesale Trade"),
        ("5100", "Wholesale Trade - Nondurable", "51", "Wholesale Trade"),
        
        # Retail Trade (5200-5999)
        ("5200", "Building Materials & Hardware", "52", "Retail Trade"),
        ("5300", "General Merchandise Stores", "53", "Retail Trade"),
        ("5400", "Food Stores", "54", "Retail Trade"),
        ("5500", "Auto Dealers & Service Stations", "55", "Retail Trade"),
        ("5600", "Apparel & Accessory Stores", "56", "Retail Trade"),
        ("5700", "Home Furniture & Furnishings", "57", "Retail Trade"),
        ("5800", "Eating & Drinking Places", "58", "Retail Trade"),
        ("5900", "Miscellaneous Retail", "59", "Retail Trade"),
        
        # Finance, Insurance, Real Estate (6000-6799)
        ("6000", "Depository Institutions", "60", "Finance"),
        ("6100", "Nondepository Institutions", "61", "Finance"),
        ("6200", "Security & Commodity Brokers", "62", "Finance"),
        ("6300", "Insurance Carriers", "63", "Finance"),
        ("6400", "Insurance Agents & Brokers", "64", "Finance"),
        ("6500", "Real Estate", "65", "Real Estate"),
        ("6700", "Holding & Investment Companies", "67", "Finance"),
        
        # Services (7000-8999)
        ("7000", "Hotels & Lodging", "70", "Services"),
        ("7200", "Personal Services", "72", "Services"),
        ("7300", "Business Services", "73", "Services"),
        ("7400", "Auto Repair, Services", "74", "Services"),
        ("7500", "Auto Rental & Leasing", "75", "Services"),
        ("7600", "Miscellaneous Repair", "76", "Services"),
        ("7800", "Motion Picture & Video", "78", "Services"),
        ("7900", "Amusement & Recreation", "79", "Services"),
        ("8000", "Health Services", "80", "Services"),
        ("8100", "Legal Services", "81", "Services"),
        ("8200", "Educational Services", "82", "Services"),
        ("8300", "Social Services", "83", "Services"),
        ("8400", "Museums, Botanical, Zoological", "84", "Services"),
        ("8600", "Membership Organizations", "86", "Services"),
        ("8700", "Engineering & Accounting", "87", "Professional Services"),
        ("8800", "Private Households", "88", "Services"),
        ("8900", "Miscellaneous Services", "89", "Services"),
        
        # Public Administration (9000-9999)
        ("9100", "Executive, Legislative, General", "91", "Government"),
        ("9200", "Justice, Public Order, Safety", "92", "Government"),
        ("9300", "Finance, Taxation, Monetary", "93", "Government"),
        ("9400", "Administration of Human Affairs", "94", "Government"),
        ("9500", "National Security & International", "95", "Government"),
        ("9600", "Foreign Affairs, International", "96", "Government"),
        ("9900", "Nonclassifiable Establishments", "99", "Other"),
    ]
    
    sic_df = pd.DataFrame(sic_data, columns=["sic", "sic_description", "sic_2digit", "sector_name"])
    return sic_df


def enrich_sic_mapping(sic_mapping: pd.DataFrame, sic_lookup: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich SIC mapping with industry names and sector classifications
    
    Args:
        sic_mapping: DataFrame with cik, name, sic
        sic_lookup: DataFrame with sic, sic_description, sic_2digit, sector_name
        
    Returns:
        Enriched DataFrame with all fields
    """
    
    # Merge mappings
    enriched = sic_mapping.merge(sic_lookup, left_on="sic", right_on="sic", how="left")
    
    # For SIC codes not found in lookup, create generic entry
    missing = enriched[enriched["sic_description"].isna()].copy()
    if len(missing) > 0:
        print(f"\n⚠ {len(missing)} SIC codes not found in standard lookup")
        print(f"Unique missing SIC codes: {missing['sic'].nunique()}")
        
        # Fill missing with generic category
        enriched.loc[enriched["sic_description"].isna(), "sector_name"] = "Other"
        enriched.loc[enriched["sic_description"].isna(), "sic_description"] = "Unclassified"
        enriched.loc[enriched["sic_description"].isna(), "sic_2digit"] = enriched.loc[enriched["sic_description"].isna(), "sic"].str[:2]
    
    return enriched


def main():
    """Extract and create SIC lookup files"""
    
    print("=" * 70)
    print("SIC CODE EXTRACTION FROM SEC QUARTERLY FILES")
    print("=" * 70)
    
    base_dir = "data/sec"
    quarterly_dir = os.path.join(base_dir, "quarterly_raw_data")
    output_dir = os.path.join(base_dir, "external")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Step 1: Extract SIC codes from quarterly files
    print("\n[Step 1/3] Extracting SIC codes from quarterly submission files...")
    sic_mapping = extract_sic_from_quarterly_files(quarterly_dir)
    
    # Step 2: Create SIC industry lookup
    print("\n[Step 2/3] Creating SIC industry classification lookup...")
    sic_lookup = create_sic_industry_lookup()
    print(f"Created lookup with {len(sic_lookup)} SIC codes")
    
    # Step 3: Enrich mapping with industry names
    print("\n[Step 3/3] Enriching SIC mapping with industry data...")
    enriched = enrich_sic_mapping(sic_mapping, sic_lookup)
    
    # Save outputs
    output_mapping = os.path.join(output_dir, "cik_to_sic_mapping.csv")
    output_lookup = os.path.join(output_dir, "sic_industry_names.csv")
    
    # Ensure sic_2digit for all items (for those added during enrichment)
    enriched["sic_2digit"] = enriched["sic_2digit"].fillna(enriched["sic"].str[:2])
    
    enriched.to_csv(output_mapping, index=False)
    sic_lookup.to_csv(output_lookup, index=False)
    
    print("\n" + "=" * 70)
    print("OUTPUT FILES CREATED")
    print("=" * 70)
    print(f"\n✅ CIK-to-SIC Mapping: {output_mapping}")
    print(f"   Rows: {len(enriched)}")
    print(f"   Columns: {', '.join(enriched.columns.tolist())}")
    
    print(f"\n✅ SIC Industry Lookup: {output_lookup}")
    print(f"   Rows: {len(sic_lookup)}")
    print(f"   Columns: {', '.join(sic_lookup.columns.tolist())}")
    
    print("\nSample from CIK-to-SIC Mapping:")
    print(enriched[["cik", "name", "sic", "sic_description", "sector_name"]].head(10).to_string())
    
    print("\n\nSIC Codes by Sector:")
    sector_summary = enriched.groupby("sector_name").agg({
        "cik": "count",
        "sic": "nunique"
    }).rename(columns={"cik": "companies", "sic": "sic_codes"}).sort_values("companies", ascending=False)
    print(sector_summary.to_string())
    
    return enriched, sic_lookup


if __name__ == "__main__":
    enriched, sic_lookup = main()
