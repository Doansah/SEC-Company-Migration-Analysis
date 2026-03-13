import os
import pandas as pd

# -------------------------
# Config
# -------------------------
DATA_DIR = "sec_financial_statements"

# Excel file containing the CIK list you want to filter to
CIK_EXCEL_PATH = "maryland_ciks.xlsx"   # <-- change to your filename
CIK_SHEET_NAME = None                  # None = first sheet; or set e.g. "Sheet1"
CIK_COLUMN_NAME = "CIK"                # <-- change if your column is named differently

# Outputs
OUT_TIMELINE = "company_hq_timeline_filtered.xlsx"
OUT_MIGRATIONS_ALL = "all_hq_migrations_filtered.xlsx"
OUT_MIGRATIONS_MD = "maryland_hq_migrations_filtered.xlsx"

# -------------------------
# Helpers
# -------------------------
def normalize_cik(x: str) -> str:
    """
    SEC CIK normalization:
    - keep digits only
    - zero-pad to 10 digits
    """
    if pd.isna(x):
        return ""
    s = "".join(ch for ch in str(x) if ch.isdigit())
    return s.zfill(10) if s else ""

def load_cik_allowlist(path: str, sheet_name=None, cik_col="CIK") -> set[str]:
    # If sheet_name is None, read the first sheet
    sheet_to_read = 0 if sheet_name is None else sheet_name
    df = pd.read_excel(path, sheet_name=sheet_to_read)
    if cik_col not in df.columns:
        raise ValueError(
            f"CIK column '{cik_col}' not found. Columns present: {list(df.columns)}"
        )
    ciks = df[cik_col].apply(normalize_cik)
    ciks = set(ciks[ciks != ""])
    if not ciks:
        raise ValueError("No valid CIKs found after normalization.")
    return ciks

# -------------------------
# Load allowlist of CIKs
# -------------------------
allow_ciks = load_cik_allowlist(CIK_EXCEL_PATH, sheet_name=CIK_SHEET_NAME, cik_col=CIK_COLUMN_NAME)
print(f"Loaded {len(allow_ciks):,} CIKs from {CIK_EXCEL_PATH}")

# -------------------------
# Parse sub.txt files
# -------------------------
records = []
print("Parsing SEC quarterly datasets (sub.txt)...")

for root, _, files in os.walk(DATA_DIR):
    if "sub.txt" not in files:
        continue

    file_path = os.path.join(root, "sub.txt")

    try:
        df = pd.read_csv(
            file_path,
            sep="\t",
            dtype=str,
            usecols=["cik", "name", "period", "cityba", "stprba"],
            engine="python",
        )
    except Exception as e:
        print(f"Skipping {file_path}: {e}")
        continue

    # Normalize CIK and filter early to keep memory small
    df["cik"] = df["cik"].apply(normalize_cik)
    df = df[df["cik"].isin(allow_ciks)]

    if df.empty:
        continue
    
    # Rename columns for consistency
    df = df.rename(columns={"cityba": "city", "stprba": "state"})

    # Year from period (YYYYMMDD -> YYYY)
    df["year"] = df["period"].str.slice(0, 4)

    # Keep only relevant columns
    df = df[["cik", "name", "year", "period", "city", "state"]]
    records.append(df)

if not records:
    raise RuntimeError(
        "No matching rows found for your CIK list. "
        "Double-check the Excel CIK column and that DATA_DIR is correct."
    )

print("Combining filtered quarterly data...")
master_df = pd.concat(records, ignore_index=True)

# -------------------------
# Collapse to yearly resolution
# Keep the latest record per (CIK, year) using 'period'
# -------------------------
master_df = master_df.sort_values(["cik", "year", "period"])
master_df = master_df.drop_duplicates(subset=["cik", "year"], keep="last")

# Clean timeline view
timeline_df = master_df[["cik", "name", "year", "city", "state"]].copy()
timeline_df = timeline_df.sort_values(["cik", "year"])

# -------------------------
# Detect migrations year-over-year per company
# -------------------------
print("Detecting HQ migrations (state changes year-over-year)...")

migration_events = []
for cik, group in timeline_df.groupby("cik", sort=False):
    group = group.sort_values("year")

    prev_state = None
    for _, row in group.iterrows():
        cur_state = row["state"]
        cur_year = row["year"]

        # Record when state changes (ignore blank/missing)
        if prev_state and cur_state and cur_state != prev_state:
            migration_events.append(
                {
                    "CIK": cik,
                    "Company": row["name"],
                    "Move_Year": cur_year,
                    "From_State": prev_state,
                    "To_State": cur_state,
                }
            )
        if cur_state:
            prev_state = cur_state

migration_df = pd.DataFrame(migration_events)

# If there are no migrations, still write outputs cleanly
if migration_df.empty:
    print("No migrations detected for the provided CIK list in the available time range.")

# Maryland-related migrations
maryland_moves = migration_df[
    (migration_df["From_State"] == "MD") | (migration_df["To_State"] == "MD")
].copy() if not migration_df.empty else pd.DataFrame(columns=["CIK","Company","Move_Year","From_State","To_State"])

# -------------------------
# Save outputs
# -------------------------
print("Saving Excel outputs...")
timeline_df.rename(columns={"cik": "CIK", "name": "Company", "year": "Year", "city": "City", "state": "State"}).to_excel(
    OUT_TIMELINE, index=False
)
migration_df.to_excel(OUT_MIGRATIONS_ALL, index=False)
maryland_moves.to_excel(OUT_MIGRATIONS_MD, index=False)

print("Done.")
print(f"Wrote: {OUT_TIMELINE}")
print(f"Wrote: {OUT_MIGRATIONS_ALL}")
print(f"Wrote: {OUT_MIGRATIONS_MD}")
