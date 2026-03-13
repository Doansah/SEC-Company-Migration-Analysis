# SEC Pipeline Rework Plan: Maryland Corporate Movement Analysis (2015-2025)

**Objective:** Analyze and understand corporate movements in/out of Maryland with focus on industry sectors, financial health, and destination patterns.

---

## Part 1: Directory Reorganization

### Current Structure Issues
- Raw data, scripts, and outputs mixed in root directory
- No clear separation between legacy and new pipeline
- Difficult to track which files are inputs vs. intermediates vs. outputs

### New Directory Structure
```
SEC Project/
├── archive/                                    # LEGACY (READ-ONLY)
│   ├── v1_analysis/
│   │   ├── cikAnalysis.py                     # Original script
│   │   ├── ANALYSIS_METHODOLOGY.md            # Original documentation
│   │   ├── maryland_ciks.xlsx                 # Input CIK list
│   │   └── v1_outputs/
│   │       ├── company_hq_timeline_filtered.xlsx
│   │       ├── all_hq_migrations_filtered.xlsx
│   │       └── maryland_hq_migrations_filtered.xlsx
│   └── ARCHIVE_README.md                      # Explains what's here & why
│
├── data/                                       # RAW DATA (INPUT ONLY)
│   ├── sec/
│   │   ├── quarterly_raw_data/                # Original SEC XBRL submission files
│   │   │   ├── 2015q1/ (num.txt, sub.txt, etc.)
│   │   │   ├── 2015q2/
│   │   │   └── ...2025q4/
│   │   └── metadata/                          # Company metadata
│   │       ├── company_facts.json             # From API
│   │       └── submissions.json               # From API
│   │
│   └── external/                              # Additional reference data
│       ├── cik_to_sic_mapping.csv             # CIK ↔ SIC code mapping (TBD)
│       ├── sic_industry_names.csv             # SIC descriptions
│       └── company_financial_metrics.csv      # Revenue, employees, etc. (TBD)
│
├── pipeline/                                  # NEW PIPELINE (SCRIPTS)
│   ├── v2_rework/                             # Version 2 pipeline
│   │   ├── __init__.py
│   │   ├── config.py                          # Config: paths, filters, parameters
│   │   ├── ingestion.py                       # Read & parse SEC files
│   │   ├── normalization.py                   # CIK norm, address cleanup
│   │   ├── enrichment.py                      # Add SIC, financial data
│   │   ├── transformation.py                  # Aggregation, migration logic
│   │   ├── validation.py                      # QA checks
│   │   └── main.py                            # Orchestration script
│   └── requirements.txt                       # Dependencies
│
├── analysis/                                  # OUTPUTS (GENERATED)
│   ├── v2_outputs/
│   │   ├── 01_timeline_with_sic.xlsx          # Timeline + industry info
│   │   ├── 02_migrations_detailed.xlsx        # Migrations with destinations
│   │   ├── 03_financial_profile_departed.xlsx # Revenue/metrics of departed cos.
│   │   ├── 04_industry_trends.xlsx            # SIC-level analysis
│   │   └── 05_destination_analysis.xlsx       # Where did they go?
│   └── reports/
│       ├── MARYLAND_CORPORATE_MOVEMENT_REPORT.md
│       └── FINDINGS_SUMMARY.md
│
├── notebooks/                                  # INTERACTIVE ANALYSIS (OPTIONAL)
│   └── exploratory_analysis.ipynb
│
├── PLAN.md                                    # This file
├── README.md                                  # Project overview (updated)
└── ANALYSIS_METHODOLOGY.md                    # Original methodology (reference)
```

---

## Part 2: Enhanced Analysis Plan

### Goal 1: Company Movement In/Out of Maryland (2015-2025)

**Approach:**
- Expand existing `maryland_hq_migrations_filtered.xlsx`
- Segment by direction:
  - **Arrivals:** Companies moving TO Maryland (in-migration)
  - **Departures:** Companies moving FROM Maryland (out-migration)
  - **Stable:** Companies remaining in Maryland entire period
- Calculate net flow by year

**Outputs:**
- Migration counts by year
- Growth/decline trends
- List of companies by movement type

---

### Goal 2: Industry Classification via SIC Codes

**Data Source:** SEC CIK-to-SIC mapping (from sub.txt `sic` column or external lookup)

**Approach:**

1. **Extract SIC Codes from SEC Data**
   - Sub.txt files contain `sic` column (4-digit code)
   - Map each CIK → Primary SIC code
   - Create lookup table: CIK → SIC → Industry Name

2. **Enrich Migration Data**
   - Join migration records with SIC mapping
   - Add columns: `SIC_Code`, `Industry_Name`, `Industry_Sector`
   
3. **Industry Categorization**
   - Group SIC codes into sectors (e.g., SIC 6000-6799 = Finance)
   - Create filtered analysis by sector
   - Identify which industries are leaving Maryland

**SIC Groupings to Analyze:**
```
1000-1999: Mining, Oil & Gas
2000-3999: Manufacturing
4000-4999: Transportation
5000-5999: Wholesale/Retail
6000-6999: Finance, Insurance, Real Estate
7000-7999: Services
8000-8999: Professional Services (Legal, Accounting, etc.)
9000-9999: Government/Non-profit
```

**Outputs:**
- Industry breakdown of migrations (SIC groupings)
- Top 10 SICs leaving Maryland
- Top 10 SICs arriving in Maryland
- Industry concentration analysis

---

### Goal 3: Financial Profile of Departed Companies

**Data Source:** SEC submission files + external financial metrics

**Approach:**

1. **Extract Financial Data from SEC Filings**
   - 10-K forms contain financial statements
   - Key metrics: Revenue (net sales), total assets, employees, net income
   - Extract year before departure and year of departure (if available)
   - Note: May require parsing form documents (complex); alternative: use SEC API

2. **Use External Dataset (TBD)**
   - Company Snapshot API / SEC Edgar data
   - Build CSV of: CIK → Revenue/Assets/Employees (most recent year available)
   - Or: Use annual 10-K data extracted by third parties

3. **Financial Profile Classification**
   - Categorize companies: Micro (< $10M), Small ($10M-$100M), Mid ($100M-$1B), Large (>$1B)
   - Analyze which size companies are leaving

4. **Financial Health Indicators**
   - Net income before departure (profitable vs. struggling?)
   - Revenue growth trend (declining revenues = more likely to leave?)
   - Asset efficiency metrics (if available)

**Outputs:**
- Financial profile of departed companies: avg revenue, assets, employees
- Comparison: Departed vs. Stayed (do struggling companies leave more?)
- Financial breakdown by industry sector
- Table: Top 20 companies by revenue that departed

---

### Goal 4: Destination Analysis (Attrition vs. Relocation)

**Three Categories:**

#### A. **Confirmed Relocations** (Companies moved to specific states)
- Method: Filter migrations where `To_State != null` and `To_State != "MD"`
- Analyze top destination states (TX, CA, FL, etc.)
- Identify patterns (tax havens, industry clusters)

**Outputs:**
- Top 10 destination states for departed companies
- Flow diagram: MD → Destination State

#### B. **Natural Attrition** (Companies that disappear - no relocation detected)
- Method: Identify CIKs that:
  - Have Maryland filing(s) in 2019-2021
  - No US filing after that (presumed dissolved, acquired, or ceased operations)
  - No detected migration to another US state
- Distinguish:
  - **Likely Dissolved/Merged:** No SEC filings in 3+ years
  - **Incomplete Data:** Company still exists but not in dataset (private, delisted, etc.)

**Outputs:**
- List of departed companies with no detected relocation
- Possible causes (merger, acquisition, dissolution)
- Cross-reference with news/SEC announcements if possible

#### C. **Delayed or Multi-Step Migrations**
- Method: Identify companies with intermediate states
  - MD → (intermediate state) → Final destination
- Track decision-making timeline

---

## Part 3: Implementation Roadmap

### Phase 1: Setup & Data Preparation (Week 1)
- [ ] Create directory structure
- [ ] Move legacy files to `archive/`
- [ ] Extract SIC codes from sub.txt files
- [ ] Create CIK-to-SIC lookup table
- [ ] Verify data completeness

### Phase 2: Pipeline Development (Weeks 2-3)
- [ ] Build `ingestion.py` (read SEC + external data)
- [ ] Build `enrichment.py` (add SIC + financial data)
- [ ] Build `transformation.py` (migration logic + goals 1-4)
- [ ] Build `validation.py` (QA checks)
- [ ] Build `main.py` (orchestration)

### Phase 3: Analysis & Reporting (Week 4)
- [ ] Generate 5 output files
- [ ] Create executive summary
- [ ] Document findings & insights
- [ ] Validate against original v1 pipeline

### Phase 4: Documentation & Archive (Week 5)
- [ ] Write README + PLAN documentation
- [ ] Create ARCHIVE_README explaining v1
- [ ] Prepare for version control / hand-off

---

## Part 4: Data Requirements & Gaps

### What We Have (from v1)
✅ SEC sub.txt files (2015q1-2025q4, 44 files)  
✅ Maryland CIK list (4,670 companies)  
✅ Basic location data (state, city)  

### What We Need to Acquire/Create

| Need | Source | Effort | Priority |
|------|--------|--------|----------|
| **CIK ↔ SIC Mapping** | SEC Edgar (sic column in sub.txt) | LOW | **HIGH** |
| **SIC Industry Names** | OSHA SIC manual / CSV lookup | LOW | **HIGH** |
| **Financial Metrics** | SEC Edgar API / Company Facts API | MEDIUM | **HIGH** |
| **Company Dissolution Data** | SEC EDGAR delisted companies | MEDIUM | MEDIUM |
| **Industry Sector Classification** | Custom grouping (see Goal 2) | LOW | **HIGH** |
| **Relocation News** | Google News API / press releases | MEDIUM | LOW |

---

## Part 5: Key Metrics to Track

### Output 1: Timeline with Industry
```
CIK | Company | Year | City | State | SIC_Code | Industry_Name | Industry_Sector
```

### Output 2: Migrations with Destinations
```
CIK | Company | Move_Year | From_State | To_State | SIC_Code | Industry_Sector | 
  Movement_Type (Relocation/Attrition) | Confidence_Score
```

### Output 3: Financial Profile of Departed
```
CIK | Company | Departure_Year | Revenue_Last_Filing | Total_Assets | Employees | 
  SIC_Code | Industry | Financial_Classification (Micro/Small/Mid/Large) | 
  Net_Income_Before_Departure | Reason_for_Departure (Relocation/Attrition/Unknown)
```

### Output 4: Industry Trends
```
SIC_Code | Industry_Name | Sector | Companies_Departing_2015_2025 | 
  Avg_Revenue | Avg_Employees | Top_Destination_State | Net_MD_Movement
```

### Output 5: Destination Analysis
```
Destination_State | Count_Arrivals | Top_Industries | Avg_Size_Class | 
  Avg_Revenue_Departed | Relocation_% | Dissolution_%
```

---

## Part 6: Success Criteria

✅ **Complete Directory Reorganization**
- Legacy data isolated in `archive/`
- New pipeline scripts in `pipeline/v2_rework/`
- Clear data flow: raw → processed → analysis

✅ **SIC Enrichment**
- 100% of migrating companies have SIC codes
- Industry-level trends identified
- Top 5 departing/arriving industries identified

✅ **Financial Analysis**
- Financial profiles of 80%+ of departed companies obtained
- Comparison: departed vs stayed (size, profitability)
- Identified whether financially struggling companies leave disproportionately

✅ **Destination & Attrition Analysis**
- 100% of departed companies classified: Relocation vs Attrition
- Top 5 destination states identified
- Companies with no detected relocation flagged for manual review

✅ **Deliverables**
- 5 Excel files with clean, analysis-ready data
- Executive summary report
- Code is modular, documented, reproducible

---

## Part 7: Assumptions & Constraints

**Assumptions:**
- Business address (stprba/cityba) is accurate HQ location
- SEC filings are authoritative; no cross-validation with other sources
- Financial data available from SEC (may be incomplete for older years)
- SIC codes remain stable (in reality, they change; we use primary SIC)

**Constraints:**
- No manual web scraping (regulatory/legal risk)
- Limited to publicly-filed SEC data (private companies excluded)
- Financial data only back to 2015 (earlier data may require 10-K document parsing)
- Destination addresses may not be tracked (we only know they left MD, not *where*)

---

## Next Steps

1. **Approve Plan** — Confirm direction, goals, deliverables
2. **Acquire Data** — Pull SIC codes, obtain financial metrics
3. **Build Pipeline** — Modular Python implementation
4. **Validate Output** — Compare against v1, manual spot-checks
5. **Report** — Executive summary + detailed findings

---

**Timeline:** 4-5 weeks  
**Team Size:** 1 (efficient, focused execution)  
**Complexity:** Medium (SIC enrichment straightforward; financial data may require API integration)
