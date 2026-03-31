import requests
import xml.etree.ElementTree as ET
import pandas as pd
import time
from datetime import datetime, timedelta
import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv
from email.utils import parsedate_to_datetime
import urllib.parse

# --- CONFIGURATION ---
load_dotenv()
OSINT_DB = "osint_news_v2.csv"
FEEDBACK_DB = "osint_feedback.json"
TRIGGER_FILE = "scraper_trigger.json"
POLL_INTERVAL = 1800  # Check for data triggers every 30 mins
LOOKBACK_DAYS = 30

# Initialize Gemini 2.0 Client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def get_dynamic_discovery_query():
    if os.path.exists(TRIGGER_FILE):
        try:
            with open(TRIGGER_FILE, "r") as f:
                trigger = json.load(f)
            
            lat = trigger.get('lat', 0)
            if 24 < lat < 27: location = "Strait of Hormuz"
            elif lat < 20: location = "Red Sea"
            elif 32 < lat < 36: location = "Levant"
            else: location = "Middle East"
            
            # Stripped parentheses to prevent Google News RSS from choking
            query = f'"{location}" GPS jamming OR GNSS spoofing when:30d'
            
            os.remove(TRIGGER_FILE)
            print(f"📡 DATA TRIGGER: Sifting for 30-day fresh reports in {location}...")
            return query
        except Exception as e:
            print(f"Error reading trigger: {e}")
            
    # THE FALLBACK: Simplified syntax guaranteed to work with Google RSS
    print("🌍 ACTIVE HUNT: Pulling global baseline...")
    return 'GPS jamming OR GNSS spoofing OR EASA interference when:7d'

def fetch_and_process_news():
    query = get_dynamic_discovery_query()
    
    if not query:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Data is nominal. Standing by...")
        return

    safe_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={safe_query}&hl=en-US&gl=US&ceid=US:en"
    print(f"🔗 Searching: {rss_url}")
    
    feedback_history = load_analyst_feedback()
    
    try:
        res = requests.get(rss_url, timeout=15)
        root = ET.fromstring(res.content)
        items = root.findall('./channel/item')
        
        print(f"📡 Google News returned {len(items)} raw articles.")
        
        if len(items) == 0:
            print("⚠️ WARNING: Google returned an empty feed.")
            return

        discovered_articles = []
        strict_cutoff = datetime.now() - timedelta(days=LOOKBACK_DAYS)
        
        for item in items[:15]:
            raw_date = item.find('pubDate').text
            dt_obj = parsedate_to_datetime(raw_date)
            
            if dt_obj.replace(tzinfo=None) >= strict_cutoff:
                title = item.find('title').text
                print(f"  -> Evaluating: {title[:60]}...") 
                
                analysis = evaluate_with_agent(title, feedback_history)
                
                # --- THE MISSING PACER: DO NOT REMOVE ---
                # This keeps you under the Free Tier's 15 Requests Per Minute limit.
                time.sleep(4) 
                
                if analysis.get('is_relevant'):
                    print("     ✅ RELEVANT")
                    discovered_articles.append({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "pub_date": raw_date,
                        "title": title,
                        "source": item.find('source').text if item.find('source') is not None else "Unknown",
                        "link": item.find('link').text,
                        "bluf": analysis.get('bluf'),
                        "actors": ", ".join(analysis.get('actors', []))
                    })
                else:
                    print("     ❌ REJECTED by Agent")

        if discovered_articles:
            df = pd.DataFrame(discovered_articles)
            df.to_csv(OSINT_DB, mode='a', header=not os.path.exists(OSINT_DB), index=False)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📝 SUCCESS: Added {len(discovered_articles)} reports.")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🕵️ Discovery completed: No new relevant articles.")

    except Exception as e:
        print(f"❌ Scraper Loop Error: {e}")

def load_analyst_feedback():
    if os.path.exists(FEEDBACK_DB):
        with open(FEEDBACK_DB, 'r') as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def evaluate_with_agent(title, feedback_history):
    """
    Uses Gemini to evaluate if a discovered report validates the raw telemetry data, 
    retaining analytical intuition.
    """
    body = "You are an Intel Analyst. Determine if this report explains real-time EW or GNSS interference trends.\n"
    if feedback_history:
        body += "\nApply these past human-analyst corrections to refine your baseline:\n"
        for item in feedback_history[-5:]:
            status = "RELEVANT" if item['relevant'] else "IRRELEVANT"
            body += f"- Headline: '{item['title']}' was marked {status}\n"

    prompt = f"""
    {body}
    
    Evaluate this new discovery: "{title}"
    
    Apply the mindset of a Cryptologic Warfare Officer analyzing open-source signals. Does this provide actionable context for regional spectrum denial? 
    (Ignore consumer electronics, Garmin watches, and routine smartphone software updates.)
    
    Return ONLY JSON with this exact schema:
    {{
        "is_relevant": true/false,
        "bluf": "1-sentence tactical Bottom Line Up Front (the 'so what?')",
        "actors": ["Specific entities, nations, or agencies involved"]
    }}
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.4 # Raised back up to allow for analytical synthesis
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Agent Evaluation Error: {e}")
        return {"is_relevant": False}

if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Launching Strategic OSINT Feed...")
    print(f"📡 System configured for Silent Watch: Polling every {POLL_INTERVAL // 60} minutes.")
    
    while True:
        # 1. Execute the fetch and evaluation cycle
        fetch_and_process_news()
        
        # 2. Log completion and calculate next wake-up
        next_run = datetime.now() + timedelta(seconds=POLL_INTERVAL)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 💤 Cycle complete. Next hunt at {next_run.strftime('%H:%M:%S')}.")
        
        # 3. Hibernate for 30 minutes
        time.sleep(POLL_INTERVAL)