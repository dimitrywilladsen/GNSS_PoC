import os
import time
import pandas as pd
from datetime import datetime, timezone
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Ensure this matches your actual filename
DATABASE_FILE = "ew_historical_collection_v2.csv" 

if not GEMINI_API_KEY:
    print("🛑 CRITICAL: API KEY not found.")
    exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)

def analyze_database():
    if not os.path.exists(DATABASE_FILE):
        return "No database found."
    
    try:
        df = pd.read_csv(DATABASE_FILE)
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        
        # Filter for the last 12 hours
        lookback_limit = datetime.now() - pd.Timedelta(hours=12)
        recent_df = df[df['timestamp'] >= lookback_limit]
        
        if recent_df.empty:
            return "No anomalies detected in the last 12 hours."

        # Calculation 1: Total volume of signal degradation
        total_anomalies = len(recent_df)
        
        # Calculation 2: Total number of unique aircraft impacted
        unique_aircraft = recent_df['callsign'].nunique()
        
        return (f"Logged {total_anomalies} total anomalous pings "
                f"affecting {unique_aircraft} unique aircraft in the last 12 hours.")
    
    except Exception as e:
        return f"Error analyzing database: {e}"

def generate_and_save_summary():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Initiating Autonomous Summary Generation...")
    recent_data = analyze_database()
    
    prompt = f"""
    You are an analyst writing a twice-daily Summary. 
    System telemetry: "{recent_data}"
    Section 1: One-sentence BLUF.
    Section 2: Technical Deep Dive (max 3 paragraphs).
    |||SPLIT|||
    CONSTRAINT: Do not output 'Navy SEAL'.
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash', # Corrected Version
            contents=prompt
        )
        sections = response.text.split("|||SPLIT|||")
        if len(sections) == 2:
            # Write the files the dashboard is looking for
            with open("intel_exec_summaries.txt", "a") as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M')} | {sections[0].strip()}\n")
            with open("intel_deep_dives.txt", "a") as f:
                f.write(f"\n{datetime.now().strftime('%Y-%m-%d')}\n{sections[1].strip()}\n")
            print("✅ Summary successfully generated.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # FORCE RUN ON STARTUP
    generate_and_save_summary()
    
    while True:
        current_time = datetime.now(timezone.utc)
        if current_time.hour in [0, 12] and current_time.minute == 0:
            generate_and_save_summary()
            time.sleep(61)
        time.sleep(30)