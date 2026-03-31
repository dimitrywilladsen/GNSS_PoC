import requests
import pandas as pd
import time
from datetime import datetime
import os
import json

# --- CONFIGURATION ---
DATABASE_FILE = "ew_historical_collection_v2.csv"
STATUS_FILE = "collector_status.json"
TRIGGER_FILE = "scraper_trigger.json"
POLL_INTERVAL = 60  

# AOR Bounding Box (Middle East / Levant / Red Sea)
LAT_MIN, LAT_MAX = 10.0, 38.0
LON_MIN, LON_MAX = 32.0, 60.0

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Encoding': 'gzip' # Critical for bypassing Cloudflare drops
}

# Targeted API calls (Center of Middle East + 1000nm radius)
ENDPOINTS = [
    "https://api.airplanes.live/v2/point/24.0/46.0/1000",
    "https://api.adsb.fi/v2/point/24.0/46.0/1000",
    "https://api.adsb.lol/v2/point/24.0/46.0/1000",
    "https://api.theairtraffic.com/v2/point/24.0/46.0/1000" # Added Redundancy
]

def update_status(api_name, status="ACTIVE", threats=0):
    with open(STATUS_FILE, "w") as f:
        json.dump({
            "active_api": api_name, 
            "status": status, 
            "last_poll": datetime.now().strftime("%H:%M:%S"),
            "threats_logged": threats
        }, f)

def initialize_database():
    if not os.path.exists(DATABASE_FILE):
        df = pd.DataFrame(columns=[
            "timestamp", "callsign", "latitude", "longitude", 
            "altitude", "velocity", "nic", "sil", "Threat_Type"
        ])
        df.to_csv(DATABASE_FILE, index=False)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Database Initialized.")

def fetch_telemetry():
    """Cycles through Point APIs to grab unthrottled regional data."""
    for url in ENDPOINTS:
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            if res.status_code == 200:
                data = res.json().get('ac', res.json().get('aircraft', []))
                # Bounding box filter
                aor_data = [
                    ac for ac in data 
                    if ac.get('lat') and ac.get('lon') and 
                    LAT_MIN <= ac['lat'] <= LAT_MAX and LON_MIN <= ac['lon'] <= LON_MAX
                ]
                
                source_name = url.split('//')[1].split('/')[0]
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 📡 {source_name}: Tracking {len(aor_data)} live aircraft in AOR.")
                
                return aor_data, source_name
        except requests.RequestException:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ API Timeout: {url}. Rotating...")
            continue
    return None, "ALL_APIS_FAILED"

def process_and_log(planes, source_name):
    if not planes: return 0, []
    anomalies = []
    
    for p in planes:
        is_mlat = p.get('mlat', []) != [] 
        lat, lon = p.get('lat'), p.get('lon')
        nic, sil = p.get('nic'), p.get('sil')
        vel, alt = p.get('gs', 0), p.get('alt_baro', 0)
        callsign = str(p.get('flight', 'UNK')).strip()
        
        threat = None
        
        # Priority 1: Confirmed Jamming (Ground MLAT takes over from lost GPS)
        if is_mlat and lat and lon:
            threat = "Confirmed Jamming (MLAT Active)"
            
        # Priority 2: Spoofing (Kinematic impossibilities)
        elif vel > 600 and alt < 40000:
            threat = "Spoofing (Kinematic)"
            
        # Priority 3: Degradation (Aircraft broadcasts low integrity)
        elif nic is not None and (nic < 7 or (sil is not None and sil < 2)):
            threat = "Jamming/Degradation (Low NIC/SIL)"

        if threat:
            anomalies.append([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                callsign, lat, lon, alt, vel, 
                nic if nic is not None else 0, 
                sil if sil is not None else 0, 
                threat
            ])

    if anomalies:
        pd.DataFrame(anomalies).to_csv(DATABASE_FILE, mode='a', header=False, index=False)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 {source_name}: Logged {len(anomalies)} integrity alerts.")
        return len(anomalies), anomalies
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {source_name}: Normal operations.")
        return 0, []

if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Launching Hardened Aviation EW Collector...")
    initialize_database()
    
    current_backoff = POLL_INTERVAL
    MAX_BACKOFF = 600  # Cap the maximum wait time at 10 minutes
    
    while True:
        data, source = fetch_telemetry()
        
        if data is not None:
            # --- SUCCESS LOGIC ---
            current_backoff = POLL_INTERVAL # Reset backoff timer on success
            threats_found, anomalies_list = process_and_log(data, source)
            update_status(source, "ACTIVE", threats_found)
            
            # --- THE TRIGGER LOGIC ---
            if threats_found >= 3:
                avg_lat = sum(a[2] for a in anomalies_list) / len(anomalies_list)
                avg_lon = sum(a[3] for a in anomalies_list) / len(anomalies_list)
                
                with open(TRIGGER_FILE, "w") as f:
                    json.dump({
                        "timestamp": datetime.now().isoformat(),
                        "lat": avg_lat,
                        "lon": avg_lon,
                        "threat_type": "Regional Cluster",
                        "threat_count": threats_found
                    }, f)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🛰️ DATA TRIGGER: High-confidence EW event. Signal sent to Scraper.")
                
            time.sleep(POLL_INTERVAL)
            
        else:
            # --- ANTI-BAN EXPONENTIAL BACKOFF LOGIC ---
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ All APIs failed. Engaging Exponential Backoff.")
            update_status("OFFLINE", "ERROR", 0)
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🛡️ Anti-Ban Protocol: Sleeping for {current_backoff} seconds...")
            time.sleep(current_backoff)
            
            # Double the backoff time for the next failure, capped at MAX_BACKOFF
            current_backoff = min(current_backoff * 2, MAX_BACKOFF)

if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Launching Hardened Aviation EW Collector...")
    initialize_database()
    
    try:
        while True:
            data, source = fetch_telemetry()
            
            if data is not None:
                # ... [your existing processing and trigger logic here] ...
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 💤 Cycle complete. Sleeping for {POLL_INTERVAL}s...")
                time.sleep(POLL_INTERVAL)
            else:
                # ... [your existing backoff logic here] ...
                time.sleep(current_backoff)
                
    except KeyboardInterrupt:
        # This catches the Ctrl+C and exits cleanly without an error message
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🛑 Shutdown signal received. Closing Collector safely.")