# Task: Build Master Dataset Consolidation Script

## Context

I'm working on a Maryland corporate movement analysis project that tracks companies moving in and out of Maryland using SEC EDGAR data (2015–2025). Right now the analysis is spread across multiple Excel files and Python scripts, and every new question requires a new script. I need to consolidate everything into **one flat master Excel file** that can be plugged directly into Power BI for interactive exploration.

## What I Need You to Build

A Python script called `build_master_dataset.py` that reads my existing output files, merges them, and produces a single Excel file: `MASTER_DATASET.xlsx`.

**Before you start coding, please:**
1. Read through the files and directories listed below to understand the current data structures
2. Ask me any clarifying questions about missing data, ambiguous fields, or files you can't find
3. Confirm the schema with me before writing the script
4. Request any Excel sheets or data files you need that aren't already in the repo

## Existing Data Files to Read

Start by exploring these paths and understanding their structure (columns, row counts, data types):

### Core Analysis Outputs (in `analysis/v2_outputs/`)
- `01_timeline_with_sic.xlsx` — 31,504 rows, company-year records with SIC codes. Columns include: CIK, Company, Year, City, State, sic, sic_description, sector_name
- `02_migrations_detailed.xlsx` — 3,792 migration records. Columns include: CIK, Company, Move_Year, From_State, To_State, sic, sic_description, sector_name
- `04_industry_trends.xlsx` — Multi-sheet: MD companies by year, migrations by sector, net flows
- `05_destination_analysis.xlsx` — Multi-sheet: destinations from MD, origins to MD, by sector
- `MARYLAND_DEPARTURES_CONSOLIDATED.xlsx` — 27 departures (18 relocations + 9 attritions). Multiple sheets: All_Departures, Summary, Relocations_Only, Attritions_Only, By_Sector, By_Year

### Attrition Analysis (in `analysis/v2_outputs/attrition_analysis/`)
- `01_attrition_candidates.xlsx` — 43 gap candidates
- `03_attrition_classification.xlsx` — All 43 classified by type (RELOCATED, ESTABLISHED_ATTRITION, RECENT_ATTRITION, RECENT_DISAPPEARANCE, UNCLEAR_MIGRATION)
- `04_final_attrition_reconciliation.xlsx` — Summary + detailed breakdown

### Legacy/Reference (in `archive/v1_outputs/`)
- `company_hq_timeline_filtered.xlsx` — Original v1 timeline (31,504 rows)
- `all_hq_migrations_filtered.xlsx` — Original v1 migrations (3,792 rows)

### Supporting Data (in `data/sec/external/`)
- `cik_to_sic_mapping.csv` — 13,520 CIKs with SIC codes and sector names
- `sic_industry_names.csv` — 853 SIC codes mapped to sectors

### Baltimore Region City List
- I have a city list file for Baltimore metro area filtering — ask me for the exact path/filename

### Financial Data (Market Cap / Stock Prices)
- I have stock price and Yahoo Finance data for market cap — ask me for the exact path/filename and structure. The data includes stock prices nearest to event dates (departure or arrival), derived from latest 10-K data.

## Target Schema for MASTER_DATASET.xlsx

Each row = one company-event. Most companies have one row. A company that arrived and later departed gets two rows.

### Identity Columns
| Column | Type | Description |
|--------|------|-------------|
| `CIK` | string | SEC Central Index Key (10-digit, zero-padded) |
| `Company` | string | Official company name from SEC filings |
| `Ticker` | string (nullable) | Stock ticker symbol, if available |
| `SIC` | string | 4-digit SIC code |
| `SIC_Description` | string | Industry name |
| `Sector` | string | 12-sector rollup (Manufacturing, Finance, Services, etc.) |

### Location Columns
| Column | Type | Description |
|--------|------|-------------|
| `City` | string | City from SEC filing at time of event |
| `State` | string | State at time of event (always MD for this dataset) |
| `Is_Baltimore_Region` | boolean | Whether the city falls within Baltimore metro area |
| `Counterpart_State` | string (nullable) | For departures: destination state. For arrivals: origin state. For origins/attritions: null |
| `Counterpart_City` | string (nullable) | Same as above, city level if available |

### Event Columns
| Column | Type | Description |
|--------|------|-------------|
| `Event_Type` | string | One of: `ORIGIN`, `ARRIVAL`, `RELOCATION_DEPARTURE`, `ATTRITION` |
| `Event_Year` | int | Year the event occurred |
| `Origin_Subtype` | string (nullable) | For origins: `IPO_IN_MD` or `FIRST_APPEARANCE`. Null for non-origins. |
| `Departure_Subtype` | string (nullable) | For departures: `RELOCATED`, `ESTABLISHED_ATTRITION`, `RECENT_ATTRITION`. Null for non-departures. |
| `First_MD_Year` | int | First year this company appeared in Maryland in the data |
| `Last_MD_Year` | int | Last year this company appeared in Maryland |
| `Years_In_MD` | int | Calculated: Last_MD_Year - First_MD_Year + 1 |

### Financial Columns
| Column | Type | Description |
|--------|------|-------------|
| `Market_Cap_At_Event` | float (nullable) | Market cap nearest to event date |
| `Market_Cap_At_Event_CPI_Adjusted` | float (nullable) | CPI-adjusted to base year (use 2024 as base) |
| `Stock_Price_At_Event` | float (nullable) | Share price used for market cap calc |
| `Shares_Outstanding_At_Event` | int (nullable) | From 10-K filing |
| `Market_Cap_Current` | float (nullable) | Current market cap (null for attritions/delistings) |
| `Exchange_Tier` | string (nullable) | `MAJOR` (NYSE/NASDAQ), `OTC`, or `NOT_TRADED` |
| `Financial_Data_Available` | boolean | Whether any financial data exists for this company |

### Metadata Columns
| Column | Type | Description |
|--------|------|-------------|
| `Data_Source` | string | Where this record was derived from: `SEC_TIMELINE`, `MIGRATION_DETECTION`, `ATTRITION_ANALYSIS` |
| `Verification_Status` | string | `VERIFIED`, `UNVERIFIED`, or `FLAGGED` — default all to UNVERIFIED |
| `Notes` | string (nullable) | Free text for anything unusual |

## Logic for Classifying Events

### ORIGIN
- Company's **first-ever appearance** in the full timeline (across all states) is in Maryland
- `Origin_Subtype = IPO_IN_MD` if the company has no records in any other state before its first MD appearance
- `Origin_Subtype = FIRST_APPEARANCE` if we can't confirm it's a true IPO (just first time in our data)

### ARRIVAL
- Company appeared in another state **before** appearing in Maryland
- Identified via migration records where `To_State == 'MD'`
- `Counterpart_State` = the state they came from

### RELOCATION_DEPARTURE
- Company was in Maryland and moved to another state
- Identified via migration records where `From_State == 'MD'`
- `Departure_Subtype = RELOCATED`
- `Counterpart_State` = destination state

### ATTRITION
- Company was in Maryland and disappeared from all SEC filings
- Identified via the attrition classification analysis
- `Departure_Subtype = ESTABLISHED_ATTRITION` (3+ years gone) or `RECENT_ATTRITION` (1-2 years gone)
- `Counterpart_State` = null

## Important Implementation Notes

1. **Normalize CIK** to 10-digit zero-padded strings everywhere before joining
2. **Handle companies with multiple events** — a company that arrived in MD in 2017 and departed in 2022 should have TWO rows
3. **Financial columns** — populate what you can from the available data. Leave as null what we don't have yet. Ask me for the financial data file paths.
4. **Baltimore region** — ask me for the city list file path, then do case-insensitive matching with some fuzzy logic for common misspellings
5. **CPI adjustment** — use CPI data to adjust historical market caps to 2024 dollars. You can hardcode annual CPI values or ask me if I have a CPI table.
6. **Deduplication** — make sure the same company-event doesn't appear twice
7. **Output** — write to `analysis/v2_outputs/MASTER_DATASET.xlsx` with a single sheet called `Master`

## What to Ask Me

Before coding, please ask me for:
- The exact file path and column structure of my financial/market cap data
- The exact file path of my Baltimore region city list
- Any files you can't find at the expected paths
- Clarification on any ambiguous classification logic
- Whether I have CPI data available or if you should use standard BLS values
