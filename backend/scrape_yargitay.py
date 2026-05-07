"""
Yargıtay Karar Scraper - Parallel Multi-Session API Approach
=============================================================
Uses multiple HTTP sessions in parallel to bypass per-session rate limits.
Each worker gets its own session with its own cookies.
"""
import os
import re
import time
import json
import requests
from html import unescape
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# --- Configuration ---
OUTPUT_DIR = "yargıtaykarar"
RECORDS_FILE = os.path.join(OUTPUT_DIR, "_records.json")
BASE_URL = "https://karararama.yargitay.gov.tr"
PAGE_SIZE = 100
NUM_WORKERS = 10  # Number of parallel download sessions

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": BASE_URL,
    "Referer": BASE_URL + "/",
}

SEARCH_PARAMS = {
    "arananKelime": '"tck 243" "tck 244" "tck 245"',
    "esasYil": "",
    "esasIlkSiraNo": "",
    "esasSonSiraNo": "",
    "kararYil": "",
    "kararIlkSiraNo": "",
    "kararSonSiraNo": "",
    "baslangicTarihi": "01.04.2010",
    "bitisTarihi": "24.04.2026",
    "siralama": "1",
    "siralamaDirection": "desc",
    "birimYrgKurulDaire": "",
    "birimYrgHukukDaire": "",
    "birimYrgCezaDaire": "",
}

lock = threading.Lock()
counter = {"saved": 0, "errors": 0}


def html_to_text(html_str):
    """Convert HTML content to plain text."""
    if not html_str:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', html_str)
    text = re.sub(r'<p[^>]*>', '\n', text)
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def safe_filename(text):
    return re.sub(r'[\\/:*?"<>|]', '_', text)


def create_session():
    """Create a fresh session with its own cookies."""
    session = requests.Session()
    session.get(BASE_URL, headers={"User-Agent": HEADERS["User-Agent"]})
    return session


def fetch_all_records(session):
    """Fetch all record metadata from the search API."""
    if os.path.exists(RECORDS_FILE):
        print(f"Loading cached records from {RECORDS_FILE}...", flush=True)
        with open(RECORDS_FILE, "r", encoding="utf-8") as f:
            records = json.load(f)
        print(f"Loaded {len(records)} cached records.", flush=True)
        return records

    print("Initiating search...", flush=True)
    resp = session.post(f"{BASE_URL}/detayliArama", json={"data": SEARCH_PARAMS}, headers=HEADERS)
    if resp.status_code != 200:
        print(f"ERROR: Search initiation failed (HTTP {resp.status_code})")
        return []

    all_records = []
    page_number = 1
    while True:
        print(f"Fetching page {page_number} (offset {len(all_records)})...", flush=True)
        payload = {"data": {**SEARCH_PARAMS, "pageSize": PAGE_SIZE, "pageNumber": page_number}}

        for attempt in range(10):
            resp = session.post(f"{BASE_URL}/aramadetaylist", json=payload, headers=HEADERS)
            if resp.status_code != 429:
                break
            wait = min(2 ** attempt, 60)
            print(f"  Rate limited. Waiting {wait}s...", flush=True)
            time.sleep(wait)

        if resp.status_code != 200:
            break

        records = resp.json().get("data", {}).get("data", [])
        if not records:
            break

        all_records.extend(records)
        print(f"  Got {len(records)} records (total: {len(all_records)})", flush=True)

        if len(records) < PAGE_SIZE:
            break
        page_number += 1
        time.sleep(1)

    if all_records:
        with open(RECORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(all_records, f, ensure_ascii=False, indent=2)
        print(f"Cached {len(all_records)} records.", flush=True)

    return all_records


def download_single(record, total_to_download):
    """Download a single document. Each call creates its own session."""
    doc_id = record.get("id")
    daire = record.get("daire", "unknown")
    esas_no = record.get("esasNo", "unknown")
    karar_no = record.get("kararNo", "unknown")

    filename = safe_filename(f"{daire}_{esas_no}_{karar_no}") + ".txt"
    filepath = os.path.join(OUTPUT_DIR, filename)

    if os.path.exists(filepath):
        return "skip"

    session = create_session()

    for attempt in range(10):
        try:
            resp = session.get(f"{BASE_URL}/getDokuman", params={"id": doc_id}, headers=HEADERS, timeout=30)
            if resp.status_code == 429:
                wait = min(2 ** attempt, 120)
                time.sleep(wait)
                continue
            if resp.status_code == 200:
                doc_data = resp.json()
                html_content = doc_data.get("data")
                text_content = html_to_text(html_content) if html_content else ""
                if text_content:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(text_content)
                    with lock:
                        counter["saved"] += 1
                        print(f"  [{counter['saved']}/{total_to_download}] Saved: {filename}", flush=True)
                    return "saved"
            return "error"
        except Exception as e:
            time.sleep(min(2 ** attempt, 30))

    with lock:
        counter["errors"] += 1
    return "error"


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    session = create_session()

    # Phase 1: Get all records
    records = fetch_all_records(session)
    if not records:
        print("No records found.", flush=True)
        return

    # Filter out already downloaded
    to_download = []
    for r in records:
        fn = safe_filename(f"{r.get('daire','unknown')}_{r.get('esasNo','unknown')}_{r.get('kararNo','unknown')}") + ".txt"
        if not os.path.exists(os.path.join(OUTPUT_DIR, fn)):
            to_download.append(r)

    total = len(to_download)
    already = len(records) - total
    print(f"\nTotal records: {len(records)}", flush=True)
    print(f"Already downloaded: {already}", flush=True)
    print(f"Remaining to download: {total}", flush=True)
    print(f"Using {NUM_WORKERS} parallel workers\n", flush=True)

    # Phase 2: Download in parallel
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = {executor.submit(download_single, r, total): r for r in to_download}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"  Worker error: {e}", flush=True)

    print(f"\n{'='*50}", flush=True)
    print(f"Scraping complete!", flush=True)
    print(f"Saved: {counter['saved']}", flush=True)
    print(f"Errors: {counter['errors']}", flush=True)
    print(f"Output: {os.path.abspath(OUTPUT_DIR)}", flush=True)


if __name__ == "__main__":
    main()
