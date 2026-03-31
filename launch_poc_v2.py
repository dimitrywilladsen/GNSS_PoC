import subprocess
import time
import sys

def launch_services():
    print("===================================================")
    print("Initiating V2 Multi-Domain Intelligence Architecture")
    print("===================================================")

    processes = []

    try:
        # 1. Launch Aviation Telemetry Collector
        print("[*] Launching API Rotator & Heuristics Engine (adsb_collector_v2.py)...")
        p1 = subprocess.Popen([sys.executable, "adsb_collector_v2.py"])
        processes.append(p1)

        # 2. Launch FAA NOTAM Scraper
        print("[*] Launching Geospatial OSINT Scraper (notam_scraper_v2.py)...")
        p2 = subprocess.Popen([sys.executable, "notam_scraper_v2.py"])
        processes.append(p2)

        # 3. Launch News OSINT Scraper
        print("[*] Launching Strategic OSINT Feed (osint_scraper_v2.py)...")
        p3 = subprocess.Popen([sys.executable, "osint_scraper_v2.py"])
        processes.append(p3)

        # 4. Launch Streamlit Dashboard
        print("[*] Launching Executive Dashboard (gnss_app_v2.py)...")
        p4 = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "gnss_app_v2.py"])
        processes.append(p4)

        # Launch Autonomous SITREP Generator
        print("[*] Launching Autonomous Intelligence Node (auto_summary.py)...")
        p4 = subprocess.Popen([sys.executable, "auto_summary.py"])
        processes.append(p4)

        print("\n[+] All collection pipelines deployed successfully.")
        print("[!] Press Ctrl+C in this terminal to shut down the entire architecture cleanly.\n")

        # Keep the master thread alive to monitor the sub-processes
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[!] Stand down command received. Terminating all intelligence pipelines...")
        for p in processes:
            p.terminate()
        print("Shutdown complete. All ports closed.")

    except Exception as e:
        print(f"\n[!] Critical Error: {e}")
        for p in processes:
            p.terminate()

if __name__ == "__main__":
    launch_services()