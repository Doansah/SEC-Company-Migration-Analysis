# MASTER_DATASET.xlsx - V1 Documentation

## Overview

The Master Dataset consolidates all Maryland corporate migration analysis (2015-2025) into a single flat Excel file designed for Power BI. Each row represents one **company-event** — a company that originated in, arrived to, relocated from, or attrited out of Maryland. Companies with multiple events (e.g., arrived in 2019, departed in 2023) have multiple rows.

**Output:** `analysis/v2_outputs/MASTER_DATASET.xlsx` (single sheet: "Master")
**V1 Generated:** 2026-03-18
**Row count:** 88 rows across 61 unique companies

---

## Scripts Created

### 1. `pipeline/build_financial_profiles.py`

**Purpose:** Fetch financial data for the 24 companies that arrived in Maryland, producing `03_financial_profile_arrivals.xlsx` to complement the existing `03_financial_profile_departed.xlsx`.

**Data Sources:**
- **SEC EDGAR Submissions API** (`data.sec.gov/submissions/`) — ticker symbols, company metadata
- **SEC XBRL Company Facts API** (`data.sec.gov/api/xbrl/companyfacts/`) — Revenue, Total Assets, Net Income, Employees, Shares Outstanding from 10-K filings
- **yfinance** — historical stock prices nearest to the arrival year

**Key Logic:**
- Identifies arrivals from `02_migrations_detailed.xlsx` where `To_State == 'MD'`
- For each company, queries two SEC API endpoints (with 150ms rate-limiting between calls)
- Extracts the closest financial metric to the arrival year (within +/- 2 years) from annual (10-K) filings
- Calculates Market Cap = Shares Outstanding x Stock Price
- Includes sanity checks for reverse-split distortion: if calculated market cap exceeds 50x the current yfinance market cap, falls back to yfinance's current value
- Classifies companies by market cap tier: Micro (<$50M), Small (<$300M), Mid (<$2B), Large (<$10B), Mega (>$10B)

**Output:** `analysis/v2_outputs/03_financial_profile_arrivals.xlsx` (24 rows, 18 columns)

**Results:**
| Metric | Count |
|--------|-------|
| Tickers found | 17/24 |
| Market caps populated | 16/24 |
| Complete data quality | 16/24 |
| Partial data quality | 8/24 |

**Known Limitation:** Historical market caps for micro-cap/OTC stocks that underwent reverse splits may use the current yfinance market cap as a proxy rather than the true historical value. These are best treated as estimates.

---

### 2. `pipeline/build_master_dataset.py`

**Purpose:** Read all existing analysis outputs, classify every Maryland company-event, merge financial data, and produce the single consolidated `MASTER_DATASET.xlsx`.

**Input Files Read:**

| File | Records | Purpose |
|------|---------|---------|
| `01_timeline_with_sic.xlsx` | 31,504 | Company-year location records across all states |
| `02_migrations_detailed.xlsx` | 3,792 | All detected state-to-state HQ migrations |
| `MARYLAND_DEPARTURES_CONSOLIDATED.xlsx` | 27 | Classified MD departures (relocations + attritions) |
| `03_financial_profile_departed.xlsx` | 27 | Financial data for departed companies |
| `03_financial_profile_arrivals.xlsx` | 24 | Financial data for arrival companies (new) |
| `City-County-Lookup.xlsx` | 86 | Baltimore metro region city list |

**Processing Pipeline:**

1. **Load** all source files
2. **Build MD roster** — identify all 61 unique CIKs that ever appeared in Maryland
3. **Classify events** into four types (see Event Classification below)
4. **Deduplicate** on (CIK, Event_Type, Event_Year)
5. **Normalize CIK** to 10-digit zero-padded string
6. **Enrich** with identity columns (Company name, SIC, Sector from timeline)
7. **Enrich** with MD tenure (First_MD_Year, Last_MD_Year, Years_In_MD)
8. **Enrich** with Baltimore region flag (case-insensitive city match against 86-city lookup)
9. **Enrich** with financial data (join on CIK to financial profile files)
10. **CPI-adjust** market caps to 2024 dollars using hardcoded BLS CPI-U annual averages
11. **Sort** by Event_Year descending, then Event_Type
12. **Write** to Excel with CIK formatted as text to preserve leading zeros

---

## Event Classification Logic

### ORIGIN (37 events)
- Company's **first-ever appearance** across all states in the timeline is in Maryland
- Companies that arrived via migration are excluded (they get ARRIVAL instead)
- **Origin_Subtype:**
  - `IPO_IN_MD` — no records in any other state before first MD appearance (all 37 in V1)
  - `FIRST_APPEARANCE` — appeared elsewhere before MD, but first record was MD (0 in V1)

### ARRIVAL (24 events)
- Company appeared in another state before moving to Maryland
- Sourced from migration records where `To_State == 'MD'`
- `Counterpart_State` = the state they came from
- `Counterpart_City` = their city in the origin state (nearest year before move)

### RELOCATION_DEPARTURE (18 events)
- Company was in Maryland and moved its HQ to another state
- Sourced from `MARYLAND_DEPARTURES_CONSOLIDATED.xlsx` where `Departure_Type == 'RELOCATION'`
- `Departure_Subtype` = `RELOCATED`
- `Counterpart_State` = destination state
- `Counterpart_City` = first city in destination state after departure

### ATTRITION (9 events)
- Company was in Maryland and disappeared from all SEC filings
- Sourced from departures file where `Departure_Type == 'ATTRITION'`
- **Departure_Subtype** derived from the `Status` column:
  - `ESTABLISHED_ATTRITION` — 3+ years without SEC filings (6 companies)
  - `RECENT_ATTRITION` — 1-2 years without filings (3 companies)
- `Counterpart_State` = null (company ceased filing, no destination)

---

## Output Schema (28 columns)

### Identity Columns
| Column | Description |
|--------|-------------|
| `CIK` | 10-digit zero-padded SEC Central Index Key (stored as text) |
| `Company` | Company name from first MD appearance in timeline |
| `Ticker` | Stock ticker from financial profiles (null if unavailable) |
| `SIC` | 4-digit SIC code (zero-padded) |
| `SIC_Description` | Industry name from SIC lookup |
| `Sector` | 12-sector rollup (Manufacturing, Finance, Services, etc.) |

### Location Columns
| Column | Description |
|--------|-------------|
| `City` | City from SEC filing at time of event |
| `State` | Always "MD" |
| `Is_Baltimore_Region` | True if city is in the 86-city Baltimore metro lookup |
| `Counterpart_State` | For arrivals: origin state. For relocations: destination. Null for origins/attritions |
| `Counterpart_City` | City-level counterpart (where available from timeline) |

### Event Columns
| Column | Description |
|--------|-------------|
| `Event_Type` | `ORIGIN`, `ARRIVAL`, `RELOCATION_DEPARTURE`, or `ATTRITION` |
| `Event_Year` | Year the event occurred |
| `Origin_Subtype` | `IPO_IN_MD` or `FIRST_APPEARANCE` (null for non-origins) |
| `Departure_Subtype` | `RELOCATED`, `ESTABLISHED_ATTRITION`, or `RECENT_ATTRITION` (null for non-departures) |
| `First_MD_Year` | First year this company appeared in Maryland |
| `Last_MD_Year` | Last year this company appeared in Maryland |
| `Years_In_MD` | Calculated: Last_MD_Year - First_MD_Year + 1 |

### Financial Columns
| Column | Description |
|--------|-------------|
| `Market_Cap_At_Event` | Market cap at or near event date (from financial profiles) |
| `Market_Cap_At_Event_CPI_Adjusted` | CPI-adjusted to 2024 dollars |
| `Stock_Price_At_Event` | Share price used for market cap calculation |
| `Shares_Outstanding_At_Event` | Shares outstanding from 10-K or yfinance |
| `Market_Cap_Current` | Null in V1 (reserved for future enrichment) |
| `Exchange_Tier` | `MAJOR` if market cap data exists, `NOT_TRADED` if unknown classification |
| `Financial_Data_Available` | True if any of Market_Cap, Stock_Price, or Revenue exists |

### Metadata Columns
| Column | Description |
|--------|-------------|
| `Data_Source` | `SEC_TIMELINE`, `MIGRATION_DETECTION`, or `ATTRITION_ANALYSIS` |
| `Verification_Status` | All set to `UNVERIFIED` in V1 |
| `Notes` | Null in V1 (available for manual annotation) |

---

## V1 Summary Statistics

| Metric | Value |
|--------|-------|
| Total rows | 88 |
| Unique companies | 61 |
| Origins | 37 |
| Arrivals | 24 |
| Relocation Departures | 18 |
| Attritions | 9 |
| Companies with multiple events | 27 |
| Baltimore Region events | 30 (34%) |
| Financial data available | 64 events (73%) |
| Market caps populated | 31 events (35%) |
| Tickers populated | 34 events (39%) |
| CPI adjustments applied | 28 events |

---

## CPI Adjustment Method

Market caps are adjusted to **2024 constant dollars** using BLS CPI-U annual averages:

```
Formula: Adjusted_Cap = Market_Cap x (CPI_2024 / CPI_event_year)

CPI-U Values Used:
2015: 237.017    2018: 251.107    2021: 270.970    2024: 314.690
2016: 240.007    2019: 255.657    2022: 292.655    2025: 314.690*
2017: 245.120    2020: 258.811    2023: 304.702
* 2025 uses 2024 value as proxy (full-year data not yet available)
```

---

## Dependencies

- Python 3.11+
- pandas, openpyxl (Excel read/write)
- requests (SEC EDGAR API calls)
- yfinance (stock price lookups — only needed for `build_financial_profiles.py`)
- numpy

---

## How to Regenerate

```bash
# Step 1: Fetch financial profiles for arrivals (requires internet, ~2 minutes)
python pipeline/build_financial_profiles.py

# Step 2: Build the master dataset (offline, ~5 seconds)
python pipeline/build_master_dataset.py
```

Step 1 only needs to be re-run if arrival companies change. Step 2 can be re-run anytime source files are updated.

---

## Known Limitations & Future Work

1. **Market_Cap_Current** is null for all rows — requires a separate enrichment pass with current stock data
2. **Verification_Status** is `UNVERIFIED` for all rows — manual review needed
3. **Exchange_Tier** is approximate — derived from market cap classification rather than actual exchange listing data
4. **Historical market caps for arrivals** may use current yfinance market cap as proxy when reverse splits distort historical calculations
5. **Origin companies** (37) have no financial data in V1 — a future `build_financial_profiles.py` extension could cover them
6. **Company names** are from the first MD timeline appearance, which may differ from the company's current or most recognizable name
7. **Notes** column is empty — available for manual annotation in Excel/Power BI
