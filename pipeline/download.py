import os
import requests
import zipfile
import io
import time

'''
Download All SEC Quartely Financial Statement Datasets

'''
BASE_URL = "https://www.sec.gov/files/dera/data/financial-statement-data-sets"
START_YEAR = 2015
END_YEAR = 2025

HEADERS = {
    "User-Agent": "Maryland-HQ-Migration-Research DillonOwusuAnsah research@example.com"
}

DATA_DIR = "sec_financial_statements"

os.makedirs(DATA_DIR, exist_ok=True)

for year in range(START_YEAR, END_YEAR + 1):
    for quarter in range(1, 5):

        dataset_name = f"{year}q{quarter}"
        url = f"{BASE_URL}/{dataset_name}.zip"

        print(f"Downloading {dataset_name}...")

        response = requests.get(url, headers=HEADERS)

        if response.status_code != 200:
            print(f"Skipping {dataset_name} (not available)")
            continue

        zip_path = os.path.join(DATA_DIR, f"{dataset_name}.zip")

        with open(zip_path, "wb") as f:
            f.write(response.content)

        print(f"Saved {zip_path}")

        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            z.extractall(os.path.join(DATA_DIR, dataset_name))

        print(f"Extracted {dataset_name}")

        time.sleep(0.5)

print("All downloads complete.")