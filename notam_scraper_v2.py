import requests
import pandas as pd
import time
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
# Load environment variables (API Keys)
load_dotenv()
API_KEY = os.getenv("CHECKWX_API_KEY")

NOTAM_DB = "notam_reports_v2.csv"
POLL_INTERVAL = 1800  # 30 minutes (1800 seconds)

# Expanded keywords to catch 2026 reporting standards
EW_KEYWORDS = ["GPS", "GNSS", "JAMMING", "INTERFERENCE", "SPOOFING", "UNRELIABLE", "HAZARD"]

# Mapping major FIRs to coordinates for dashboard plotting (AOR: 10-38N, 32-60E)
FIR_COORDS = {
    "LCCC": {"lat": 35.0, "lon": 33.0}, # Nicosia (Cyprus)
    "OLBB": {"lat": 33.8, "lon": 35.5}, # Beirut (Lebanon)
    "LLLL": {"lat": 32.0, "lon": 34.8}, # Tel Aviv (Israel)
    "OSTT": {"lat": 33.5, "lon": 36.3}, # Damascus (Syria)
    "OJAC": {"lat": 31.9, "lon": 35.9}, # Amman (Jordan)
    "HECC": {"lat": 30.1, "lon": 31.4}, # Cairo (Egypt)
    "ORBB": {"lat": 33.3, "lon": 44.4}, # Baghdad (Iraq)
    "OKAC": {"lat": 29.2, "lon": 47.9}, # Kuwait
    "OBBB": {"lat": 26.2, "lon": 50.6}, # Bahrain
    "OMAE": {"lat": 24.4, "lon": 54.4}, # Emirates (UAE)
    "OIIX": {"lat": 35.7, "lon": 51.4}, # Tehran (Iran)
    "OEJD": {"lat": 21.5, "lon": 39.2}, # Jeddah (Saudi)
    "OOMM": {"lat": 23.6, "lon": 58.3}, # Muscat (Oman)
    "OYSC": {"lat": 15.3, "lon": 44.2}, # Sanaa (Yemen)
    "HCSM": {"lat": 2.0,  "lon": 45.3}  # Mogadishu (Somalia)
}

def initialize_notam_db():
    """Creates the CSV database if it does not exist."""
    if not os.path.exists(NOTAM_DB):
        columns = ["timestamp", "notam_id", "facility", "latitude", "longitude", "message"]
        pd.DataFrame(columns=columns).to_csv(NOTAM_DB, index=False)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📁 NOTAM Database Initialized.")

def fetch_notams():
    """Pulls live, real-world NOTAMs from the CheckWX aviation aggregator."""
    if not API_KEY:
        print("❌ CRITICAL ERROR: CHECKWX_API_KEY not found in .env file.")
        return []

    designators = ",".join(FIR_COORDS.keys())
    url = f"https://api.checkwx.com/notam/loc/{designators}"
    
    headers = {
        "X-API-Key": API_KEY
    }
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📡 WIDE-AREA SWEEP: Pulling live data for {len(FIR_COORDS)} FIRs via CheckWX...")
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        raw_json = response.json()
        
        # CheckWX stores the list of NOTAMs inside the 'data' key
        notam_list = raw_json.get('data', [])
        
        if not notam_list:
            print(f"🔍 DEBUG: Connected successfully, but 0 active NOTAMs returned for these regions.")
        else:
            print(f"✅ SUCCESS: Downloaded {len(notam_list)} live NOTAMs. Handing off to EW filter...")
            
        return notam_list

    except requests.exceptions.HTTPError as e:
        print(f"❌ API Error {response.status_code}: Check your API Key or rate limits.")
        return []
    except Exception as e:
        print(f"❌ FETCH ERROR: {e}")
        return []

def process_notams(notam_list):
    """Filters the live CheckWX feed for Electronic Warfare indicators."""
    if not notam_list:
        return

    new_entries = []
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for item in notam_list:
        message = item.get('text', '').upper()
        notam_id = item.get('id', 'UNK')
        facility = item.get('location', 'UNK')
        
        # Keyword filter to isolate EW/GPS events
        if any(kw in message for kw in EW_KEYWORDS):
            # Fallback coordinate if the facility isn't in our dictionary
            coords = FIR_COORDS.get(facility, {"lat": 24.5, "lon": 46.5}) 
            
            new_entries.append({
                "timestamp": current_time,
                "notam_id": notam_id,
                "facility": facility,
                "latitude": coords["lat"],
                "longitude": coords["lon"],
                "message": message.replace('\n', ' ') # Clean up newlines for the CSV
            })

    if new_entries:
        df_new = pd.DataFrame(new_entries)
        
        # Prevent double-counting by checking against existing IDs
        if os.path.exists(NOTAM_DB):
            existing = pd.read_csv(NOTAM_DB)
            df_new = df_new[~df_new['notam_id'].isin(existing['notam_id'])]
            
        if not df_new.empty:
            df_new.to_csv(NOTAM_DB, mode='a', header=False, index=False)
            print(f"✅ LOGGED: {len(df_new)} unique LIVE regional EW alerts.")
        else:
            print("✅ No new alerts discovered in this cycle.")

if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Launching V2 NOTAM Scraper (Live API Mode)...")
    initialize_notam_db()
    
    try:
        while True:
            # 1. Fetch live data
            raw_data = fetch_notams()
            
            # 2. Process and log to CSV
            process_notams(raw_data)
            
            # 3. Sleep until next cycle
            next_run = datetime.now() + timedelta(seconds=POLL_INTERVAL)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 💤 Sweep Complete. Next update at {next_run.strftime('%H:%M:%S')}.")
            time.sleep(POLL_INTERVAL)
            
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🛑 Shutdown signal received. Closing Scraper safely.")