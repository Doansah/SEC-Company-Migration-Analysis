"""
Build financial profiles for Maryland arrival companies.
Mirrors the schema of 03_financial_profile_departed.xlsx.

Data sources:
- SEC EDGAR API for company info, tickers, shares outstanding, and financial statements
- yfinance for stock prices nearest to event date

Output: analysis/v2_outputs/03_financial_profile_arrivals.xlsx
"""

import os
import time
import pandas as pd
import requests
import warnings

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2_OUTPUTS = os.path.join(BASE_DIR, "analysis", "v2_outputs")

SEC_HEADERS = {
    "User-Agent": "CompanyMigrationResearch research@example.com",
    "Accept-Encoding": "gzip, deflate",
}

# Market cap classification thresholds
def classify_market_cap(market_cap):
    if pd.isna(market_cap) or market_cap is None:
        return "Unknown"
    if market_cap < 50_000_000:
        return "Micro"
    elif market_cap < 300_000_000:
        return "Small"
    elif market_cap < 2_000_000_000:
        return "Mid"
    elif market_cap < 10_000_000_000:
        return "Large"
    else:
        return "Mega"


def get_sec_company_data(cik):
    """Fetch company data from SEC EDGAR submissions API."""
    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    try:
        resp = requests.get(url, headers=SEC_HEADERS, timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"  SEC API error for CIK {cik}: {e}")
    return None


def get_financial_facts(cik):
    """Fetch XBRL financial facts from SEC company facts API."""
    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
    try:
        resp = requests.get(url, headers=SEC_HEADERS, timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"  XBRL facts error for CIK {cik}: {e}")
    return None


def extract_financial_metric(facts, metric_names, target_year, unit_key="USD"):
    """Extract a financial metric value nearest to the target year from XBRL facts."""
    if not facts or "facts" not in facts:
        return None

    us_gaap = facts["facts"].get("us-gaap", {})

    for metric in metric_names:
        if metric not in us_gaap:
            continue
        units = us_gaap[metric].get("units", {})
        values = units.get(unit_key, [])
        if not values:
            continue

        # Filter for annual filings (10-K), prefer those near target_year
        annual = [v for v in values if v.get("form") in ("10-K", "10-K/A")]
        if not annual:
            annual = values

        # Find closest to target year
        best = None
        best_diff = float("inf")
        for v in annual:
            try:
                end = v.get("end", "")
                year = int(end[:4]) if end else 0
                diff = abs(year - target_year)
                if diff < best_diff:
                    best_diff = diff
                    best = v
            except (ValueError, TypeError):
                continue

        if best and best_diff <= 2:
            return best.get("val")

    return None


def extract_shares_outstanding(facts, target_year):
    """Extract shares outstanding from XBRL facts."""
    return extract_financial_metric(
        facts,
        [
            "CommonStockSharesOutstanding",
            "EntityCommonStockSharesOutstanding",
            "CommonStockSharesIssued",
            "WeightedAverageNumberOfShareOutstandingBasicAndDiluted",
        ],
        target_year,
        unit_key="shares",
    )


def get_stock_price_and_market_cap(ticker, target_year):
    """Get stock price and market cap using yfinance.

    Returns (price, price_date, market_cap, shares) tuple.
    Uses yfinance info for current market cap as a cross-check.
    For historical prices, fetches unadjusted data to avoid split distortion.
    """
    if not ticker or pd.isna(ticker):
        return None, None, None, None

    try:
        import yfinance as yf

        stock = yf.Ticker(ticker)

        # Get current info for market cap and shares (most reliable)
        info = stock.fast_info if hasattr(stock, "fast_info") else {}
        current_market_cap = getattr(info, "market_cap", None) if info else None
        current_shares = getattr(info, "shares", None) if info else None

        # Get historical price nearest to event year-end
        start_date = f"{target_year}-09-01"
        end_date = f"{target_year + 1}-03-31"
        hist = stock.history(start=start_date, end=end_date, auto_adjust=False)
        if hist.empty:
            hist = stock.history(start=f"{target_year}-01-01", end=f"{target_year + 1}-06-30", auto_adjust=False)

        price = None
        price_date = None
        if not hist.empty and "Close" in hist.columns:
            price = float(hist["Close"].iloc[-1])
            price_date = str(hist.index[-1].date())

        return price, price_date, current_market_cap, current_shares
    except Exception as e:
        print(f"  yfinance error for {ticker}: {e}")

    return None, None, None, None


def build_arrival_profiles():
    """Build financial profiles for all Maryland arrival companies."""
    print("Loading migration data...")
    migrations = pd.read_excel(os.path.join(V2_OUTPUTS, "02_migrations_detailed.xlsx"))
    arrivals = migrations[migrations["To_State"] == "MD"].copy()
    print(f"Found {len(arrivals)} arrival companies to Maryland")

    # Load timeline for sector info
    timeline = pd.read_excel(os.path.join(V2_OUTPUTS, "01_timeline_with_sic.xlsx"))

    results = []

    for _, row in arrivals.iterrows():
        cik = int(row["CIK"])
        company = row["Company"]
        arrival_year = int(row["Move_Year"])
        from_state = row["From_State"]
        sector = row["sector_name"] if pd.notna(row["sector_name"]) else "Other"

        print(f"\nProcessing: {company} (CIK {cik}, arrived {arrival_year} from {from_state})")

        # Query SEC EDGAR for company info
        time.sleep(0.15)  # Rate limit: 10 req/sec
        sec_data = get_sec_company_data(cik)

        ticker = None
        if sec_data:
            # Get ticker from SEC data
            tickers = sec_data.get("tickers", [])
            if tickers:
                ticker = tickers[0]
            elif sec_data.get("exchanges"):
                # Sometimes ticker is in a different field
                ticker = sec_data.get("ticker")
            print(f"  Ticker: {ticker}")

        # Get XBRL financial facts
        time.sleep(0.15)
        facts = get_financial_facts(cik)

        # Use arrival year as target for financial data
        data_year = arrival_year

        # Extract financial metrics
        revenue = extract_financial_metric(
            facts,
            ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
             "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax",
             "SalesRevenueGoodsNet"],
            data_year,
        )
        total_assets = extract_financial_metric(
            facts, ["Assets"], data_year
        )
        net_income = extract_financial_metric(
            facts,
            ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
            data_year,
        )
        employees = extract_financial_metric(
            facts,
            ["EntityNumberOfEmployees"],
            data_year,
            unit_key="pure" if facts and "pure" in str(facts) else "USD",
        )
        # Employees sometimes stored differently
        if employees is None and facts:
            employees = extract_financial_metric(
                facts, ["EntityNumberOfEmployees"], data_year, unit_key="employee"
            )

        # Get shares outstanding from XBRL
        shares = extract_shares_outstanding(facts, data_year)

        print(f"  Revenue: {revenue}, Assets: {total_assets}, NetIncome: {net_income}, Shares: {shares}")

        # Get stock price and market cap from yfinance
        price, price_date, yf_market_cap, yf_shares = get_stock_price_and_market_cap(ticker, arrival_year)
        print(f"  Price: {price} ({price_date}), yf_mcap: {yf_market_cap}, yf_shares: {yf_shares}")

        # Prefer yfinance shares if XBRL shares seem stale
        if yf_shares and shares:
            # If shares differ by more than 10x, prefer yfinance (likely post-split)
            ratio = max(shares, yf_shares) / max(min(shares, yf_shares), 1)
            if ratio > 10:
                print(f"  Share count mismatch (XBRL: {shares}, yf: {yf_shares}), using yfinance")
                shares = yf_shares
        elif yf_shares and not shares:
            shares = yf_shares

        # Calculate market cap with sanity checks
        market_cap = None
        if price and shares:
            calculated_mcap = shares * price
        else:
            calculated_mcap = None

        if calculated_mcap and yf_market_cap:
            # If calculated is more than 50x current yfinance market cap, it's likely
            # distorted by reverse splits. Use yfinance current as best estimate.
            if calculated_mcap > yf_market_cap * 50:
                print(f"  Calculated mcap ${calculated_mcap:,.0f} >> current ${yf_market_cap:,.0f}, using yfinance")
                market_cap = yf_market_cap
            else:
                market_cap = calculated_mcap
        elif calculated_mcap:
            # No yfinance comparison available — cap at $50B for these companies
            if calculated_mcap > 50_000_000_000:
                print(f"  WARNING: Market cap ${calculated_mcap:,.0f} seems unreasonable, setting to None")
                market_cap = None
            else:
                market_cap = calculated_mcap
        elif yf_market_cap:
            market_cap = yf_market_cap

        if market_cap:
            print(f"  Market Cap: ${market_cap:,.0f}")

        financial_class = classify_market_cap(market_cap)

        # Determine data quality
        has_financials = any(v is not None for v in [revenue, total_assets, net_income])
        has_market = market_cap is not None
        if has_financials and has_market:
            data_quality = "Complete"
        elif has_financials or has_market:
            data_quality = "Partial"
        else:
            data_quality = "Minimal"

        results.append({
            "CIK": cik,
            "Company": company,
            "Arrival_Year": arrival_year,
            "Event_Type": "Arrival",
            "Sector": sector,
            "Origin_State": from_state if pd.notna(from_state) else None,
            "Market_Cap": market_cap,
            "Ticker": ticker,
            "Shares": shares,
            "Price": price,
            "Price_Date": price_date,
            "Revenue": revenue,
            "Total_Assets": int(total_assets) if total_assets is not None else None,
            "Net_Income": int(net_income) if net_income is not None else None,
            "Employees": employees,
            "Financial_Class": financial_class,
            "Data_Year": data_year,
            "Data_Quality": data_quality,
        })

    df = pd.DataFrame(results)
    output_path = os.path.join(V2_OUTPUTS, "03_financial_profile_arrivals.xlsx")
    df.to_excel(output_path, index=False, engine="openpyxl")
    print(f"\n{'='*60}")
    print(f"Saved {len(df)} arrival profiles to {output_path}")
    print(f"Data quality: {df['Data_Quality'].value_counts().to_dict()}")
    print(f"Tickers found: {df['Ticker'].notna().sum()}/{len(df)}")
    print(f"Market caps: {df['Market_Cap'].notna().sum()}/{len(df)}")

    return df


if __name__ == "__main__":
    build_arrival_profiles()
