# SEC Project: Maryland Corporate Movement Analysis (2015-2025)

**Status:** v2 Pipeline Development In Progress  
**Last Updated:** March 6, 2026

---

## Project Overview

Analysis of corporate headquarters movements in and out of Maryland over an 11-year period (2015-2025). Tracks companies by industry (SIC codes), financial profile, and destination state to understand migration patterns, attrition, and economic trends.

### Key Deliverables (v2)
1. **Timeline with Industry Data** — Company HQ locations + SIC codes
2. **Migration Details** — State transitions with destinations
3. **Financial Profiles** — Revenue, assets, employees of departed companies
4. **Industry Trends** — SIC-level analysis of migration patterns
5. **Destination Analysis** — Where companies relocated and why (relocation vs. attrition)

---

## Directory Structure

```
SEC Project/
├── archive/                          # Legacy v1 pipeline (READ-ONLY)
│   ├── v1_analysis/                 # Original scripts & documentation
│   │   ├── cikAnalysis.py
│   │   ├── ANALYSIS_METHODOLOGY.md
│   │   └── maryland_ciks.xlsx
│   ├── v1_outputs/                  # v1 Analysis outputs
│   │   ├── company_hq_timeline_filtered.xlsx
│   │   ├── all_hq_migrations_filtered.xlsx
│   │   └── maryland_hq_migrations_filtered.xlsx
│   └── ARCHIVE_README.md
│
├── data/                             # Raw data (INPUT)
│   ├── sec/
│   │   ├── quarterly_raw_data/      # 44 quarterly SEC submission files
│   │   │   ├── 2015q1/, 2015q2/, ... 2025q4/
│   │   │   └── Each contains: sub.txt, num.txt, pre.txt, tag.txt
│   │   └── metadata/                # SEC API examples
│   │       ├── CompanyFactsAPI_Example.json
│   │       └── SubmissionsAPI_Example.json
│   │
│   └── external/                    # External reference data (TBD)
│       ├── cik_to_sic_mapping.csv   # CIK ↔ SIC mapping
│       ├── sic_industry_names.csv   # SIC descriptions
│       └── company_financial_metrics.csv  # Revenue, employees, etc.
│
├── pipeline/                         # Analysis code
│   ├── v2_rework/                   # v2 Pipeline (MASTER)
│   │   ├── __init__.py              # Module init
│   │   ├── config.py                # Configuration & paths
│   │   ├── ingestion.py             # Read SEC files
│   │   ├── normalization.py         # CIK normalization, cleanup
│   │   ├── enrichment.py            # Add SIC, financial data
│   │   ├── transformation.py        # Aggregation, migration logic
│   │   ├── validation.py            # QA & validation
│   │   └── main.py                  # Orchestration
│   ├── download.py                  # Helper: download SEC data
│   ├── inspect_outputs.py           # Helper: inspect output files
│   └── requirements.txt             # Python dependencies
│
├── analysis/                         # Results and Reports
│   ├── v2_outputs/                  # Final analysis files
│   │   ├── 01_timeline_with_sic.xlsx
│   │   ├── 02_migrations_detailed.xlsx
│   │   ├── 03_financial_profile_departed.xlsx
│   │   ├── 04_industry_trends.xlsx
│   │   └── 05_destination_analysis.xlsx
│   └── reports/
│       ├── MARYLAND_CORPORATE_MOVEMENT_REPORT.md
│       └── FINDINGS_SUMMARY.md
│
├── notebooks/                       # Interactive Jupyter analysis (optional)
│   └── exploratory_analysis.ipynb
│
├── PLAN.md                          # Strategic plan (this rework)
├── ANALYSIS_METHODOLOGY.md          # v1 methodology explanation (reference)
├── README.md                        # This file
└── edgar-api-overview.pdf           # SEC EDGAR API reference

```

---

## Getting Started

### Prerequisites
- Python 3.8+
- Libraries: pandas, openpyxl, requests, numpy
- 500MB+ free disk space

### Setup Instructions

1. **Navigate to project directory**
   ```bash
   cd "c:\Users\dansah\OneDrive - GBC REGION INC\Desktop\SEC Project"
   ```

2. **Create virtual environment** (if not already created)
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r pipeline/requirements.txt
   ```

4. **Run v1 validation** (confirms data integrity)
   ```bash
   python pipeline/inspect_outputs.py
   ```

5. **Run v2 pipeline** (when ready)
   ```bash
   python pipeline/v2_rework/main.py
   ```

---

## Data Sources

### SEC EDGAR Files (Primary)
- **Format:** Tab-separated values (TSV), XBRL submissions
- **Period:** 2015 Q1 through 2025 Q4 (44 files)
- **Location:** `data/sec/quarterly_raw_data/{year}q{quarter}/`
- **Key File:** `sub.txt` (company submissions, contains CIK, company name, state, city, SIC code)

### External Data (To Be Acquired)
- **SIC Code Mappings:** From sec.gov or third-party provider
- **Financial Metrics:** SEC Edgar API, financial data vendors
- **Industry Classifications:** OSHA SIC manual or custom grouping

---

## Pipeline Phases

### Phase 1: Setup & Data Preparation ✅
- [x] Create directory structure
- [x] Move legacy files to archive
- [ ] Extract SIC codes from sub.txt
- [ ] Create CIK-to-SIC lookup

### Phase 2: Pipeline Development (In Progress)
- [ ] Build `ingestion.py` — Read SEC + external data
- [ ] Build `enrichment.py` — Add SIC + financial info
- [ ] Build `transformation.py` — Migration logic
- [ ] Build `validation.py` — QA checks
- [ ] Build `main.py` — Orchestration

### Phase 3: Analysis & Reporting
- [ ] Generate 5 output Excel files
- [ ] Create executive summary report
- [ ] Document findings

### Phase 4: Documentation & Validation
- [ ] Update README with results
- [ ] Validate against v1 pipeline
- [ ] Archive final code version

---

## Key Files & Purposes

| File/Directory | Purpose | Status |
|---|---|---|
| `PLAN.md` | Strategic plan for v2 rework | ✅ Complete |
| `archive/v1_analysis/` | Legacy pipeline & docs | ✅ Archived |
| `archive/v1_outputs/` | v1 Analysis results | ✅ Reference |
| `data/sec/quarterly_raw_data/` | Raw SEC XBRL files | ✅ In place |
| `pipeline/v2_rework/` | New v2 pipeline code | 🔨 Building |
| `analysis/v2_outputs/` | v2 Results (TBD) | ⏳ Pending |

---

## Development Workflow

### Starting a New Feature
1. Ensure you're in the activated virtual environment
2. Create feature branch (if using git): `git checkout -b feature/sic-enrichment`
3. Make changes in `pipeline/v2_rework/`
4. Test locally: `python pipeline/v2_rework/main.py --test`
5. Commit & push when complete

### Running Validation
```bash
python pipeline/v2_rework/validation.py
```

### Inspecting Outputs
```bash
python pipeline/inspect_outputs.py
```

---

## Key Goals of This Rework

✅ **Industry Analysis (SIC):** Identify which sectors are leaving/entering Maryland  
✅ **Financial Profiling:** Understand size & health of departed companies  
✅ **Destination Tracking:** Determine if companies relocated or dissolved  
✅ **Comprehensive Reporting:** 5 Excel files + Executive summary  
✅ **Data Quality:** Validation, confidence scoring, outlier detection  

---

## Contact & Questions

- **Project Owner:** [Your Name]
- **Documentation:** See PLAN.md for strategic details
- **Legacy Reference:** See archive/ARCHIVE_README.md for v1 info
- **Methodology:** See ANALYSIS_METHODOLOGY.md for technical details

---

## License & Version Control

**v2.0.0** — Initial rework (March 2026)  
Previous: **v1.0** (cikAnalysis.py, archived)

---

## Quick Reference: Output Files

### When ready, v2 will generate:

1. **01_timeline_with_sic.xlsx**
   - Company-year-location records + SIC codes
   - 31,500+ rows spanning 2015-2025

2. **02_migrations_detailed.xlsx**
   - All state changes + destinations + industry
   - 3,792+ migration events

3. **03_financial_profile_departed.xlsx**
   - Revenue, assets, employees of departing companies
   - Comparison: departed vs. stable

4. **04_industry_trends.xlsx**
   - SIC-level summary statistics
   - Sectors leaving vs. entering Maryland

5. **05_destination_analysis.xlsx**
   - Where companies relocated
   - Relocation patterns by state & industry

---

**Next Step:** Review PLAN.md for detailed technical roadmap →
