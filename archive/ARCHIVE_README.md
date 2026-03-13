# Archive - Version 1 Analysis

This directory contains the legacy v1 pipeline and outputs.

## Contents

### v1_analysis/
- **cikAnalysis.py** — Original pipeline script (working, but limited functionality)
- **ANALYSIS_METHODOLOGY.md** — Original documentation of methodology
- **maryland_ciks.xlsx** — Input CIK filter list (4,670 Maryland companies)

### v1_outputs/
- **company_hq_timeline_filtered.xlsx** — Timeline of HQ locations 2015-2025 (31,504 rows)
- **all_hq_migrations_filtered.xlsx** — All detected state-to-state migrations (3,792 rows)
- **maryland_hq_migrations_filtered.xlsx** — Maryland-specific migrations

## Why This Exists

The v1 pipeline successfully:
- ✅ Parsed all 44 quarterly SEC files (2015-2025)
- ✅ Filtered to 4,670 Maryland-based companies
- ✅ Generated company-state timeline
- ✅ Detected year-over-year state changes

**Limitations of v1 that v2 Addresses:**
- ❌ No industry (SIC code) analysis
- ❌ No financial profile of departed companies
- ❌ No destination tracking (where did they go?)
- ❌ No distinction between relocation vs. dissolution/attrition
- ❌ No data quality scoring or confidence metrics

## How to Use This Archive

- **Reference:** Review ANALYSIS_METHODOLOGY.md for detailed explanation of v1 logic
- **Validation:** Use v1 outputs to validate v2 pipeline (should produce same timeline/migrations)
- **Code Review:** Examine cikAnalysis.py as reference for simple, readable implementation
- **Do Not Modify:** This is read-only archive; all development in v2_rework

## Relation to v2 Rework

v2 pipeline will:
1. Read v1 outputs as intermediate data
2. Enrich with SIC codes, financial metrics, destination analysis
3. Generate 5 new comprehensive analysis files per PLAN.md

**Expected Timeline:** v2 outputs ready by Week 4 of rework schedule
