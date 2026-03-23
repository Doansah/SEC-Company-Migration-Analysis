# MASTER_DATASET.xlsx - V2 Documentation

## Overview

V2 of the Master Dataset fixes 5 data quality issues from V1 and adds 3 new columns. The dataset remains a single flat Excel file designed for Power BI, with each row representing one **company-event**.

**Output:** `analysis/v2_outputs/MASTER_DATASET.xlsx` (single sheet: "Master")
**V2 Generated:** 2026-03-18
**Row count:** 88 rows across 61 unique companies
**Column count:** 31 (up from 28 in V1)

---

## What Changed from V1

### Issue 1: Financial_Data_Available Flag Fixed
- **Problem:** 4 rows had `Financial_Data_Available = True` but no market cap, stock price, or shares data
- **Fix:** Set to `False` when all three of Market_Cap_At_Event, Stock_Price_At_Event, and Shares_Outstanding_At_Event are null
- **Result:** 4 flags corrected. 32 rows with shares-only data got explanatory notes.

### Issue 2: Missing Market Caps Partially Filled
- **Problem:** 28 MAJOR exchange rows had no Market_Cap_At_Event
- **Fix:** Added known ticker mappings for 14 companies, then queried yfinance for historical prices
- **Result:** 3 additional market caps populated (BURTECH, PETLIFE, RAND WORLDWIDE). 25 remain null — mostly delisted/acquired companies where yfinance has no historical data.
- **Tickers:** Increased from 34 to 60 populated (added known tickers for Legg Mason=LM, GSE Systems=GVP, TESSCO=TESS, U.S. Silica=SLCA, Terraform Power=TERP, Terraform Global=GLBL, Enviva=EVA, etc.)

### Issue 3: Market_Cap_Current Populated
- **Problem:** All 88 rows had null Market_Cap_Current
- **Fix:** Used yfinance `fast_info.market_cap` for companies with tickers that are still publicly traded
- **Result:** 35 rows populated. Skipped for attrition/acquired companies (18 rows). 30 rows have no ticker or yfinance returned no data.

### Issue 4: Origin_Subtype Reclassified
- **Problem:** All 37 origins were classified as `IPO_IN_MD` — incorrect for established companies like Legg Mason and Under Armour
- **Root cause:** The timeline only starts 2014/2015, so pre-existing companies had no earlier records to check
- **Fix:** Queried SEC EDGAR Submissions API for each origin company's earliest filing date. If `filings.files` is non-empty (1000+ filings) or earliest filing is before 2015, classified as `FIRST_APPEARANCE`.
- **Result:** 32 reclassified to `FIRST_APPEARANCE`, 5 remain `IPO_IN_MD` (true new companies since 2015)
- **Cached:** Results in `analysis/v2_outputs/cache/sec_earliest_filings.json`

### Issue 5: Foreign Arrival Counterparts Fixed
- **Problem:** SLINGER BAG (CIK 1674440) and PLANET GREEN (CIK 1117057) had null Counterpart_State
- **Fix:** Both are foreign companies; set `Counterpart_State = "FOREIGN"` and `Counterpart_City` to their pre-MD city
- **Result:**
  - SLINGER BAG: FOREIGN / PRAGUE (Czech Republic)
  - PLANET GREEN: FOREIGN / SHANGHAI (China)

---

## New Columns Added (3)

### Is_Still_In_MD (boolean)
- `True` if the company has NO relocation or attrition event (still headquartered in MD)
- `False` if the company has a `RELOCATION_DEPARTURE` or `ATTRITION` event
- Applied to ALL rows for a given CIK (a company with ORIGIN + DEPARTURE gets False on both rows)
- **Distribution:** 34 True, 54 False

### Attrition_Reason (string, nullable)
- Only populated for `Event_Type = ATTRITION` rows
- **Classified values:**
  - `ACQUIRED` — LEGG MASON (Franklin Templeton), HAMILTON BANCORP (Severn Bancorp), TERRAFORM GLOBAL (Brookfield)
  - `BANKRUPTCY` — ENVIVA PARTNERS
  - `UNKNOWN` — GSE SYSTEMS, TESSCO TECHNOLOGIES, HEALTHCARE SERVICES ACQUISITION CORP, VIEW SYSTEMS, RAND WORLDWIDE (5 companies awaiting user classification)

### Company_Size_Tier (string)
Based on `Market_Cap_At_Event`:
| Tier | Threshold | Count |
|------|-----------|-------|
| `LARGE_CAP` | >$10B | 0 |
| `MID_CAP` | $2B–$10B | 2 |
| `SMALL_CAP` | $300M–$2B | 4 |
| `MICRO_CAP` | <$300M | 28 |
| `UNKNOWN` | No market cap | 54 |

---

## Script Created: `pipeline/enrich_master_dataset.py`

**Purpose:** Standalone enrichment script that reads the existing MASTER_DATASET.xlsx, applies all fixes and extensions, and writes the updated file. Isolates API-dependent logic from the regeneration pipeline.

**Data Sources:**
- **SEC EDGAR Submissions API** (`data.sec.gov/submissions/`) — earliest filing dates for origin classification, ticker lookup
- **yfinance** — historical stock prices (Issue 2), current market caps (Issue 3)

**Functions:**
| Function | Purpose |
|----------|---------|
| `fix_financial_data_flag(df)` | Issue 1: Correct inconsistent True flags |
| `fix_missing_counterparts(df, timeline)` | Issue 5: Fill foreign company origins |
| `fix_origin_subtypes(df)` | Issue 4: Reclassify via SEC EDGAR API |
| `fill_missing_market_caps(df)` | Issue 2: yfinance historical prices |
| `add_attrition_reason(df)` | Extension 2: Hardcoded + UNKNOWN |
| `fill_current_market_caps(df)` | Issue 3: yfinance current market cap |
| `add_is_still_in_md(df, timeline)` | Extension 1: Departure status flag |
| `add_company_size_tier(df)` | Extension 3: Market cap classification |

**Caching:** API results are cached in `analysis/v2_outputs/cache/` to avoid redundant calls on re-runs:
- `sec_earliest_filings.json` — CIK → earliest filing year (Issue 4)
- `enriched_market_caps.json` — CIK → market cap data (Issue 2)
- `current_market_caps.json` — CIK → current market cap (Issue 3)

**Runtime:** ~90 seconds (dominated by yfinance API calls)

---

## Script Modified: `pipeline/build_master_dataset.py`

**Changes for V2:**
1. **`classify_origins()`** — Now reads cached SEC filing dates from `cache/sec_earliest_filings.json` to correctly distinguish `IPO_IN_MD` from `FIRST_APPEARANCE`. Falls back to timeline heuristic if cache is unavailable.
2. **`enrich_with_financials()`** — Fixed `Financial_Data_Available` logic to check Market_Cap, Stock_Price, and Shares (not Revenue) for the flag.
3. **Schema** — Added `Company_Size_Tier`, `Is_Still_In_MD`, and `Attrition_Reason` columns to the output. Column order updated from 28 to 31 columns.

---

## Updated Output Schema (31 columns)

### Identity Columns (6)
| Column | Description |
|--------|-------------|
| `CIK` | 10-digit zero-padded SEC Central Index Key (stored as text) |
| `Company` | Company name from first MD appearance in timeline |
| `Ticker` | Stock ticker (populated for 60/88 rows in V2, up from 34 in V1) |
| `SIC` | 4-digit SIC code (zero-padded) |
| `SIC_Description` | Industry name from SIC lookup |
| `Sector` | 12-sector rollup |

### Location Columns (5)
| Column | Description |
|--------|-------------|
| `City` | City from SEC filing at time of event |
| `State` | Always "MD" |
| `Is_Baltimore_Region` | True if city is in the 86-city Baltimore metro lookup |
| `Counterpart_State` | For arrivals: origin state (or "FOREIGN"). For relocations: destination. Null for origins/attritions |
| `Counterpart_City` | City-level counterpart |

### Event Columns (7)
| Column | Description |
|--------|-------------|
| `Event_Type` | `ORIGIN`, `ARRIVAL`, `RELOCATION_DEPARTURE`, or `ATTRITION` |
| `Event_Year` | Year the event occurred |
| `Origin_Subtype` | `IPO_IN_MD` (5) or `FIRST_APPEARANCE` (32) — fixed in V2 |
| `Departure_Subtype` | `RELOCATED`, `ESTABLISHED_ATTRITION`, or `RECENT_ATTRITION` |
| `First_MD_Year` | First year this company appeared in Maryland |
| `Last_MD_Year` | Last year this company appeared in Maryland |
| `Years_In_MD` | Calculated: Last_MD_Year - First_MD_Year + 1 |

### Financial Columns (8)
| Column | Description |
|--------|-------------|
| `Market_Cap_At_Event` | Market cap at or near event date (34/88 populated) |
| `Market_Cap_At_Event_CPI_Adjusted` | CPI-adjusted to 2024 dollars |
| `Stock_Price_At_Event` | Share price used for market cap calculation |
| `Shares_Outstanding_At_Event` | Shares outstanding from 10-K or yfinance |
| `Market_Cap_Current` | Current market cap from yfinance (35/88 populated in V2) |
| `Exchange_Tier` | `MAJOR` or `NOT_TRADED` |
| `Financial_Data_Available` | True if market/price/shares data exists — corrected in V2 |
| `Company_Size_Tier` | `LARGE_CAP`, `MID_CAP`, `SMALL_CAP`, `MICRO_CAP`, or `UNKNOWN` (new in V2) |

### Status Columns (2) — New in V2
| Column | Description |
|--------|-------------|
| `Is_Still_In_MD` | True if company has not departed/attrited; False otherwise |
| `Attrition_Reason` | `ACQUIRED`, `BANKRUPTCY`, or `UNKNOWN` (attrition rows only) |

### Metadata Columns (3)
| Column | Description |
|--------|-------------|
| `Data_Source` | `SEC_TIMELINE`, `MIGRATION_DETECTION`, or `ATTRITION_ANALYSIS` |
| `Verification_Status` | All `UNVERIFIED` |
| `Notes` | Explanatory notes for edge cases (32 rows annotated in V2) |

---

## V2 Summary Statistics

| Metric | V1 | V2 | Change |
|--------|----|----|--------|
| Total rows | 88 | 88 | — |
| Columns | 28 | 31 | +3 |
| Unique companies | 61 | 61 | — |
| Origins (IPO_IN_MD) | 37 | 5 | -32 reclassified |
| Origins (FIRST_APPEARANCE) | 0 | 32 | +32 reclassified |
| Arrivals | 24 | 24 | — |
| Relocation Departures | 18 | 18 | — |
| Attritions | 9 | 9 | — |
| Tickers populated | 34 | 60 | +26 |
| Market caps (at event) | 31 | 34 | +3 |
| Market caps (current) | 0 | 35 | +35 |
| Financial_Data_Available True | 64 | 60 | -4 corrected |
| CPI adjustments | 28 | 31 | +3 |
| Null Counterpart_State (arrivals) | 2 | 0 | -2 fixed |

---

## How to Regenerate

```bash
# Step 1: Fetch financial profiles for arrivals (requires internet, ~2 minutes)
python pipeline/build_financial_profiles.py

# Step 2: Build the base master dataset (offline, ~5 seconds)
python pipeline/build_master_dataset.py

# Step 3: Enrich with fixes and extensions (requires internet, ~90 seconds)
python pipeline/enrich_master_dataset.py
```

Steps 1-2 produce the base dataset. Step 3 applies all V2 fixes (origin reclassification, missing market caps, current market caps, new columns). Step 3 caches API results so subsequent runs are faster.

---

## Remaining Issues & Future Work

1. **25 MAJOR exchange rows still missing Market_Cap_At_Event** — delisted/acquired companies where yfinance has no historical data. Manual data entry or alternative data sources needed.
2. **5 attrition companies need Attrition_Reason classification:** GSE Systems, TESSCO Technologies, Healthcare Services Acquisition Corp, View Systems, Rand Worldwide
3. **Verification_Status** remains `UNVERIFIED` for all rows
4. **Origin companies** (37) have limited financial data — a future extension to `build_financial_profiles.py` could cover them
5. **Exchange_Tier** is approximate — derived from financial profile classification, not actual exchange data
6. **Company names** are from the first MD timeline appearance, which may differ from current names
