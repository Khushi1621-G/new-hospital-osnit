import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import io
from urllib.parse import quote

st.set_page_config(
    page_title="UK Hospital OSINT Analyzer",
    layout="wide"
)

# -----------------------------
# MASTER DATA SCHEMA
# -----------------------------
SCHEMA = {
    "Contacts": ["Hospital Emails", "Hospital Phone Numbers"],
    "Capacity": ["Total Beds", "ICU Beds", "Emergency Beds", "Operating Theatres", "Ambulance Fleet"],
    "Departments": ["Cardiology", "Neurology", "Oncology", "Orthopedics", "Radiology", "Pathology", "Pediatrics", "Emergency Department"],
    "Workforce": ["Doctors", "Consultants", "Nurses", "Specialists", "Administrative Staff"],
    "Equipment": ["MRI", "CT Scanner", "Ultrasound", "Ventilators", "X-Ray Systems", "Surgical Robots"],
    "Compliance": ["CQC Rating", "Privacy Notice", "Data Protection", "Cyber Security", "Information Governance"],
    "Research": ["Clinical Trials", "Research Centres", "University Partnerships", "Publications"],
    "Procurement": ["Contracts", "Tenders", "Equipment Procurement", "Technology Vendors"],
    "Emergency": ["Trauma Centre", "Emergency Department", "Critical Care", "Air Ambulance Access"]
}

# Heuristics for local rule-based intelligence matching
KEYWORD_MAPPING = {
    "Hospital Emails": ["email", "e-mail", "mail", "enquiries", "@nhs.net"],
    "Hospital Phone Numbers": ["phone", "telephone", "tel:", "switchboard", "call us", "contact number"],
    "Total Beds": ["beds", "bed capacity", "overnight beds", "total beds"],
    "ICU Beds": ["icu", "intensive care", "itu", "critical care beds"],
    "Emergency Beds": ["a&e beds", "emergency beds", "acute beds"],
    "Operating Theatres": ["theatres", "operating theatre", "surgical theatre"],
    "Ambulance Fleet": ["ambulance", "paramedic", "fleet", "vehicles"],
    "Cardiology": ["cardiology", "cardiac", "heart"],
    "Neurology": ["neurology", "brain", "neuro"],
    "Oncology": ["oncology", "cancer", "chemotherapy"],
    "Orthopedics": ["orthopedics", "orthopaedic", "bone", "joint"],
    "Radiology": ["radiology", "imaging", "x-ray", "mri"],
    "Pathology": ["pathology", "lab", "laboratory", "blood test"],
    "Pediatrics": ["pediatrics", "paediatric", "children", "child health"],
    "Emergency Department": ["emergency department", "a&e", "accident and emergency"],
    "Doctors": ["doctors", "medical staff", "physicians", "clinical team"],
    "Consultants": ["consultant", "senior doctor", "specialist consultant", "board member", "executives"],
    "Nurses": ["nurses", "nursing staff", "matron"],
    "Specialists": ["specialist", "clinical specialist", "allied health"],
    "Administrative Staff": ["admin", "clerical", "management", "administrative", "contact name", "board names", "ceo", "chair"],
    "MRI": ["mri", "magnetic resonance"],
    "CT Scanner": ["ct scan", "computed tomography", "cat scan"],
    "Ultrasound": ["ultrasound", "sonography", "echo"],
    "Ventilators": ["ventilator", "respirator", "breathing machine"],
    "X-Ray Systems": ["x-ray", "radiograph"],
    "Surgical Robots": ["robot", "da vinci", "robotic surgery"],
    "CQC Rating": ["cqc", "care quality commission", "inspected", "rating"],
    "Privacy Notice": ["privacy notice", "gdpr", "privacy policy"],
    "Data Protection": ["data protection", "dpo", "ico registration"],
    "Cyber Security": ["cyber security", "dsp toolkit", "firewall", "breach"],
    "Information Governance": ["information governance", "ig toolkit", "records management"],
    "Clinical Trials": ["clinical trial", "research study", "trials"],
    "Research Centres": ["research centre", "biomedical", "innovation"],
    "University Partnerships": ["university", "medical school", "academic"],
    "Publications": ["publications", "journal", "research paper"],
    "Contracts": ["contract", "awarded", "supplier"],
    "Tenders": ["tender", "bidding", "procurement portal"],
    "Equipment Procurement": ["procurement", "supply chain", "purchasing", "machinery"],
    "Technology Vendors": ["vendor", "software provider", "system provider", "epic", "cerner"],
    "Trauma Centre": ["trauma", "major trauma"],
    "Critical Care": ["critical care", "hdu", "high dependency"],
    "Air Ambulance Access": ["air ambulance", "helipad", "helicopter"]
}

# -----------------------------
# INITIALIZE STORAGE STATE
# -----------------------------
if "master_data" not in st.session_state:
    st.session_state["master_data"] = {}

# -----------------------------
# AUTOMATED PIPELINE LOGIC
# -----------------------------
def fetch_search_links(query, api_key):
    """Fetches organic search links safely from SerpApi."""
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": 5, 
        "gl": "uk",
        "hl": "en"
    }
    try:
        response = requests.get("https://serpapi.com/search", params=params, timeout=10)
        response.raise_for_status()
        results = response.json().get("organic_results", [])
        return [r.get("link") for r in results if r.get("link")]
    except Exception as e:
        st.error(f"Search failed for query '{query}': {e}")
        return []

def high_speed_scraper(urls):
    """Quietly extracts page text with strict limits and protects against non-HTML data payloads."""
    text_lines = []
    contacts = {"emails": [], "phones": []}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    status_bar = st.empty()
    
    for i, url in enumerate(urls):
        if any(url.lower().endswith(ext) for ext in ['.pdf', '.xlsx', '.xls', '.docx', '.doc', '.zip', '.pptx']):
            continue
            
        display_url = url if len(url) < 60 else f"{url[:57]}..."
        status_bar.caption(f"   ⏳ Processing source {i+1}/{len(urls)}: {display_url}")
        
        try:
            res = requests.get(url, headers=headers, timeout=2.5)
            content_type = res.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type:
                continue
                
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                
                raw_text = soup.get_text(separator="\n")
                lines = [line.strip() for line in raw_text.split("\n") if len(line.strip()) > 15]
                text_lines.extend(lines)
                
                full_text_block = " ".join(lines)
                # Global regular expression parsing filters
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', full_text_block)
                phones = re.findall(r'(?:\+44\s?7\d{3}|\+44\s?[123589]\d{1,4}|\b0[1235789]\d{1,4})\s?\d{3,4}\s?\d{3,4}\b', full_text_block)
                
                contacts["emails"].extend(emails)
                contacts["phones"].extend(phones)
        except Exception:
            continue
            
    status_bar.empty()
    return text_lines, contacts

def clean_illegal_excel_characters(val):
    """Removes all hidden non-printable control characters that trigger openpyxl export crashes."""
    if isinstance(val, str):
        return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', val)
    return val

# -----------------------------
# MAIN LAYOUT INTERFACE
# -----------------------------
st.title("🏥 UK Hospital OSINT Analyzer")

# Configuration Input Fields
col_h, col_s = st.columns([3, 2])
with col_h:
    hospital = st.text_input("Hospital Name", placeholder="Royal Free Hospital")
with col_s:
    serp_key = st.text_input("SerpApi Key", type="password", help="Enter your key from serpapi.com")

if hospital:
    st.success(f"Target Monitored: {hospital}")
    
    st.header("Search & Extraction Framework")
    st.caption("Review the target dork strings below. Clicking the unified action button below will process all pipelines consecutively.")

    # Core query matrices combined with explicit contact dorks
    queries = [
        f'"{hospital}" "email" OR "contact details" OR "phone" OR "telephone" OR "directory"',
        f'"{hospital}" "contact us" OR "get in touch" email phone @nhs.net',
        f'"{hospital}" annual report operational capacity staff workforce',
        f'"{hospital}" total beds ICU ward emergency infrastructure',
        f'site:cqc.org.uk "{hospital}" quality rating performance inspection',
        f'"{hospital}" consultants doctors board members procurement tenders contracts',
        f'"{hospital}" privacy notice data protection cyber security contact info'
    ]

    for q in queries:
        st.code(q)

    st.markdown("---")

    if st.button("🚀 Run All Queries & Extract Everything", use_container_width=True, type="primary"):
        if not serp_key or len(serp_key) < 8:
            st.error("🔑 Please supply a valid SerpApi Key before launching.")
        else:
            master_progress = st.progress(0.0)
            status_log = st.empty()
            st.session_state["master_data"] = {}
            
            # Master contact arrays to accumulate unique targets globally
            global_emails = []
            global_phones = []
            
            for idx, q in enumerate(queries):
                percent_complete = (idx) / len(queries)
                master_progress.progress(percent_complete)
                status_log.markdown(f"### 🔍 Processing Objective {idx+1}/{len(queries)}...\nRunning Search: `{q}`")
                
                discovered_urls = fetch_search_links(q, serp_key)
                
                if discovered_urls:
                    text_pool, captured_contacts = high_speed_scraper(discovered_urls)
                    
                    # Store tracked values globally
                    global_emails.extend(captured_contacts["emails"])
                    global_phones.extend(captured_contacts["phones"])
                    
                    unique_emails = list(set(global_emails))[:12] # Limit collection to the top 12 matches for visibility
                    unique_phones = list(set(global_phones))[:12]
                    contact_summary = f"Emails: {', '.join(unique_emails) if unique_emails else 'None'} | Phones: {', '.join(unique_phones) if unique_phones else 'None'}"

                    for category, fields in SCHEMA.items():
                        for field in fields:
                            
                            # Handle dedicated dataset population rules for global values
                            if field == "Hospital Emails":
                                if unique_emails:
                                    st.session_state["master_data"][field] = {
                                        "Category": "Contacts", "Field": field, "Extracted Intelligence": ", ".join(unique_emails)
                                    }
                                continue
                            elif field == "Hospital Phone Numbers":
                                if unique_phones:
                                    st.session_state["master_data"][field] = {
                                        "Category": "Contacts", "Field": field, "Extracted Intelligence": ", ".join(unique_phones)
                                    }
                                continue

                            search_tokens = KEYWORD_MAPPING.get(field, [field.lower()])
                            extracted_sentences = []
                            
                            for line in text_pool:
                                if any(token in line.lower() for token in search_tokens):
                                    extracted_sentences.append(line)
                                    if len(extracted_sentences) >= 2: 
                                        break
                            
                            raw_finding = " | ".join(extracted_sentences) if extracted_sentences else "Not Found"
                            
                            # Inject context block tags next to target management items
                            if field in ["Administrative Staff", "Consultants", "Doctors", "Workforce"] and (unique_emails or unique_phones):
                                final_intelligence = f"{raw_finding} [Global Contacts Match -> {contact_summary}]"
                            else:
                                final_intelligence = raw_finding

                            if final_intelligence != "Not Found" or field not in st.session_state["master_data"]:
                                st.session_state["master_data"][field] = {
                                    "Category": category,
                                    "Field": field,
                                    "Extracted Intelligence": final_intelligence
                                }
            
            # Post-loop cleaning fallback validation to guarantee contact rows are never completely empty
            if "Hospital Emails" not in st.session_state["master_data"]:
                st.session_state["master_data"]["Hospital Emails"] = {"Category": "Contacts", "Field": "Hospital Emails", "Extracted Intelligence": ", ".join(list(set(global_emails))[:12]) if global_emails else "Not Found"}
            if "Hospital Phone Numbers" not in st.session_state["master_data"]:
                st.session_state["master_data"]["Hospital Phone Numbers"] = {"Category": "Contacts", "Field": "Hospital Phone Numbers", "Extracted Intelligence": ", ".join(list(set(global_phones))[:12]) if global_phones else "Not Found"}

            master_progress.progress(1.0)
            status_log.success("🎉 Comprehensive Extraction Complete! Your document is compiled below.")
            st.toast("Intelligence processed into dashboard successfully!", icon="📊")

    # -----------------------------
    # LIVE MASTER DATA REPORT PANEL
    # -----------------------------
    st.divider()
    st.header("📋 Collected Intelligence Document")

   