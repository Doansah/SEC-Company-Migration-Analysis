"""
Build the MASTER_DATASET.xlsx consolidating all Maryland corporate migration data.

Each row = one company-event. Companies can have multiple rows
(e.g., ARRIVAL in 2017 + RELOCATION_DEPARTURE in 2022).

Output: analysis/v2_outputs/MASTER_DATASET.xlsx (single sheet: "Master")
"""

import os
import numpy as np
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2_OUTPUTS = os.path.join(BASE_DIR, "analysis", "v2_outputs")

# BLS CPI-U Annual Averages (base year 2024)
CPI_TABLE = {
    2015: 237.017,
    2016: 240.007,
    2017: 245.120,
    2018: 251.107,
    2019: 255.657,
    2020: 258.811,
    2021: 270.970,
    2022: 292.655,
    2023: 304.702,
    2024: 314.690,
    2025: 314.690,  # Use 2024 as proxy
}
CPI_BASE = CPI_TABLE[2024]


def load_data():
    """Load all source data files."""
    print("Loading data files...")

    timeline = pd.read_excel(os.path.join(V2_OUTPUTS, "01_timeline_with_sic.xlsx"))
    print(f"  Timeline: {len(timeline)} rows")

    migrations = pd.read_excel(os.path.join(V2_OUTPUTS, "02_migrations_detailed.xlsx"))
    print(f"  Migrations: {len(migrations)} rows")

    departures = pd.read_excel(
        os.path.join(V2_OUTPUTS, "MARYLAND_DEPARTURES_CONSOLIDATED.xlsx"),
        sheet_name="All_Departures",
    )
    print(f"  Departures: {len(departures)} rows")

    fin_departed = pd.read_excel(
        os.path.join(V2_OUTPUTS, "03_financial_profile_departed.xlsx")
    )
    print(f"  Financial (departed): {len(fin_departed)} rows")

    fin_arrivals_path = os.path.join(V2_OUTPUTS, "03_financial_profile_arrivals.xlsx")
    if os.path.exists(fin_arrivals_path):
        fin_arrivals = pd.read_excel(fin_arrivals_path)
        print(f"  Financial (arrivals): {len(fin_arrivals)} rows")
    else:
        fin_arrivals = pd.DataFrame()
        print("  Financial (arrivals): NOT FOUND — skipping")

    baltimore_cities = pd.read_excel(os.path.join(BASE_DIR, "City-County-Lookup.xlsx"))
    # Clean column names (has non-breaking spaces)
    baltimore_cities.columns = [c.strip().replace("\xa0", "") for c in baltimore_cities.columns]
    print(f"  Baltimore cities: {len(baltimore_cities)} entries")

    return timeline, migrations, departures, fin_departed, fin_arrivals, baltimore_cities


def build_baltimore_set(baltimore_cities):
    """Build a set of normalized Baltimore metro city names."""
    city_col = [c for c in baltimore_cities.columns if "city" in c.lower()][0]
    cities = set()
    for city in baltimore_cities[city_col].dropna():
        cities.add(str(city).strip().upper())
    return cities


def normalize_cik(cik):
    """Normalize CIK to 10-digit zero-padded string."""
    try:
        return str(int(float(cik))).zfill(10)
    except (ValueError, TypeError):
        return str(cik).zfill(10)


def get_md_company_info(timeline):
    """For each MD company, get first/last MD year and city at various years."""
    md_records = timeline[timeline["State"] == "MD"].copy()
    md_ciks = md_records["CIK"].unique()

    info = {}
    for cik in md_ciks:
        company_md = md_records[md_records["CIK"] == cik]
        company_all = timeline[timeline["CIK"] == cik]

        first_md_year = int(company_md["Year"].min())
        last_md_year = int(company_md["Year"].max())
        first_all_year = int(company_all["Year"].min())

        # City at first and last MD year
        first_md_row = company_md[company_md["Year"] == first_md_year].iloc[0]
        last_md_row = company_md[company_md["Year"] == last_md_year].iloc[0]

        info[cik] = {
            "company_name": first_md_row["Company"],
            "first_md_year": first_md_year,
            "last_md_year": last_md_year,
            "first_all_year": first_all_year,
            "first_md_city": first_md_row["City"],
            "last_md_city": last_md_row["City"],
            "sic": first_md_row.get("sic"),
            "sic_description": first_md_row.get("sic_description"),
            "sector_name": first_md_row.get("sector_name"),
        }

    return info


def classify_origins(timeline, md_info, departures_ciks, arrivals_ciks):
    """Classify ORIGIN events: companies whose first-ever appearance was in MD.

    Origin_Subtype logic:
    - IPO_IN_MD: Company's earliest SEC filing was 2015+ and in MD (true new company)
    - FIRST_APPEARANCE: Company existed before our study period (pre-2015) or has
      extensive filing history — they were already in MD when our data begins.

    Uses cached SEC EDGAR filing dates from analysis/v2_outputs/cache/sec_earliest_filings.json
    if available, otherwise falls back to timeline-only heuristic.
    """
    import json

    rows = []

    # Load cached earliest filing dates if available
    cache_path = os.path.join(V2_OUTPUTS, "cache", "sec_earliest_filings.json")
    filing_cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, "r") as f:
            filing_cache = json.load(f)

    for cik, info in md_info.items():
        # Skip companies that arrived from another state — they're ARRIVAL, not ORIGIN
        if cik in arrivals_ciks:
            continue

        # Check if first-ever appearance across ALL states was in MD
        company_all = timeline[timeline["CIK"] == cik]
        first_all = company_all.sort_values("Year").iloc[0]

        if first_all["State"] == "MD":
            # Determine subtype using SEC EDGAR filing history (cached)
            cik_str = str(cik)
            cached_entry = filing_cache.get(cik_str, {})
            earliest_year = cached_entry.get("earliest_year")
            has_older = cached_entry.get("has_older_files", False)

            if has_older:
                # 1000+ filings — definitely established pre-2015
                origin_subtype = "FIRST_APPEARANCE"
            elif earliest_year is not None and earliest_year < 2015:
                origin_subtype = "FIRST_APPEARANCE"
            elif earliest_year is not None and earliest_year >= 2015:
                origin_subtype = "IPO_IN_MD"
            elif info["first_md_year"] <= 2015:
                # No cached data, event at data boundary — likely pre-existing
                origin_subtype = "FIRST_APPEARANCE"
            else:
                # Fallback: check timeline for non-MD records before first MD year
                pre_md = company_all[
                    (company_all["Year"] < info["first_md_year"])
                    & (company_all["State"] != "MD")
                ]
                if len(pre_md) == 0:
                    origin_subtype = "IPO_IN_MD"
                else:
                    origin_subtype = "FIRST_APPEARANCE"

            rows.append({
                "CIK": cik,
                "Event_Type": "ORIGIN",
                "Event_Year": info["first_md_year"],
                "Origin_Subtype": origin_subtype,
                "Departure_Subtype": None,
                "City": info["first_md_city"],
                "State": "MD",
                "Counterpart_State": None,
                "Counterpart_City": None,
                "Data_Source": "SEC_TIMELINE",
            })

    return rows


def classify_arrivals(migrations, timeline):
    """Classify ARRIVAL events: companies that moved TO Maryland."""
    arrivals = migrations[migrations["To_State"] == "MD"]
    rows = []

    for _, mig in arrivals.iterrows():
        cik = mig["CIK"]
        from_state = mig["From_State"]
        move_year = int(mig["Move_Year"])

        # Get counterpart city: the company's city in the From_State before arrival
        company_records = timeline[
            (timeline["CIK"] == cik) & (timeline["State"] == from_state)
        ]
        if not company_records.empty:
            # Get the record closest to move_year (before)
            before = company_records[company_records["Year"] <= move_year]
            if not before.empty:
                counterpart_city = before.sort_values("Year").iloc[-1]["City"]
            else:
                counterpart_city = company_records.iloc[0]["City"]
        else:
            counterpart_city = None

        # Get the company's MD city at arrival
        md_records = timeline[
            (timeline["CIK"] == cik) & (timeline["State"] == "MD")
        ]
        if not md_records.empty:
            at_arrival = md_records[md_records["Year"] >= move_year]
            if not at_arrival.empty:
                city = at_arrival.sort_values("Year").iloc[0]["City"]
            else:
                city = md_records.iloc[-1]["City"]
        else:
            city = None

        rows.append({
            "CIK": cik,
            "Event_Type": "ARRIVAL",
            "Event_Year": move_year,
            "Origin_Subtype": None,
            "Departure_Subtype": None,
            "City": city,
            "State": "MD",
            "Counterpart_State": from_state if pd.notna(from_state) else None,
            "Counterpart_City": counterpart_city,
            "Data_Source": "MIGRATION_DETECTION",
        })

    return rows


def classify_departures(departures, timeline):
    """Classify RELOCATION_DEPARTURE and ATTRITION events."""
    rows = []

    for _, dep in departures.iterrows():
        cik = dep["CIK"]
        dep_type = dep["Departure_Type"]
        last_md_year = int(dep["Last_MD_Year"])

        # Get the company's last MD city
        md_records = timeline[
            (timeline["CIK"] == cik) & (timeline["State"] == "MD")
        ]
        if not md_records.empty:
            last_row = md_records.sort_values("Year").iloc[-1]
            city = last_row["City"]
        else:
            city = None

        if dep_type == "RELOCATION":
            event_type = "RELOCATION_DEPARTURE"
            departure_subtype = "RELOCATED"
            counterpart_state = dep["Destination_State"] if pd.notna(dep["Destination_State"]) else None

            # Get counterpart city from timeline (first appearance in destination state after departure)
            if counterpart_state:
                dest_records = timeline[
                    (timeline["CIK"] == cik) & (timeline["State"] == counterpart_state)
                ]
                if not dest_records.empty:
                    after = dest_records[dest_records["Year"] >= last_md_year]
                    if not after.empty:
                        counterpart_city = after.sort_values("Year").iloc[0]["City"]
                    else:
                        counterpart_city = dest_records.iloc[-1]["City"]
                else:
                    counterpart_city = None
            else:
                counterpart_city = None

            data_source = "MIGRATION_DETECTION"
        else:
            # ATTRITION
            event_type = "ATTRITION"
            # Use Status column for subtype (ESTABLISHED_ATTRITION or RECENT_ATTRITION)
            status = dep.get("Status", "")
            if "ESTABLISHED" in str(status).upper():
                departure_subtype = "ESTABLISHED_ATTRITION"
            elif "RECENT" in str(status).upper():
                departure_subtype = "RECENT_ATTRITION"
            else:
                departure_subtype = "ATTRITION"
            counterpart_state = None
            counterpart_city = None
            data_source = "ATTRITION_ANALYSIS"

        rows.append({
            "CIK": cik,
            "Event_Type": event_type,
            "Event_Year": last_md_year,
            "Origin_Subtype": None,
            "Departure_Subtype": departure_subtype,
            "City": city,
            "State": "MD",
            "Counterpart_State": counterpart_state,
            "Counterpart_City": counterpart_city,
            "Data_Source": data_source,
        })

    return rows


def enrich_with_identity(events_df, md_info, timeline):
    """Add identity columns: Company, SIC, SIC_Description, Sector."""
    companies = []
    sics = []
    sic_descs = []
    sectors = []

    for _, row in events_df.iterrows():
        cik_int = int(str(row["CIK"]).lstrip("0") or "0")
        info = md_info.get(cik_int, {})

        companies.append(info.get("company_name", ""))

        sic = info.get("sic")
        sic_desc = info.get("sic_description")
        sector = info.get("sector_name")

        # If not in md_info, try timeline directly
        if pd.isna(sic) or sic is None:
            tl_rows = timeline[timeline["CIK"] == cik_int]
            if not tl_rows.empty:
                row_with_sic = tl_rows.dropna(subset=["sic"])
                if not row_with_sic.empty:
                    sic = row_with_sic.iloc[0]["sic"]
                    sic_desc = row_with_sic.iloc[0]["sic_description"]
                    sector = row_with_sic.iloc[0]["sector_name"]

        sics.append(str(int(sic)).zfill(4) if pd.notna(sic) else None)
        sic_descs.append(sic_desc)
        sectors.append(sector)

    events_df["Company"] = companies
    events_df["SIC"] = sics
    events_df["SIC_Description"] = sic_descs
    events_df["Sector"] = sectors

    return events_df


def enrich_with_md_years(events_df, md_info):
    """Add First_MD_Year, Last_MD_Year, Years_In_MD."""
    first_years = []
    last_years = []
    years_in = []

    for _, row in events_df.iterrows():
        cik_int = int(str(row["CIK"]).lstrip("0") or "0")
        info = md_info.get(cik_int, {})
        fy = info.get("first_md_year")
        ly = info.get("last_md_year")
        first_years.append(fy)
        last_years.append(ly)
        if fy and ly:
            years_in.append(ly - fy + 1)
        else:
            years_in.append(None)

    events_df["First_MD_Year"] = first_years
    events_df["Last_MD_Year"] = last_years
    events_df["Years_In_MD"] = years_in

    return events_df


def enrich_with_baltimore(events_df, baltimore_set):
    """Add Is_Baltimore_Region flag."""
    events_df["Is_Baltimore_Region"] = events_df["City"].apply(
        lambda c: str(c).strip().upper() in baltimore_set if pd.notna(c) else False
    )
    return events_df


def enrich_with_financials(events_df, fin_departed, fin_arrivals):
    """Add financial columns from financial profile files."""
    # Build lookup: CIK -> financial data
    fin_lookup = {}

    # Departed financials
    for _, row in fin_departed.iterrows():
        cik = int(row["CIK"])
        fin_lookup[cik] = {
            "Market_Cap_At_Event": row.get("Market_Cap"),
            "Stock_Price_At_Event": row.get("Price"),
            "Shares_Outstanding_At_Event": row.get("Shares"),
            "Ticker": row.get("Ticker"),
            "Exchange_Tier": _classify_exchange(row.get("Financial_Class")),
            "Revenue": row.get("Revenue"),
            "Total_Assets": row.get("Total_Assets"),
            "Net_Income": row.get("Net_Income"),
            "Employees": row.get("Employees"),
        }

    # Arrival financials (may overwrite if same CIK appeared in both)
    if not fin_arrivals.empty:
        for _, row in fin_arrivals.iterrows():
            cik = int(row["CIK"])
            if cik not in fin_lookup:
                fin_lookup[cik] = {
                    "Market_Cap_At_Event": row.get("Market_Cap"),
                    "Stock_Price_At_Event": row.get("Price"),
                    "Shares_Outstanding_At_Event": row.get("Shares"),
                    "Ticker": row.get("Ticker"),
                    "Exchange_Tier": _classify_exchange(row.get("Financial_Class")),
                    "Revenue": row.get("Revenue"),
                    "Total_Assets": row.get("Total_Assets"),
                    "Net_Income": row.get("Net_Income"),
                    "Employees": row.get("Employees"),
                }

    # Apply to events
    tickers = []
    mcaps = []
    prices = []
    shares = []
    exchanges = []
    fin_available = []

    for _, row in events_df.iterrows():
        cik_int = int(str(row["CIK"]).lstrip("0") or "0")
        fin = fin_lookup.get(cik_int, {})

        ticker = fin.get("Ticker")
        tickers.append(ticker if pd.notna(ticker) else None)
        mcap = fin.get("Market_Cap_At_Event")
        mcaps.append(mcap if pd.notna(mcap) else None)
        price = fin.get("Stock_Price_At_Event")
        prices.append(price if pd.notna(price) else None)
        share = fin.get("Shares_Outstanding_At_Event")
        shares.append(int(share) if pd.notna(share) else None)
        exch = fin.get("Exchange_Tier")
        exchanges.append(exch)
        has_market_data = any(
            pd.notna(fin.get(k))
            for k in ["Market_Cap_At_Event", "Stock_Price_At_Event", "Shares_Outstanding_At_Event"]
        )
        has_revenue = pd.notna(fin.get("Revenue"))
        fin_available.append(has_market_data or has_revenue)

    events_df["Ticker"] = tickers
    events_df["Market_Cap_At_Event"] = mcaps
    events_df["Stock_Price_At_Event"] = prices
    events_df["Shares_Outstanding_At_Event"] = shares
    events_df["Exchange_Tier"] = exchanges
    events_df["Financial_Data_Available"] = fin_available

    return events_df


def _classify_exchange(financial_class):
    """Map Financial_Class to Exchange_Tier."""
    if pd.isna(financial_class) or financial_class is None:
        return None
    fc = str(financial_class).upper()
    if fc in ("MICRO", "SMALL", "MID", "LARGE", "MEGA"):
        return "MAJOR"  # If they have market cap data, likely traded
    if fc == "UNKNOWN":
        return "NOT_TRADED"
    return None


def apply_cpi_adjustment(events_df):
    """Add CPI-adjusted market cap column."""
    adjusted = []
    for _, row in events_df.iterrows():
        mcap = row.get("Market_Cap_At_Event")
        year = row.get("Event_Year")
        if pd.notna(mcap) and year in CPI_TABLE:
            adjusted.append(mcap * (CPI_BASE / CPI_TABLE[year]))
        else:
            adjusted.append(None)
    events_df["Market_Cap_At_Event_CPI_Adjusted"] = adjusted
    return events_df


def build_master_dataset():
    """Main function to build the master dataset."""
    timeline, migrations, departures, fin_departed, fin_arrivals, baltimore_cities = load_data()

    # Build supporting structures
    baltimore_set = build_baltimore_set(baltimore_cities)
    md_info = get_md_company_info(timeline)
    print(f"\nMaryland companies in timeline: {len(md_info)}")

    # Build sets for classification logic
    arrivals_md = migrations[migrations["To_State"] == "MD"]
    arrivals_ciks = set(arrivals_md["CIK"].unique())
    departures_ciks = set(departures["CIK"].unique())

    # Classify events
    print("\nClassifying events...")
    origin_rows = classify_origins(timeline, md_info, departures_ciks, arrivals_ciks)
    print(f"  Origins: {len(origin_rows)}")

    arrival_rows = classify_arrivals(migrations, timeline)
    print(f"  Arrivals: {len(arrival_rows)}")

    departure_rows = classify_departures(departures, timeline)
    reloc_count = sum(1 for r in departure_rows if r["Event_Type"] == "RELOCATION_DEPARTURE")
    attr_count = sum(1 for r in departure_rows if r["Event_Type"] == "ATTRITION")
    print(f"  Departures: {len(departure_rows)} ({reloc_count} relocations, {attr_count} attritions)")

    # Combine all events
    all_events = origin_rows + arrival_rows + departure_rows
    events_df = pd.DataFrame(all_events)
    print(f"\nTotal events before dedup: {len(events_df)}")

    # Deduplication on (CIK, Event_Type, Event_Year)
    events_df = events_df.drop_duplicates(subset=["CIK", "Event_Type", "Event_Year"])
    print(f"Total events after dedup: {len(events_df)}")

    # Normalize CIK to 10-digit zero-padded string
    events_df["CIK"] = events_df["CIK"].apply(normalize_cik).astype(str)

    # Enrich
    print("\nEnriching data...")
    events_df = enrich_with_identity(events_df, md_info, timeline)
    events_df = enrich_with_md_years(events_df, md_info)
    events_df = enrich_with_baltimore(events_df, baltimore_set)
    events_df = enrich_with_financials(events_df, fin_departed, fin_arrivals)
    events_df = apply_cpi_adjustment(events_df)

    # Add remaining columns
    events_df["Market_Cap_Current"] = None  # Populated by enrich_master_dataset.py
    events_df["Verification_Status"] = "UNVERIFIED"
    events_df["Notes"] = None

    # Company_Size_Tier based on Market_Cap_At_Event
    def _size_tier(mcap):
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

    events_df["Company_Size_Tier"] = events_df["Market_Cap_At_Event"].apply(_size_tier)

    # Is_Still_In_MD: False if company has a departure/attrition event
    departed_ciks_set = set()
    for _, row in events_df.iterrows():
        if row["Event_Type"] in ("RELOCATION_DEPARTURE", "ATTRITION"):
            departed_ciks_set.add(str(row["CIK"]))
    events_df["Is_Still_In_MD"] = ~events_df["CIK"].astype(str).isin(departed_ciks_set)

    # Attrition_Reason: null for non-attrition rows, UNKNOWN for attrition rows
    # (populated by enrich_master_dataset.py with actual values)
    events_df["Attrition_Reason"] = None
    events_df.loc[events_df["Event_Type"] == "ATTRITION", "Attrition_Reason"] = "UNKNOWN"

    # Reorder columns to match target schema
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
        "Is_Still_In_MD", "Attrition_Reason",
        # Metadata
        "Data_Source", "Verification_Status", "Notes",
    ]

    # Only include columns that exist
    final_cols = [c for c in column_order if c in events_df.columns]
    events_df = events_df[final_cols]

    # Sort by Event_Year desc, then Event_Type
    type_order = {"ORIGIN": 0, "ARRIVAL": 1, "RELOCATION_DEPARTURE": 2, "ATTRITION": 3}
    events_df["_sort"] = events_df["Event_Type"].map(type_order)
    events_df = events_df.sort_values(["Event_Year", "_sort"], ascending=[False, True])
    events_df = events_df.drop(columns=["_sort"])

    # Ensure CIK is stored as text in Excel
    events_df["CIK"] = events_df["CIK"].astype(str)

    # Write output
    output_path = os.path.join(V2_OUTPUTS, "MASTER_DATASET.xlsx")
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        events_df.to_excel(writer, index=False, sheet_name="Master")
        # Format CIK column as text to prevent Excel from dropping leading zeros
        ws = writer.sheets["Master"]
        from openpyxl.styles import numbers
        for row in ws.iter_rows(min_row=2, min_col=1, max_col=1, max_row=ws.max_row):
            for cell in row:
                cell.number_format = numbers.FORMAT_TEXT

    # Summary
    print(f"\n{'='*60}")
    print(f"MASTER DATASET written to: {output_path}")
    print(f"Total rows: {len(events_df)}")
    print(f"Unique companies: {events_df['CIK'].nunique()}")
    print(f"\nEvent type breakdown:")
    print(events_df["Event_Type"].value_counts().to_string())
    print(f"\nBaltimore region: {events_df['Is_Baltimore_Region'].sum()} events")
    print(f"Financial data available: {events_df['Financial_Data_Available'].sum()} events")
    print(f"Market caps populated: {events_df['Market_Cap_At_Event'].notna().sum()} events")
    print(f"Tickers populated: {events_df['Ticker'].notna().sum()} events")

    return events_df


if __name__ == "__main__":
    build_master_dataset()
