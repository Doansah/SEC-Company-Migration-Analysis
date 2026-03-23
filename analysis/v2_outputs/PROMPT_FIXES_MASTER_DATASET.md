# Task: Fix Issues & Extend MASTER_DATASET.xlsx

## Context

We have a master dataset (`analysis/v2_outputs/MASTER_DATASET.xlsx`) for a Maryland corporate movement analysis project. It tracks 61 unique companies across 88 rows (one row per company-event) from 2015–2025 using SEC EDGAR data. The dataset is well-structured but has several data quality issues and needs a few new columns to be fully useful for Power BI visualization.

**Before you start coding, please:**
1. Read MASTER_DATASET.xlsx and confirm you can see the 88 rows / 28 columns
2. Read through the existing pipeline code and data files to understand what source data is available
3. Ask me for any files or data you can't locate
4. Confirm your plan before making changes

## Issue 1: Financial_Data_Available Flag is Inconsistent

**Problem:** 4 records have `Financial_Data_Available = True` but have NO market cap, NO stock price, AND NO shares outstanding. These should be `False`.

**Fix:** Set `Financial_Data_Available = False` for any row where ALL THREE of these are null: `Market_Cap_At_Event`, `Stock_Price_At_Event`, `Shares_Outstanding_At_Event`.

Additionally, for any row that has `Shares_Outstanding_At_Event` but no `Market_Cap_At_Event` and no `Stock_Price_At_Event` (like BURTECH ACQUISITION CORP), keep the flag as `True` but add a note in the `Notes` column explaining that market cap could not be calculated due to missing price data.

## Issue 2: 28 MAJOR Exchange Companies Missing Market Cap

**Problem:** 28 rows have `Exchange_Tier = MAJOR` but no `Market_Cap_At_Event`. Many of these are well-known companies where historical price data should be obtainable.

**What to do:**
- Print out a list of all 28 rows: Company, CIK, Event_Type, Event_Year, Ticker, Exchange_Tier
- For any of these where the Ticker is null, try to determine the ticker by searching the SEC EDGAR data or cross-referencing CIK numbers
- Ask me if I have historical price data available for these companies, or if I can provide it
- For companies that were acquired (like Legg Mason → Franklin Templeton in 2020), note that the last trading price before acquisition should be used
- Do NOT fabricate or estimate market cap values — only populate from verified data sources

## Issue 3: Market_Cap_Current is Completely Empty

**Problem:** 0 of 88 rows have `Market_Cap_Current` populated.

**What to do:**
- Identify which companies should have a current market cap (companies that are still publicly traded right now)
- Companies with `Event_Type = ATTRITION` should remain null
- Companies that were acquired should remain null
- Ask me for the source of current market cap data (Yahoo Finance export or similar)
- Do NOT fabricate values — flag which rows need current market cap and ask me for the data

## Issue 4: All Origins Incorrectly Classified as IPO_IN_MD

**Problem:** All 37 origins have `Origin_Subtype = IPO_IN_MD`. This is wrong. 25 of these have `Event_Year = 2014`, which is simply the first year of our dataset — not their actual IPO year. Companies like Legg Mason (founded 1899) and Tessco Technologies (public since the 1990s) were NOT IPOs in 2014; they just appeared in our data starting then.

**Fix logic:**
- `IPO_IN_MD` should ONLY be used for companies whose **actual first SEC filing ever** occurred during our study period (2015–2025) AND that first filing was from Maryland. These are true new public companies born in Maryland.
- `FIRST_APPEARANCE` should be used for companies that existed before our study period began but appeared in Maryland from the start of our data (2014/2015). These are established companies that were already in Maryland when we started tracking.

**How to determine this:**
- Check the SEC EDGAR data. Look at the earliest filing date for each origin company across ALL quarterly sub.txt files.
- If a company's earliest filing in any sub.txt file is from 2015 or later, AND it was in Maryland, it's a plausible `IPO_IN_MD`.
- If a company has filings prior to 2015 (or if its `Event_Year = 2014`, since our data starts in 2015 Q1 and 2014 likely represents the earliest period captured), it should be `FIRST_APPEARANCE`.
- When in doubt, check the raw SEC quarterly files in `data/sec/quarterly_raw_data/` — look at the earliest sub.txt file where each CIK appears.
- Ask me if you need help determining specific companies' actual IPO dates.

## Issue 5: Two Arrivals Have Null Counterpart_State

**Problem:** SLINGER BAG INC. (CIK 1674440, arrival 2021) and PLANET GREEN HOLDINGS CORP. (CIK 1117057, arrival 2019) have null `Counterpart_State` and `Counterpart_City`.

**Fix:**
- Check the migration data (`analysis/v2_outputs/02_migrations_detailed.xlsx`) for these CIKs to find their From_State
- Check the timeline data (`analysis/v2_outputs/01_timeline_with_sic.xlsx`) — look at what state they were in before their first Maryland appearance
- Populate `Counterpart_State` and `Counterpart_City` accordingly
- If truly undeterminable, leave as null but add a note explaining why

---

## Extension 1: Add `Is_Still_In_MD` Column

**Type:** Boolean

**Logic:**
- `True` if the company's most recent appearance in the timeline data is in Maryland AND the company has NOT had a departure or attrition event
- `False` if the company has an `Event_Type` of `RELOCATION_DEPARTURE` or `ATTRITION`
- For companies with multiple events (e.g., ORIGIN + RELOCATION_DEPARTURE), this should be `False` because they ultimately left
- For companies with only an ORIGIN or ARRIVAL event and no subsequent departure, this should be `True`

**Verification:** Cross-reference with `analysis/v2_outputs/01_timeline_with_sic.xlsx` — check the company's most recent year/state entry.

## Extension 2: Add `Attrition_Reason` Column

**Type:** String, nullable (only populated for ATTRITION event rows)

**Possible values:** `ACQUIRED`, `BANKRUPTCY`, `WENT_PRIVATE`, `DELISTED`, `UNKNOWN`

**The 9 attrition cases to classify:**
- LEGG MASON, INC. (Last MD: 2020) — was acquired by Franklin Templeton in 2020 → `ACQUIRED`
- HEALTHCARE SERVICES ACQUISITION CORP (Last MD: 2022) — this was a SPAC → needs investigation
- HAMILTON BANCORP, INC. (Last MD: 2018) — was acquired by Severn Bancorp → `ACQUIRED`
- VIEW SYSTEMS INC (Last MD: 2020) → needs investigation
- TERRAFORM GLOBAL, INC. (Last MD: 2017) — was acquired by Brookfield → `ACQUIRED`
- RAND WORLDWIDE INC (Last MD: 2015) → needs investigation
- GSE SYSTEMS INC (Last MD: 2024) → needs investigation
- ENVIVA PARTNERS, LP (Last MD: 2023) — filed for bankruptcy → `BANKRUPTCY`
- TESSCO TECHNOLOGIES INC (Last MD: 2023) — was acquired by TESSCO Technologies → needs investigation

**What to do:**
- For the ones I've identified above (Legg Mason, Hamilton Bancorp, Terraform Global, Enviva), populate directly
- For the others, search SEC EDGAR filings (check for 8-K filings about mergers/acquisitions, or SC TO-T tender offer filings) or ask me for clarification
- If you can't determine the reason from available data, set to `UNKNOWN` and ask me

## Extension 3: Add `Company_Size_Tier` Column

**Type:** String, nullable

**Based on `Market_Cap_At_Event`:**
- `LARGE_CAP` — Market cap > $10 billion
- `MID_CAP` — Market cap $2 billion to $10 billion
- `SMALL_CAP` — Market cap $300 million to $2 billion
- `MICRO_CAP` — Market cap < $300 million
- `UNKNOWN` — No market cap data available

**Logic:** Simple conditional based on `Market_Cap_At_Event`. If null, set to `UNKNOWN`.

---

## Output

- Overwrite `analysis/v2_outputs/MASTER_DATASET.xlsx` with the corrected and extended dataset
- The sheet should still be called `Master`
- Print a summary of all changes made: how many flags were corrected, how many origins reclassified, how many new columns added, etc.
- List any rows that still need attention (missing data you couldn't resolve) so I know what to follow up on

## Files You'll Need

- `analysis/v2_outputs/MASTER_DATASET.xlsx` — the file to fix
- `analysis/v2_outputs/01_timeline_with_sic.xlsx` — for verifying company histories
- `analysis/v2_outputs/02_migrations_detailed.xlsx` — for finding missing counterpart states
- `analysis/v2_outputs/MARYLAND_DEPARTURES_CONSOLIDATED.xlsx` — for cross-referencing departures
- `analysis/v2_outputs/attrition_analysis/03_attrition_classification.xlsx` — for attrition details
- `data/sec/quarterly_raw_data/` — raw SEC sub.txt files for determining actual first filing dates (Issue 4)

Ask me for any files you can't find or any data you need to complete the fixes.