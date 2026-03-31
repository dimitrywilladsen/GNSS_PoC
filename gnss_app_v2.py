import streamlit as st
import pydeck as pdk
import pandas as pd
import os
import json
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# --- PAGE CONFIG ---
st.set_page_config(page_title="GNSS Interference PoC", layout="wide")
st.title("Aviation Domain: GNSS Integrity & EW Tracking")

# Auto-refresh the dashboard every 60 seconds
st_autorefresh(interval=60000, key="data_refresh")

# --- DATA LOADERS ---
@st.cache_data(ttl=60)
def load_historical_data():
    """Loads aviation telemetry anomalies (NIC/SIL degradation/MLAT)."""
    csv_path = "ew_historical_collection_v2.csv"
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            if not df.empty and 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
                # Force numeric types for mapping
                for col in ['latitude', 'longitude', 'nic', 'sil']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                return df.dropna(subset=['latitude', 'longitude', 'timestamp'])
        except Exception as e:
            st.error(f"Error loading telemetry: {e}")
    return pd.DataFrame()

@st.cache_data(ttl=60)
def load_notams():
    """Loads mapped FAA NOTAMs and ensures they are numeric for pydeck."""
    csv_path = "notam_reports_v2.csv"
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            if not df.empty:
                # Ensure coordinate integrity
                df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
                df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
                
                # Filter out any broken coordinates
                return df.dropna(subset=['latitude', 'longitude'])
        except Exception as e:
            st.error(f"Error loading NOTAMs: {e}")
    return pd.DataFrame()

@st.cache_data(ttl=60)
def load_osint():
    """Loads OSINT news and the new Summary file format with robust parsing."""
    csv_path = "osint_news_v2.csv"
    exec_summary_path = "intel_exec_summaries.txt"
    
    # Start with an empty dataframe
    df = pd.DataFrame(columns=['timestamp', 'title', 'link', 'bluf', 'actors', 'source', 'pub_date', 'parsed_pub_date'])
    
    # 1. Load the 129 News Articles
    if os.path.exists(csv_path):
        try:
            news_df = pd.read_csv(csv_path)
            news_df['timestamp'] = pd.to_datetime(news_df['timestamp'], errors='coerce')
            if 'pub_date' in news_df.columns:
                # Ensure the news dates are timezone-naive to match the summary logic
                news_df['parsed_pub_date'] = pd.to_datetime(news_df['pub_date'], errors='coerce', utc=True).dt.tz_localize(None)
            df = pd.concat([df, news_df], ignore_index=True)
        except Exception as e:
            st.error(f"Error loading news: {e}")

    # 2. Load the Intelligence Summary
    if os.path.exists(exec_summary_path):
        try:
            with open(exec_summary_path, "r", encoding="utf-8") as f:
                for line in f:
                    if "|" in line:
                        try:
                            parts = line.split("|")
                            date_str = parts[0].strip()
                            summary_text = parts[1].strip()
                            
                            # Parse date and ensure it is timezone-naive
                            ts = pd.to_datetime(date_str)
                            if ts.tzinfo is not None:
                                ts = ts.tz_localize(None)
                            
                            summary_row = {
                                'timestamp': ts,
                                'title': f"📋 DAILY INTEL SUMMARY: {date_str}",
                                'link': "#",
                                'bluf': summary_text, 
                                'source': "Gemini Analysis Agent",
                                'pub_date': date_str,
                                'parsed_pub_date': ts
                            }
                            df = pd.concat([df, pd.DataFrame([summary_row])], ignore_index=True)
                        except:
                            continue # Skip bad lines within the file
        except Exception as e:
            st.error(f"Error reading summary file: {e}")

    # Final cleanup and sort (outside of all loops)
    if not df.empty:
        return df.dropna(subset=['timestamp']).sort_values('parsed_pub_date', ascending=False)
    else:
        return df

ew_history_df = load_historical_data()
notam_df = load_notams()
osint_df = load_osint()

# --- TABS CONFIGURATION ---
tab_map, tab_osint, tab_intel, tab_health = st.tabs([
    " Spatial Intelligence", 
    " OSINT Feed", 
    " Telemetry Archive", 
    " System Health"
])

# --- TAB 1: SPATIAL INTELLIGENCE ---
with tab_map:
    # 1. LIVE THREAT ALERTS (Last 15 minutes of raw data)
    live_cutoff = datetime.now() - timedelta(minutes=15)
    
    if not ew_history_df.empty:
        recent_threats = ew_history_df[
            (ew_history_df['timestamp'] >= live_cutoff) & 
            (ew_history_df['Threat_Type'].str.contains('MLAT|Spoofing', case=False, na=False))
        ]
        
        if not recent_threats.empty:
            st.error(f"🚨 **LIVE CRITICAL ALERT:** {len(recent_threats)} active jamming/spoofing events detected in the last 15 minutes.")
            latest_target = recent_threats.iloc[-1]
            st.warning(f"🎯 **Last Target Impacted:** {latest_target['callsign']} at {latest_target['latitude']:.4f}, {latest_target['longitude']:.4f}")

    st.markdown("""
        <style>
        /* Pin the popover to the bottom-left of the map column */
        div[data-testid="column"]:nth-of-type(1) .stPopover {
            position: absolute;
            bottom: 20px;
            left: 20px;
            z-index: 1000;
        }
        /* Make the popover content expand to the right so it doesn't get cut off */
        div[data-testid="stPopoverContent"] {
            width: 350px !important;
        }
        </style>
        """, unsafe_allow_html=True)

    # MAP UI CONTROLS
    col_m1, col_m2 = st.columns([4, 1])
    
    st.markdown("""
        <style>
        /* Remove the padding at the top of the column to align with map */
        [data-testid="column"]:nth-of-type(2) [data-testid="stVerticalBlock"] > div:first-child {
            margin-top: -35px;
        }
        /* Reduce the gap between individual metrics */
        [data-testid="stMetric"] {
            margin-bottom: -15px;
        }
        /* Tighten the space around the horizontal divider */
        hr {
            margin-top: 10px !important;
            margin-bottom: 10px !important;
        }
        </style>
        """, unsafe_allow_html=True)

    with col_m2:
        # --- 1. ENLARGED CONTROLS ---
        st.markdown("####  Display Settings")
        map_mode = st.radio(
            "Intelligence Layer:", 
            ["Density (Raw Volume)", "Trend (7-Day Delta)"],
            label_visibility="collapsed" # Hides redundant label, keeps header big
        )
        
        lookback = st.select_slider(
            "Time Window:", 
            options=["1h", "6h", "24h", "48h", "7d", "30d"], 
            value="24h",
            help="Filters the raw volume of anomalous pings shown in 'Density' mode and defines the evaluation period used to calculate performance surges or drops in 'Trend' mode.",
            # label_visibility="collapsed"
        )
        
        # --- CALCULATION LOGIC (Untouched) ---
        time_map = {"1h": 1, "6h": 6, "24h": 24, "48h": 48, "7d": 168, "30d": 720}
        cutoff_time = datetime.now() - timedelta(hours=time_map[lookback])

        # --- 2. MARKDOWN DIVIDER BETWEEN SLIDER AND ANOMALIES ---
        st.markdown("---")

        # --- ANALYTICAL ENGINE: ISOLATION LOGIC (Untouched) ---
        if not ew_history_df.empty:
            # 1. Broad Collection (The "Wide Net")
            filtered_df = ew_history_df[ew_history_df['timestamp'] >= cutoff_time]
            total_anomalies = len(filtered_df)

            # 2. Mathematical Isolation (The "Verified Impact" Logic)
            interference_df = filtered_df[
                (filtered_df['nic'] < 7) & 
                (filtered_df['sil'] >= 3)
            ]
            
            # 3. Final Analytical Metrics
            isolated_pings = len(interference_df)
            unique_impacted = interference_df['callsign'].nunique() if not interference_df.empty else 0
        else:
            filtered_df = pd.DataFrame()
            total_anomalies = 0
            isolated_pings = 0
            unique_impacted = 0

        # --- 3. METRICS WITH FULL DEFINITIONS ---
        
        st.markdown("#### Live Data")

        st.metric(
            label="Total Anomalous Pings", 
            value=f"{total_anomalies:,}", 
            help="The raw count of all suspicious telemetry points captured. This baseline includes hardware glitches and environmental signal degradation."
        )

        st.metric(
            label="Isolated Interference Pings", 
            value=f"{isolated_pings:,}", 
            help="The subset of pings where high-integrity hardware (SIL >= 3) reported a degraded signal (NIC < 7)."
        )

        st.metric(
            label="Unique Aircraft Impacted", 
            value=f"{unique_impacted:,}", 
            help="Unique high-integrity aircraft platforms assessed to be experiencing active signal denial within the AOR."
        )
        
        st.markdown("---")

        # --- 4. DYNAMIC MAP LEGEND POPOVER ---
        with st.popover("🗺️ Map Legend", use_container_width=True):
            st.markdown("### Signal Intelligence Reference")
            
            if map_mode == "Density (Raw Volume)":
                st.markdown("🛑 **Warm Colors:** High density of interference events.")
            else:
                st.markdown("🔴 **Red Pillars:** Surge in interference vs 7-day average.")
                st.markdown("🟢 **Green Pillars:** Drop in interference vs 7-day average.")
                st.markdown("⚪ **Gray Pillars:** Stable / No significant change.")
            
            st.markdown("---")
            st.markdown("🔵 **Points:** Origin facility of FAA/ICAO NOTAMs.")
            st.info("Note: NIC/SIL math is applied to all layers to isolate external interference.")

    with col_m1:
        # Base Layer: AOR Bounding Box
        map_layers = [
            pdk.Layer(
                "PolygonLayer", 
                pd.DataFrame([{"polygon": [[32.0, 10.0], [32.0, 38.0], [60.0, 38.0], [60.0, 10.0], [32.0, 10.0]]}]), 
                get_polygon="polygon", filled=False, stroked=True, 
                get_line_color=[255, 255, 255, 80], line_width_min_pixels=2
            )
        ]
        
        # Layer 1 Data Processing Selection
        if not ew_history_df.empty:
            if map_mode == "Density (Raw Volume)" and not filtered_df.empty:
                # Standard Hexagon Layer
                map_layers.append(
                    pdk.Layer(
                        "HexagonLayer", 
                        data=filtered_df, 
                        get_position=["longitude", "latitude"],
                        radius=40000, elevation_scale=50, extruded=True, pickable=True,
                        opacity=0.7, coverage=0.9, 
                        color_range=[[254, 204, 92], [253, 141, 60], [240, 59, 32], [189, 0, 38]]
                    )
                )
            elif map_mode == "Trend (7-Day Delta)":
                # 1. Expand spatial grid to 0.5 degrees (~55km grid cells)
                trend_df = ew_history_df.copy()
                trend_df['grid_lat'] = (trend_df['latitude'] * 2).round() / 2
                trend_df['grid_lon'] = (trend_df['longitude'] * 2).round() / 2
                
                # Split data: Current Window vs Baseline (Previous 7 Days)
                baseline_start = cutoff_time - timedelta(days=7)
                
                df_current = trend_df[trend_df['timestamp'] >= cutoff_time]
                df_baseline = trend_df[(trend_df['timestamp'] >= baseline_start) & (trend_df['timestamp'] < cutoff_time)]
                
                curr_counts = df_current.groupby(['grid_lat', 'grid_lon']).size().reset_index(name='current_count')
                base_counts = df_baseline.groupby(['grid_lat', 'grid_lon']).size().reset_index(name='base_count')
                
                # Normalize the baseline to match the slider window
                window_ratio = time_map[lookback] / 168.0 
                base_counts['expected_count'] = base_counts['base_count'] * window_ratio
                
                delta_df = pd.merge(curr_counts, base_counts, on=['grid_lat', 'grid_lon'], how='outer').fillna(0)
                delta_df['delta'] = delta_df['current_count'] - delta_df['expected_count']
                
                # PRE-CALCULATE HEIGHT IN PANDAS TO PREVENT JAVASCRIPT CRASH
                delta_df['elevation_value'] = delta_df['delta'].abs() * 20
                
                # 2. Raise the threshold to eliminate single-aircraft noise
                def determine_color(d):
                    if d > 100: return [255, 50, 50, 200]     # Significant Surge (Red)
                    elif d < -100: return [50, 255, 50, 200]  # Significant Drop (Green)
                    else: return [150, 150, 150, 150]         # Nominal/Noise (Gray)
                
                delta_df['color'] = delta_df['delta'].apply(determine_color)
                
                if not delta_df.empty:
                    map_layers.append(
                        pdk.Layer(
                            "ColumnLayer",
                            data=delta_df,
                            get_position=["grid_lon", "grid_lat"],
                            get_elevation="elevation_value", # USING THE PRE-CALCULATED COLUMN
                            elevation_scale=50,
                            radius=25000, 
                            get_fill_color="color",
                            pickable=True,
                            auto_highlight=True,
                        )
                    )
            
        # Layer 2: FAA NOTAMs (Scatter Points)
        if not notam_df.empty:
            map_layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=notam_df, 
                    get_position=["longitude", "latitude"],
                    get_radius=30000, 
                    get_fill_color=[0, 150, 255, 200], 
                    get_line_color=[255, 255, 255, 255],
                    stroked=True, line_width_min_pixels=2, pickable=True
                )
            )

# Render Map
        deck = pdk.Deck(
            layers=map_layers, 
            initial_view_state=pdk.ViewState(
                latitude=25.0,
                longitude=45.0,
                zoom=3.5, 
                pitch=45,
                bearing=0
            ),
            map_style="dark", 
            tooltip={"html": "<b>Location:</b> {grid_lat}, {grid_lon} <br/> <b>Change vs Baseline:</b> {delta}"} 
        )
        
        st.pydeck_chart(deck, use_container_width=True, height=575)

# --- TAB 2: OSINT NEWS FEED ---
with tab_osint:
    import re
    st.header("📰 Open Source Intelligence (OSINT)")
    st.write("Live reporting and automated summaries evaluated by LLM Agent.")
    
    if not osint_df.empty:
        # --- SESSION STATE INITIALIZATION ---
        if 'osint_search' not in st.session_state:
            st.session_state.osint_search = ""
        if 'osint_sources' not in st.session_state:
            st.session_state.osint_sources = []
            
        def reset_filters():
            """Clears all search and filter session states."""
            st.session_state.osint_search = ""
            st.session_state.osint_sources = []
            
        # Create a layout with the feed on the left and controls on the right
        col_feed, col_filters = st.columns([2, 1])
        
        with col_filters:
            st.subheader("🔍 Threat Hunting")
            
            # Boolean Search Guide
            st.caption("💡 **Search Tips:** Use **AND**, **OR**, **NOT** \n\n*(e.g., `GPS AND Drone`, `Russia OR China`, `Spoofing NOT Europe`)*")
            
            # Tying the input to session_state via the 'key' parameter
            search_query = st.text_input("Search Keyword:", key="osint_search")
            
            st.markdown("**Time & Source Filters**")
            show_historic = st.toggle("📂 Include reports older than 30 days", value=False)
            
            available_sources = osint_df['source'].dropna().unique().tolist()
            selected_sources = st.multiselect("Filter by Source:", options=available_sources, key="osint_sources")
            
            # The Reset Button
            st.button("🔄 Reset All Filters", on_click=reset_filters, use_container_width=True)
            
            st.markdown("---")
            st.markdown("### ⚡ Live Operations")
            
            # THE NEW ACTIVE PULL BUTTON
            if st.button("🚀 Run Active Intel Pull", type="primary", use_container_width=True):
                with st.spinner("Executing OSINT scrapers & rebuilding summaries..."):
                    import subprocess
                    import sys
                    try:
                        # Reaches out to the OS and forces your background scripts to run right now
                        subprocess.run([sys.executable, "osint_scraper_v2.py"], check=True)
                        subprocess.run([sys.executable, "auto_summary.py"], check=True)
                        
                        # Clears the cache to ensure we get the fresh data, then reloads the page
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Collection execution failed: {e}")

            st.markdown("---")
            st.markdown("### 📊 Feed Metrics")
            st.metric("Total Scraped Reports", len(osint_df))
            st.metric("Active Intel Sources", len(available_sources))
            
        with col_feed:
            display_df = osint_df.copy()
            
            # 1. Apply Time Filter
            if not show_historic:
                display_cutoff = datetime.now() - timedelta(days=30)
                display_df = display_df[display_df['parsed_pub_date'] >= display_cutoff]
            
            # 2. Apply Source Filter
            if st.session_state.osint_sources:
                display_df = display_df[display_df['source'].isin(st.session_state.osint_sources)]
                
            # 3. Apply Boolean Search Filter
            sq = st.session_state.osint_search.strip()
            if sq:
                # Combine title and BLUF for a comprehensive text search
                search_corpus = display_df['title'].fillna('') + " " + display_df.get('bluf', pd.Series(dtype=str)).fillna('')
                search_corpus = search_corpus.str.lower()
                
                try:
                    if " or " in sq.lower():
                        terms = [t.strip() for t in sq.lower().split(" or ")]
                        mask = search_corpus.str.contains('|'.join(map(re.escape, terms)))
                    elif " and " in sq.lower():
                        terms = [t.strip() for t in sq.lower().split(" and ")]
                        mask = pd.Series(True, index=display_df.index)
                        for term in terms:
                            mask = mask & search_corpus.str.contains(re.escape(term))
                    elif " not " in sq.lower():
                        parts = sq.lower().split(" not ")
                        include_term = parts[0].strip()
                        exclude_term = parts[1].strip()
                        mask = search_corpus.str.contains(re.escape(include_term)) & ~search_corpus.str.contains(re.escape(exclude_term))
                    else:
                        mask = search_corpus.str.contains(re.escape(sq.lower()))
                        
                    display_df = display_df[mask]
                except Exception as e:
                    st.error(f"Search syntax error. Please use standard characters. ({e})")
                
            st.subheader(f"📑 Intel Feed ({len(display_df)} results)")
            
            # Separate the AI Summaries from the raw news to pin them
            summaries_df = display_df[display_df['title'].str.contains("DAILY INTEL SUMMARY", na=False)]
            news_df = display_df[~display_df['title'].str.contains("DAILY INTEL SUMMARY", na=False)]
            
            # 4. Render the Feed in a scrollable box
            with st.container(height=700):
                # Always show the Executive Summaries first
                for index, row in summaries_df.iterrows():
                    st.success(f"**{row['title']}**\n\n**Generated:** {row['pub_date']}\n\n**ASSESSMENT:** {row['bluf']}")
                
                # Render the rest of the news
                if not news_df.empty:
                    for index, row in news_df.head(50).iterrows():
                        st.markdown(f"#### [{row['title']}]({row.get('link', '#')})")
                        st.caption(f"🗓️ **Event Date:** `{row.get('pub_date', 'Unknown')}` | 🏢 **Source:** {row.get('source', 'Unknown')}")
                        
                        if pd.notna(row.get('bluf')):
                            st.info(f"**AI Context:** {row['bluf']}")
                            
                        if pd.notna(row.get('actors')):
                            st.write(f"🎭 **Extracted Actors:** `{row['actors']}`")
                            
                        st.divider()
                elif summaries_df.empty:
                    st.warning("No reports match your current search parameters. Try clicking 'Reset All Filters'.")

    else:
        st.info("Awaiting initial data. Ensure osint_scraper_v2.py and auto_summary.py are running.")

# --- TAB 3: TELEMETRY ARCHIVE ---
with tab_intel:
    st.header("Raw Aviation Target Telemetry")
    st.write("Aircraft reporting suspicious kinematic behavior or degraded NIC/SIL integrity.")
    if not ew_history_df.empty:
        st.dataframe(ew_history_df.sort_values('timestamp', ascending=False).head(500), use_container_width=True)
    else:
        st.info("Awaiting telemetry collection. Ensure adsb_collector_v2.py is running.")

# --- TAB 4: SYSTEM HEALTH ---
with tab_health:
    st.header("Collection Architecture Status")
    try:
        with open("collector_status.json", "r") as f:
            status_data = json.load(f)
            col1, col2, col3 = st.columns(3)
            col1.metric("Active API Source", status_data.get("active_api", "Unknown"))
            col2.metric("Last Heartbeat", status_data.get("last_poll", "N/A"))
            col3.metric("Recent Threats Logged", status_data.get("threats_logged", 0))
    except Exception as e:
        st.warning("Collector status file not found or unreadable. Ensure `adsb_collector_v2.py` is running.")