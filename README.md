\#  GNSS Signal Integrity Engine (PoC)

\### \*A Technical Proof of Concept for Automated Interference Detection \& Corroboration\*



\---



\##  Project Objective

This repository is an ongoing \*\*Proof of Concept (PoC)\*\* designed to demonstrate the feasibility of detecting regional GNSS (GPS) interference using a multi-source data pipeline. 



Instead of relying on expensive ground-based sensors, this project explores a "crowdsourced" approach: monitoring how commercial aircraft report their own navigation health and corroborating those anomalies with automated open-source reporting to identify where signals are being jammed or spoofed in real-time.



\---



\##  Core Methodology: The Integrity Duo

The project’s current analytical logic is built around the correlation of two critical ADS-B (Automatic Dependent Surveillance–Broadcast) metrics. In this PoC stage, we are testing the hypothesis that these two numbers can reliably "fingerprint" regional jamming:



\* \*\*NIC (Navigation Integrity Category):\*\* \*The "Certainty" Score.\* Defines the aircraft's own calculation of its position's safety margin (containment radius). 

\* \*\*SIL (Source Integrity Level):\*\* \*The "Source" Score.\* Indicates the probability of the position source (GPS/GNSS) exceeding the integrity containment limit.



> \*\*The PoC Hypothesis:\*\* By detecting a cluster of aircraft with \*\*Low NIC\*\* (uncertainty) but \*\*High SIL\*\* (healthy hardware), the system can mathematically isolate external regional interference from individual equipment failure.



\---



\##  Initial Framework (Work in Progress)

This PoC implements a dual-stream "plumbing" system for high-frequency data ingestion:



\### \*\*1. Telemetry Ingestion\*\*

\* \*\*RESTful API Integration:\*\* Automated calls to global flight data aggregators to pull live "State Vectors" (position, altitude, and integrity metrics).

\* \*\*Geospatial Filtering:\*\* Python scripts designed to filter for specific "Integrity Thresholds" in targeted geographic sectors, specifically within the Middle East AOR.



\### \*\*2. Automated OSINT Scraping\*\*

\* \*\*Open-Source Corroboration:\*\* An automated secondary pipeline designed to \*\*scrape open-source reporting\*\* (specialized aviation blogs, GPS interference trackers, and official regulatory notices). 

\* \*\*Validation Logic:\*\* Allows the user to cross-reference "Technical Evidence" (NIC/SIL drops) with "Human Intelligence" (public reports) to verify the nature of an interference event.



\### \*\*3. Automated Reporting \& Uploads\*\*

\* \*\*Incident Snapshots:\*\* Captures a high-resolution "snapshot" of all affected traffic in the vicinity upon detection.

\* \*\*Streamlined Export:\*\* A modular implementation of an \*\*automated upload\*\* loop, packaging "Verified Incidents" as JSON payloads and pushing them via Webhook/API to a central dashboard or storage bucket (S3).



\---



\##  Analytical Capabilities: Trends \& Aggregation

The engine moves beyond "one-off" alerts by synthesizing data into long-term intelligence:



\* \*\*Temporal Trend Analysis:\*\* Tracking changes in "Mean Integrity Levels" over time to identify escalation patterns.

\* \*\*Geospatial Aggregation:\*\* Clustering individual anomalies to map the physical footprint of interference zones.

\* \*\*Aggregated Reporting:\*\* Providing a bird's-eye view of how regional signal trends have shifted over hours, days, or weeks.



\---



\##  Roadmap \& Research Goals

\* \*\*Integrated NOTAM Correlation:\*\* Incorporating the \*\*FAA’s NMS (NOTAM Management System)\*\* via the SCDS/SWIM firehose to measure the lead-time of official warnings.

\* \*\*Signal Recovery Analysis:\*\* Measuring the \*\*"Re-acquisition Delta"\*\*—the time required for avionics to return to full precision ($NIC \\geq 7$) after exiting a contested zone.

\* \*\*Automation \& Scale:\*\* Refining the dual-stream ingestion pipeline to maintain stability under high-volume global traffic conditions.

