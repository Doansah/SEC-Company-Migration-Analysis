"""
Enrich MASTER_DATASET.xlsx — fix data quality issues and add new columns.

Fixes:
  1. Financial_Data_Available flag inconsistency (4 rows)
  2. Fill missing market caps for MAJOR exchange companies (28 rows)
  3. Populate Market_Cap_Current for still-traded companies
  4. Reclassify Origin_Subtype using SEC EDGAR earliest filing dates
  5. Fill missing Counterpart_State for two foreign arrivals

Extensions:
  1. Is_Still_In_MD (boolean)
  2. Attrition_Reason (string, nullable)
  3. Company_Size_Tier (string)

Output: Overwrites analysis/v2_outputs/MASTER_DATASET.xlsx
"""

import json
import os
import time

import numpy as np
import pandas as pd
import requests
import warnings

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2_OUTPUTS = os.path.join(BASE_DIR, "analysis", "v2_outputs")
CACHE_DIR = os.path.join(V2_OUTPUTS, "cache")

SEC_HEADERS = {
    "User-Agent": "CompanyMigrationResearch research@example.com",
    "Accept-Encoding": "gzip, deflate",
}

# BLS CPI-U Annual Averages (base year 2024)
CPI_TABLE = {
    2015: 237.017, 2016: 240.007, 2017: 245.120, 2018: 251.107,
    2019: 255.657, 2020: 258.811, 2021: 270.970, 2022: 292.655,
    2023: 304.702, 2024: 314.690, 2025: 314.690,
}
CPI_BASE = CPI_TABLE[2024]

# Known tickers for companies where SEC API may not return them (delisted/acquired)
KNOWN_TICKERS = {
    704051: "LM",        # LEGG MASON — delisted 2020 (acquired by Franklin Templeton)
    944480: "GVP",       # GSE SYSTEMS
    927355: "TESS",      # TESSCO TECHNOLOGIES
    1524741: "SLCA",     # U.S. SILICA HOLDINGS
    1599947: "TERP",     # TERRAFORM POWER — delisted 2020 (acquired by Brookfield)
    1620702: "GLBL",     # TERRAFORM GLOBAL — delisted 2017 (acquired by Brookfield)
    1592057: "EVA",      # ENVIVA PARTNERS — delisted 2023 (bankruptcy)
    852437: "RWWI",      # RAND WORLDWIDE
    1075857: "VSYM",     # VIEW SYSTEMS
    1301838: "PPGX",     # PREMIER PRODUCT GROUP (OTC)
    1354591: "PTLF",     # PETLIFE PHARMACEUTICALS (OTC)
    1413488: "MCTC",     # MICROCHANNEL TECHNOLOGIES
    1862068: "FOUN",     # FOUNDER SPAC
    1871638: "BRTX",     # BURTECH ACQUISITION — common stock ticker (not BZAIW warrant)
}

# Known attrition reasons (from user) — keyed by actual CIK from MASTER_DATASET
KNOWN_ATTRITION_REASONS = {
    704051: "ACQUIRED",      # LEGG MASON — acquired by Franklin Templeton 2020
    1551739: "ACQUIRED",     # HAMILTON BANCORP — acquired by Severn Bancorp
    1620702: "ACQUIRED",     # TERRAFORM GLOBAL — acquired by Brookfield
    1592057: "BANKRUPTCY",   # ENVIVA PARTNERS — filed for bankruptcy
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_all_data():
    """Load MASTER_DATASET and supporting files."""
    print("Loading data files...")

    master = pd.read_excel(
        os.path.join(V2_OUTPUTS, "MASTER_DATASET.xlsx"),
        dtype={"CIK": str},
    )
    print(f"  MASTER_DATASET: {len(master)} rows, {len(master.columns)} columns")

    timeline = pd.read_excel(os.path.join(V2_OUTPUTS, "01_timeline_with_sic.xlsx"))
    print(f"  Timeline: {len(timeline)} rows")

    migrations = pd.read_excel(os.path.join(V2_OUTPUTS, "02_migrations_detailed.xlsx"))
    print(f"  Migrations: {len(migrations)} rows")

    return {
        "master": master,
        "timeline": timeline,
        "migrations": migrations,
    }


# ---------------------------------------------------------------------------
# SEC EDGAR API helpers
# ---------------------------------------------------------------------------

def get_sec_submissions(cik):
    """Fetch company submission data from SEC EDGAR."""
    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    try:
        resp = requests.get(url, headers=SEC_HEADERS, timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"    SEC API error for CIK {cik}: {e}")
    return None


def get_earliest_filing_year(sec_data):
    """Determine the earliest filing year from SEC submissions data.

    Returns (year, has_older_files) tuple.
    has_older_files=True means the company has paginated filing history (1000+ filings).
    """
    if not sec_data:
        return None, False

    filings = sec_data.get("filings", {})
    recent = filings.get("recent", {})
    filing_dates = recent.get("filingDate", [])
    older_files = filings.get("files", [])

    # If there are older filing pages, company has 1000+ filings — definitely established
    if older_files:
        return None, True

    if not filing_dates:
        return None, False

    # filing_dates[0] = most recent, filing_dates[-1] = oldest in this batch
    try:
        oldest_date = filing_dates[-1]
        oldest_year = int(oldest_date[:4])
        return oldest_year, False
    except (ValueError, IndexError):
        return None, False


def get_ticker_from_sec(cik):
    """Try to find a ticker symbol from SEC EDGAR data."""
    data = get_sec_submissions(cik)
    if not data:
        return None, data
    tickers = data.get("tickers", [])
    if tickers:
        return tickers[0], data
    return None, data


# ---------------------------------------------------------------------------
# yfinance helpers
# ---------------------------------------------------------------------------

def get_historical_price(ticker, target_year):
    """Get historical stock price near year-end using yfinance.

    Returns (price, shares, yf_market_cap) or (None, None, None).
    """
    if not ticker or pd.isna(ticker):
        return None, None, None

    try:
        import yfinance as yf

        stock = yf.Ticker(ticker)

        # Current info for cross-checking
        info = stock.fast_info if hasattr(stock, "fast_info") else {}
        current_mcap = getattr(info, "market_cap", None) if info else None
        current_shares = getattr(info, "shares", None) if info else None

        # Historical price near year-end
        start_date = f"{target_year}-09-01"
        end_date = f"{target_year + 1}-03-31"
        hist = stock.history(start=start_date, end=end_date, auto_adjust=False)
        if hist.empty:
            hist = stock.history(
                start=f"{target_year}-01-01",
                end=f"{target_year + 1}-06-30",
                auto_adjust=False,
            )

        price = None
        if not hist.empty and "Close" in hist.columns:
            price = float(hist["Close"].iloc[-1])

        return price, current_shares, current_mcap
    except Exception as e:
        print(f"    yfinance error for {ticker}: {e}")

    return None, None, None


def get_current_market_cap(ticker):
    """Get current market cap from yfinance."""
    if not ticker or pd.isna(ticker):
        return None

    try:
        import yfinance as yf

        stock = yf.Ticker(ticker)
        info = stock.fast_info if hasattr(stock, "fast_info") else {}
        mcap = getattr(info, "market_cap", None) if info else None
        return mcap
    except Exception as e:
        print(f"    yfinance current mcap error for {ticker}: {e}")

    return None


# ---------------------------------------------------------------------------
# Issue 1: Fix Financial_Data_Available flag
# ---------------------------------------------------------------------------

def fix_financial_data_flag(df):
    """Set Financial_Data_Available=False when Market_Cap, Stock_Price, and Shares are all null."""
    print("\n--- Issue 1: Fixing Financial_Data_Available flag ---")
    changed = 0
    noted = 0

    for idx, row in df.iterrows():
        mcap_null = pd.isna(row["Market_Cap_At_Event"])
        price_null = pd.isna(row["Stock_Price_At_Event"])
        shares_null = pd.isna(row["Shares_Outstanding_At_Event"])

        if mcap_null and price_null and shares_null:
            if row["Financial_Data_Available"] == True:
                df.at[idx, "Financial_Data_Available"] = False
                changed += 1
        elif not shares_null and mcap_null and price_null:
            # Has shares but no price/market cap — keep True but note
            if pd.isna(row.get("Notes")) or row.get("Notes") is None:
                df.at[idx, "Notes"] = "Shares data available but no market price data for market cap calculation"
            noted += 1

    print(f"  Flags corrected (True → False): {changed}")
    print(f"  Notes added (shares only): {noted}")
    return df, changed


# ---------------------------------------------------------------------------
# Issue 5: Fix missing Counterpart_State for foreign arrivals
# ---------------------------------------------------------------------------

def fix_missing_counterparts(df, timeline):
    """Fix null Counterpart_State/City for foreign arrival companies."""
    print("\n--- Issue 5: Fixing missing Counterpart_State for foreign arrivals ---")
    changed = 0

    # Known foreign arrivals from timeline analysis
    foreign_map = {
        "1674440": {"state": "FOREIGN", "city": "PRAGUE"},      # SLINGER BAG — Czech Republic
        "1117057": {"state": "FOREIGN", "city": "SHANGHAI"},     # PLANET GREEN — China
    }

    for idx, row in df.iterrows():
        cik_str = str(row["CIK"]).zfill(10)
        cik_short = cik_str.lstrip("0") or "0"

        if row["Event_Type"] == "ARRIVAL" and pd.isna(row.get("Counterpart_State")):
            if cik_short in foreign_map:
                info = foreign_map[cik_short]
                df.at[idx, "Counterpart_State"] = info["state"]
                df.at[idx, "Counterpart_City"] = info["city"]
                print(f"  Fixed: {row['Company']} → {info['state']}/{info['city']}")
                changed += 1
            else:
                # Try to find pre-MD location from timeline
                cik_int = int(cik_short)
                company_tl = timeline[timeline["CIK"] == cik_int]
                event_year = int(row["Event_Year"])
                pre_md = company_tl[
                    (company_tl["Year"] < event_year) & (company_tl["State"] != "MD")
                ].sort_values("Year", ascending=False)

                if not pre_md.empty:
                    from_state = pre_md.iloc[0]["State"]
                    from_city = pre_md.iloc[0]["City"]
                    if pd.notna(from_state):
                        df.at[idx, "Counterpart_State"] = from_state
                        df.at[idx, "Counterpart_City"] = from_city
                        print(f"  Fixed from timeline: {row['Company']} → {from_state}/{from_city}")
                        changed += 1
                    else:
                        # State is null — likely foreign
                        city = pre_md.iloc[0]["City"] if pd.notna(pre_md.iloc[0]["City"]) else None
                        df.at[idx, "Counterpart_State"] = "FOREIGN"
                        df.at[idx, "Counterpart_City"] = city
                        print(f"  Fixed (foreign): {row['Company']} → FOREIGN/{city}")
                        changed += 1

    print(f"  Total fixed: {changed}")
    return df, changed


# ---------------------------------------------------------------------------
# Issue 4: Fix Origin_Subtype classification
# ---------------------------------------------------------------------------

def fix_origin_subtypes(df):
    """Reclassify Origin_Subtype using SEC EDGAR earliest filing dates."""
    print("\n--- Issue 4: Fixing Origin_Subtype classification ---")

    cache_path = os.path.join(CACHE_DIR, "sec_earliest_filings.json")

    # Load cache if exists
    cached = {}
    if os.path.exists(cache_path):
        with open(cache_path, "r") as f:
            cached = json.load(f)
        print(f"  Loaded {len(cached)} cached filing dates")

    origins = df[df["Event_Type"] == "ORIGIN"].copy()
    print(f"  Processing {len(origins)} origin companies...")

    reclassified = 0
    stayed_ipo = 0
    results = {}

    for idx, row in origins.iterrows():
        cik_str = str(row["CIK"]).zfill(10)
        cik_int_str = str(int(cik_str))
        company = row["Company"]
        event_year = int(row["Event_Year"])

        if cik_int_str in cached:
            earliest_year = cached[cik_int_str].get("earliest_year")
            has_older = cached[cik_int_str].get("has_older_files", False)
        else:
            time.sleep(0.15)  # Rate limit
            sec_data = get_sec_submissions(cik_str)
            earliest_year, has_older = get_earliest_filing_year(sec_data)
            results[cik_int_str] = {
                "earliest_year": earliest_year,
                "has_older_files": has_older,
                "company": company,
            }

        # Classification logic
        if has_older:
            # 1000+ filings — definitely pre-2015
            new_subtype = "FIRST_APPEARANCE"
        elif earliest_year is not None and earliest_year < 2015:
            new_subtype = "FIRST_APPEARANCE"
        elif earliest_year is not None and earliest_year >= 2015:
            new_subtype = "IPO_IN_MD"
        elif event_year <= 2015:
            # No filing data but event is at data boundary — likely pre-existing
            new_subtype = "FIRST_APPEARANCE"
        else:
            # Can't determine — keep as IPO_IN_MD if event year is recent
            new_subtype = "IPO_IN_MD"

        old_subtype = row["Origin_Subtype"]
        if old_subtype != new_subtype:
            df.at[idx, "Origin_Subtype"] = new_subtype
            reclassified += 1
            label = f"(oldest filing: {earliest_year}, has_older: {has_older})"
            print(f"  {company}: {old_subtype} → {new_subtype} {label}")
        else:
            stayed_ipo += 1

    # Update cache
    if results:
        cached.update(results)
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(cached, f, indent=2)
        print(f"  Cached {len(results)} new filing date lookups")

    print(f"  Reclassified: {reclassified} (IPO_IN_MD → FIRST_APPEARANCE)")
    print(f"  Remained IPO_IN_MD: {stayed_ipo}")
    return df, reclassified


# ---------------------------------------------------------------------------
# Issue 2: Fill missing market caps for MAJOR exchange companies
# ---------------------------------------------------------------------------

def fill_missing_market_caps(df):
    """Fill Market_Cap_At_Event for MAJOR exchange companies missing it."""
    print("\n--- Issue 2: Filling missing market caps ---")

    cache_path = os.path.join(CACHE_DIR, "enriched_market_caps.json")
    cached = {}
    if os.path.exists(cache_path):
        with open(cache_path, "r") as f:
            cached = json.load(f)
        print(f"  Loaded {len(cached)} cached market caps")

    missing = df[
        (df["Exchange_Tier"] == "MAJOR") & (df["Market_Cap_At_Event"].isna())
    ].copy()
    print(f"  {len(missing)} MAJOR exchange rows missing market cap")

    # Also try to fill for rows where we just don't have data regardless of tier
    all_missing_mcap = df[df["Market_Cap_At_Event"].isna()].copy()
    print(f"  ({len(all_missing_mcap)} total rows missing market cap)")

    filled = 0
    ticker_found = 0
    processed_ciks = set()

    for idx, row in missing.iterrows():
        cik_str = str(row["CIK"]).zfill(10)
        cik_int_str = str(int(cik_str))
        company = row["Company"]
        event_year = int(row["Event_Year"])
        ticker = row.get("Ticker")

        # Skip if already processed this CIK
        if cik_int_str in processed_ciks:
            continue
        processed_ciks.add(cik_int_str)

        # Check cache first
        cache_key = f"{cik_int_str}_{event_year}"
        if cache_key in cached:
            mcap = cached[cache_key].get("market_cap")
            if mcap:
                _apply_market_cap(df, idx, cik_str, mcap, event_year,
                                  cached[cache_key].get("price"),
                                  cached[cache_key].get("shares"),
                                  cached[cache_key].get("ticker"))
                filled += 1
                continue

        print(f"  Processing: {company} (CIK {cik_int_str}, year {event_year})")

        # Step 1: Find ticker if missing (or override warrants with common stock)
        cik_int = int(cik_int_str)
        if cik_int in KNOWN_TICKERS:
            known = KNOWN_TICKERS[cik_int]
            if pd.isna(ticker) or not ticker or ticker != known:
                ticker = known
                df.loc[df["CIK"] == cik_str, "Ticker"] = ticker
                print(f"    Using known ticker: {ticker}")

        if pd.isna(ticker) or not ticker:
            cik_int = int(cik_int_str)
            # Check known tickers fallback
            if cik_int in KNOWN_TICKERS:
                ticker = KNOWN_TICKERS[cik_int]
                ticker_found += 1
                print(f"    Known ticker: {ticker}")
            else:
                time.sleep(0.15)
                found_ticker, _ = get_ticker_from_sec(cik_int_str)
                if found_ticker:
                    ticker = found_ticker
                    ticker_found += 1
                    print(f"    Found ticker from SEC: {ticker}")
            if ticker:
                # Update ticker on all rows for this CIK
                df.loc[df["CIK"] == cik_str, "Ticker"] = ticker

        if not ticker or pd.isna(ticker):
            print(f"    No ticker available — skipping")
            cached[cache_key] = {"market_cap": None, "ticker": None}
            continue

        # Step 2: Get historical price
        price, yf_shares, yf_mcap = get_historical_price(ticker, event_year)

        if price is None:
            print(f"    No historical price for {ticker} in {event_year}")
            cached[cache_key] = {"market_cap": None, "ticker": ticker}
            continue

        # Step 3: Calculate market cap
        shares = row.get("Shares_Outstanding_At_Event")
        if pd.isna(shares) and yf_shares:
            shares = yf_shares

        market_cap = None
        if price and shares:
            calculated = shares * price
            # Sanity check: if calculated > 50x yfinance current, use yfinance
            if yf_mcap and calculated > yf_mcap * 50:
                print(f"    Calculated ${calculated:,.0f} >> current ${yf_mcap:,.0f}, using yfinance")
                market_cap = yf_mcap
            elif calculated > 50_000_000_000 and not yf_mcap:
                print(f"    Calculated ${calculated:,.0f} seems unreasonable, skipping")
                market_cap = None
            else:
                market_cap = calculated
        elif yf_mcap:
            market_cap = yf_mcap

        if market_cap:
            _apply_market_cap(df, idx, cik_str, market_cap, event_year, price, shares, ticker)
            filled += 1
            print(f"    Market Cap: ${market_cap:,.0f}")

        cached[cache_key] = {
            "market_cap": market_cap,
            "price": price,
            "shares": int(shares) if shares and not pd.isna(shares) else None,
            "ticker": ticker,
        }

    # Save cache
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(cached, f, indent=2, default=str)
    print(f"  Filled: {filled} of {len(processed_ciks)} unique companies")
    print(f"  New tickers found: {ticker_found}")
    return df, filled


def _apply_market_cap(df, idx, cik_str, market_cap, event_year, price, shares, ticker):
    """Apply market cap and related fields to the DataFrame row and any duplicates."""
    df.at[idx, "Market_Cap_At_Event"] = market_cap

    # CPI adjustment
    if event_year in CPI_TABLE:
        df.at[idx, "Market_Cap_At_Event_CPI_Adjusted"] = market_cap * (CPI_BASE / CPI_TABLE[event_year])

    if price and not pd.isna(price):
        df.at[idx, "Stock_Price_At_Event"] = price
    if shares and not pd.isna(shares):
        df.at[idx, "Shares_Outstanding_At_Event"] = int(shares)
    if ticker:
        df.at[idx, "Ticker"] = ticker

    # Update Financial_Data_Available
    df.at[idx, "Financial_Data_Available"] = True


# ---------------------------------------------------------------------------
# Extension 2: Attrition_Reason
# ---------------------------------------------------------------------------

def add_attrition_reason(df):
    """Add Attrition_Reason column for ATTRITION event rows."""
    print("\n--- Extension 2: Adding Attrition_Reason column ---")

    df["Attrition_Reason"] = None
    classified = 0
    unknown = 0

    for idx, row in df.iterrows():
        if row["Event_Type"] != "ATTRITION":
            continue

        cik_int = int(str(row["CIK"]).lstrip("0") or "0")

        if cik_int in KNOWN_ATTRITION_REASONS:
            df.at[idx, "Attrition_Reason"] = KNOWN_ATTRITION_REASONS[cik_int]
            classified += 1
            print(f"  {row['Company']}: {KNOWN_ATTRITION_REASONS[cik_int]}")
        else:
            df.at[idx, "Attrition_Reason"] = "UNKNOWN"
            unknown += 1
            print(f"  {row['Company']}: UNKNOWN (needs user input)")

    print(f"  Classified: {classified}, Unknown: {unknown}")
    return df, classified, unknown


# ---------------------------------------------------------------------------
# Issue 3: Fill Market_Cap_Current
# ---------------------------------------------------------------------------

def fill_current_market_caps(df):
    """Populate Market_Cap_Current for still-traded companies."""
    print("\n--- Issue 3: Filling Market_Cap_Current ---")

    cache_path = os.path.join(CACHE_DIR, "current_market_caps.json")
    cached = {}
    if os.path.exists(cache_path):
        with open(cache_path, "r") as f:
            cached = json.load(f)
        print(f"  Loaded {len(cached)} cached current market caps")

    # Build set of CIKs that should NOT have current market cap
    # (attrited or acquired companies)
    skip_ciks = set()
    for _, row in df.iterrows():
        if row["Event_Type"] == "ATTRITION":
            cik = str(row["CIK"]).zfill(10)
            skip_ciks.add(cik)
        if row.get("Attrition_Reason") == "ACQUIRED":
            cik = str(row["CIK"]).zfill(10)
            skip_ciks.add(cik)

    # Also skip CIKs of companies that departed (they're no longer MD companies,
    # but they may still trade — we'll still fetch for them)
    filled = 0
    skipped = 0
    no_data = 0
    processed_tickers = {}

    # Get unique CIK-ticker pairs
    for idx, row in df.iterrows():
        cik_str = str(row["CIK"]).zfill(10)
        ticker = row.get("Ticker")

        if cik_str in skip_ciks:
            skipped += 1
            continue

        if pd.isna(ticker) or not ticker:
            no_data += 1
            continue

        cik_int_str = str(int(cik_str))

        if cik_int_str in processed_tickers:
            # Already fetched — apply cached value
            mcap = processed_tickers[cik_int_str]
            if mcap:
                df.at[idx, "Market_Cap_Current"] = mcap
                filled += 1
            continue

        # Check disk cache
        if cik_int_str in cached and cached[cik_int_str] is not None:
            mcap = cached[cik_int_str]
            processed_tickers[cik_int_str] = mcap
            if mcap:
                df.at[idx, "Market_Cap_Current"] = mcap
                filled += 1
            continue

        # Fetch from yfinance
        mcap = get_current_market_cap(ticker)
        processed_tickers[cik_int_str] = mcap
        cached[cik_int_str] = mcap

        if mcap:
            df.at[idx, "Market_Cap_Current"] = mcap
            filled += 1
            print(f"  {row['Company']} ({ticker}): ${mcap:,.0f}")
        else:
            no_data += 1

    # Save cache
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump(cached, f, indent=2, default=str)

    print(f"  Filled: {filled}")
    print(f"  Skipped (attrition/acquired): {skipped}")
    print(f"  No data (no ticker or yfinance failed): {no_data}")
    return df, filled


# ---------------------------------------------------------------------------
# Extension 1: Is_Still_In_MD
# ---------------------------------------------------------------------------

def add_is_still_in_md(df, timeline):
    """Add Is_Still_In_MD column based on departure/attrition events."""
    print("\n--- Extension 1: Adding Is_Still_In_MD column ---")

    # CIKs that have departed or attrited
    departed_ciks = set()
    for _, row in df.iterrows():
        if row["Event_Type"] in ("RELOCATION_DEPARTURE", "ATTRITION"):
            departed_ciks.add(str(row["CIK"]).zfill(10))

    still_in = 0
    left = 0

    df["Is_Still_In_MD"] = None
    for idx, row in df.iterrows():
        cik_str = str(row["CIK"]).zfill(10)
        if cik_str in departed_ciks:
            df.at[idx, "Is_Still_In_MD"] = False
            left += 1
        else:
            df.at[idx, "Is_Still_In_MD"] = True
            still_in += 1

    print(f"  Still in MD (True): {still_in} rows")
    print(f"  Left MD (False): {left} rows")
    return df


# ---------------------------------------------------------------------------
# Extension 3: Company_Size_Tier
# ---------------------------------------------------------------------------

def add_company_size_tier(df):
    """Add Company_Size_Tier column based on Market_Cap_At_Event."""
    print("\n--- Extension 3: Adding Company_Size_Tier column ---")

    def classify(mcap):
        if pd.isna(mcap) or mcap is None:
            return "UNKNOWN"
        if mcap > 10_000_000_000:
            return "LARGE_CAP"
        elif mcap >= 2_000_000_000:
            return "MID_CAP"
        elif mcap >= 300_000_000:
            return "SMALL_CAP"
        else:
            return "MICRO_CAP"

    df["Company_Size_Tier"] = df["Market_Cap_At_Event"].apply(classify)

    counts = df["Company_Size_Tier"].value_counts()
    for tier, count in counts.items():
        print(f"  {tier}: {count}")

    return df


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_output(df):
    """Write enriched DataFrame to MASTER_DATASET.xlsx."""
    # Reorder columns
    column_order = [
        # Identity
        "CIK", "Company", "Ticker", "SIC", "SIC_Description", "Sector",
        # Location
        "City", "State", "Is_Baltimore_Region",
        "Counterpart_State", "Counterpart_City",
        # Event
        "Event_Type", "Event_Year",
        "Origin_Subtype", "Departure_Subtype",
        "First_MD_Year", "Last_MD_Year", "Years_In_MD",
        # Financial
        "Market_Cap_At_Event", "Market_Cap_At_Event_CPI_Adjusted",
        "Stock_Price_At_Event", "Shares_Outstanding_At_Event",
        "Market_Cap_Current", "Exchange_Tier", "Financial_Data_Available",
        "Company_Size_Tier",
        # Status
        "Is_Still_In_MD",
        "Attrition_Reason",
        # Metadata
        "Data_Source", "Verification_Status", "Notes",
    ]

    final_cols = [c for c in column_order if c in df.columns]
    df = df[final_cols]

    # Sort
    type_order = {"ORIGIN": 0, "ARRIVAL": 1, "RELOCATION_DEPARTURE": 2, "ATTRITION": 3}
    df["_sort"] = df["Event_Type"].map(type_order)
    df = df.sort_values(["Event_Year", "_sort"], ascending=[False, True])
    df = df.drop(columns=["_sort"])

    # Ensure CIK is text
    df["CIK"] = df["CIK"].astype(str)

    output_path = os.path.join(V2_OUTPUTS, "MASTER_DATASET.xlsx")
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Master")
        ws = writer.sheets["Master"]
        from openpyxl.styles import numbers
        for row in ws.iter_rows(min_row=2, min_col=1, max_col=1, max_row=ws.max_row):
            for cell in row:
                cell.number_format = numbers.FORMAT_TEXT

    print(f"\nWritten to: {output_path}")
    print(f"  Rows: {len(df)}, Columns: {len(df.columns)}")
    return df


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_change_summary(before_df, after_df, stats):
    """Print detailed change summary."""
    print(f"\n{'='*60}")
    print("ENRICHMENT SUMMARY")
    print(f"{'='*60}")
    print(f"Before: {len(before_df)} rows, {len(before_df.columns)} columns")
    print(f"After:  {len(after_df)} rows, {len(after_df.columns)} columns")
    print(f"New columns: {len(after_df.columns) - len(before_df.columns)}")

    print(f"\nIssue 1 (Financial_Data_Available): {stats.get('issue1', 0)} flags corrected")
    print(f"Issue 2 (Missing Market Caps): {stats.get('issue2', 0)} filled")
    print(f"Issue 3 (Market_Cap_Current): {stats.get('issue3', 0)} populated")
    print(f"Issue 4 (Origin Subtypes): {stats.get('issue4', 0)} reclassified")
    print(f"Issue 5 (Counterpart States): {stats.get('issue5', 0)} fixed")

    print(f"\nExtension 1 (Is_Still_In_MD): "
          f"{(after_df['Is_Still_In_MD'] == True).sum()} True, "
          f"{(after_df['Is_Still_In_MD'] == False).sum()} False")
    print(f"Extension 2 (Attrition_Reason): "
          f"{stats.get('ext2_classified', 0)} classified, "
          f"{stats.get('ext2_unknown', 0)} UNKNOWN")
    print(f"Extension 3 (Company_Size_Tier): "
          f"{after_df['Company_Size_Tier'].value_counts().to_dict()}")

    # Verification
    print(f"\nVerification:")
    dupes = after_df.duplicated(subset=["CIK", "Event_Type", "Event_Year"]).sum()
    print(f"  Duplicate (CIK, Event_Type, Event_Year): {'PASS' if dupes == 0 else f'FAIL ({dupes} dupes)'}")
    cik_ok = all(after_df["CIK"].astype(str).str.len() == 10)
    print(f"  CIK format (10-digit): {'PASS' if cik_ok else 'FAIL'}")

    # Remaining attention needed
    print(f"\nRows needing attention:")
    unknowns = after_df[after_df["Attrition_Reason"] == "UNKNOWN"]
    if not unknowns.empty:
        print("  UNKNOWN attrition reasons:")
        for _, r in unknowns.iterrows():
            print(f"    - {r['Company']} (CIK {r['CIK']}, Last MD: {r['Last_MD_Year']})")

    still_missing = after_df[
        (after_df["Exchange_Tier"] == "MAJOR") & (after_df["Market_Cap_At_Event"].isna())
    ]
    if not still_missing.empty:
        print(f"  MAJOR exchange still missing market cap: {len(still_missing)} rows")
        for _, r in still_missing.iterrows():
            print(f"    - {r['Company']} ({r['Ticker'] or 'no ticker'}, {r['Event_Year']})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    data = load_all_data()
    df = data["master"]
    timeline = data["timeline"]

    # Ensure object dtype for columns we'll write strings into
    for col in ["Notes", "Counterpart_State", "Counterpart_City", "Origin_Subtype"]:
        if col in df.columns:
            df[col] = df[col].astype(object)

    before_df = df.copy()
    stats = {}

    # Issue 1: Fix Financial_Data_Available
    df, count = fix_financial_data_flag(df)
    stats["issue1"] = count

    # Issue 5: Fix missing counterparts
    df, count = fix_missing_counterparts(df, timeline)
    stats["issue5"] = count

    # Issue 4: Fix origin subtypes
    df, count = fix_origin_subtypes(df)
    stats["issue4"] = count

    # Issue 2: Fill missing market caps
    df, count = fill_missing_market_caps(df)
    stats["issue2"] = count

    # Extension 2: Attrition reason (before Issue 3 so we know acquired CIKs)
    df, classified, unknown = add_attrition_reason(df)
    stats["ext2_classified"] = classified
    stats["ext2_unknown"] = unknown

    # Issue 3: Fill current market caps
    df, count = fill_current_market_caps(df)
    stats["issue3"] = count

    # Extension 1: Is_Still_In_MD
    df = add_is_still_in_md(df, timeline)

    # Extension 3: Company_Size_Tier
    df = add_company_size_tier(df)

    # Write output
    df = write_output(df)

    # Summary
    print_change_summary(before_df, df, stats)


if __name__ == "__main__":
    main()
