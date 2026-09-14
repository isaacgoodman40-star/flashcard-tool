import streamlit as st
import pandas as pd
from fpdf import FPDF
from io import BytesIO
from datetime import datetime
import json

# ----------------------
# 🔑 CONFIG — UPDATE THESE!
# ----------------------
MAX_FREE_CARDS = 99999  # Unlimited for everyone!
ADMIN_PIN = "1234"  # ⚡ CHANGE THIS to your own secret PIN!

# Google Sheets Settings
GSHEET_SPREADSHEET_ID = "CTRN1LvOOVB9L9X5u-GUc_DGsWdNZUqSvoCgI9pp4PX0"
GSHEET_SHEET_NAME = "usage_stats"

# ----------------------
# 📊 GOOGLE SHEETS INTEGRATION
# ----------------------
def get_gsheets_credentials():
    """Load credentials from Streamlit secrets or local file"""
    if "gcp_service_account" in st.secrets:
        return dict(st.secrets["gcp_service_account"])
    return None

def log_to_gsheet(event_type, extra=None):
    """Log usage data directly to Google Sheets"""
    try:
        from googleapiclient.discovery import build
        from google.oauth2.service_account import Credentials
        
        creds_dict = get_gsheets_credentials()
        if not creds_dict:
            return False  # Skip if no credentials set yet
            
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        service = build("sheets", "v4", credentials=creds)
        
        # Prepare row data
        row = [
            datetime.now().isoformat(),
            event_type,
            str(extra.get("count", "") if extra else "")
        ]
        
        body = {"values": [row]}
        service.spreadsheets().values().append(
            spreadsheetId=GSHEET_SPREADSHEET_ID,
            range=f"{GSHEET_SHEET_NAME}!A:C",
            valueInputOption="RAW",
            body=body
        ).execute()
        return True
    except Exception:
        return False

def get_stats_from_gsheet():
    """Pull and calculate stats from Google Sheets"""
    try:
        from googleapiclient.discovery import build
        from google.oauth2.service_account import Credentials
        
        creds_dict = get_gsheets_credentials()
        if not creds_dict:
            return None
            
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        service = build("sheets", "v4", credentials=creds)
        
        result = service.spreadsheets().values().get(
            spreadsheetId=GSHEET_SPREADSHEET_ID,
            range=f"{GSHEET_SHEET_NAME}!A:C"
        ).execute()
        
        rows = result.get("values", [])
        if not rows:
            return {"total_loads": 0, "total_generations": 0, "total_cards_made": 0, "recent": []}
        
        total_loads = sum(1 for r in rows if len(r)>=2 and r[1]=="app_load")
        total_gens = sum(1 for r in rows if len(r)>=2 and r[1]=="generate")
        total_cards = sum(int(r[2]) for r in rows if len(r)>=3 and r[2].isdigit())
        
        return {
            "total_loads": total_loads,
            "total_generations": total_gens,
            "total_cards_made": total_cards,
            "recent": rows[-10:]  # Last 10 entries
        }
    except Exception:
        return None

# ----------------------
# 📝 LOCAL FALLBACK LOGGING
# ----------------------
USAGE_LOG_FILE = "usage_stats.json"

def log_usage(event_type, extra=None):
    """Log to Google Sheets first, fall back to local file"""
    logged_to_gsheet = log_to_gsheet(event_type, extra)
    
    # Always keep local copy too
    try:
        try:
            with open(USAGE_LOG_FILE, "r") as f:
                stats = json.load(f)
        except FileNotFoundError:
            stats = {"total_loads": 0, "total_generations": 0, "total_cards_made": 0, "sessions": []}
        
        if event_type == "app_load":
            stats["total_loads"] += 1
        elif event_type == "generate":
            stats["total_generations"] += 1
            stats["total_cards_made"] += extra.get("count", 0)
        
        stats["sessions"].append({
            "time": datetime.now().isoformat(),
            "event": event_type,
            "extra": extra or {}
        })
        
        if len(stats["sessions"]) > 200:
            stats["sessions"] = stats["sessions"][-200:]
        
        with open(USAGE_LOG_FILE, "w") as f:
            json.dump(stats, f, indent=2)
    except Exception:
        pass

def get_stats():
    """Prefer Google Sheets data, fall back to local"""
    gsheet_stats = get_stats_from_gsheet()
    if gsheet_stats and gsheet_stats["total_loads"] > 0:
        return gsheet_stats
    
    try:
        with open(USAGE_LOG_FILE, "r") as f:
            return json.load(f)
    except:
        return {"total_loads": 0, "total_generations": 0, "total_cards_made": 0, "sessions": []}

# ----------------------
# � PAGE SETUP
# ----------------------
st.set_page_config(page_title="Smart Flashcard Generator", layout="wide")

if "logged_load" not in st.session_state:
    log_usage("app_load")
    st.session_state.logged_load = True

st.title("📝 Smart Flashcard Generator")
st.subheader("Turn your notes into study cards — instantly")
st.info("✨ Beta — unlimited cards for everyone! No sign-up required.")

# ----------------------
# 📄 PDF EXPORT FUNCTION
# ----------------------
class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "Flashcards", ln=True, align="C")
        self.ln(5)

def create_pdf(cards):
    pdf = PDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    
    page_width = pdf.w - 2 * pdf.l_margin
    
    for i, card in enumerate(cards, 1):
        pdf.set_fill_color(230, 240, 255)
        pdf.multi_cell(page_width, 7, f"Q{i}: {card['question']}", fill=True)
        pdf.multi_cell(page_width, 6, f"A: {card['answer']}")
        pdf.ln(4)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(4)
    
    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return bytes(buffer.read())

# ----------------------
# 🔍 CARD PARSING
# ----------------------
def parse_notes(text):
    cards = []
    lines = text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "=" in line:
            q, a = line.split("=", 1)
            cards.append({"question": q.strip(), "answer": a.strip()})
        elif ":" in line:
            q, a = line.split(":", 1)
            cards.append({"question": q.strip(), "answer": a.strip()})
    return cards

# ----------------------
# 🎯 MAIN APP
# ----------------------
input_text = st.text_area(
    "Paste your notes below",
    height=200,
    placeholder="Examples:\nCapital of France = Paris\nPhotosynthesis: Plants use sunlight to make energy"
)

generate_btn = st.button("✨ Generate Flashcards", type="primary")

if generate_btn and input_text:
    raw_cards = parse_notes(input_text)
    
    if not raw_cards:
        st.warning("⚠️ Couldn't detect cards. Use `question = answer` or `question: answer` format")
    else:
        log_usage("generate", {"count": len(raw_cards)})
        st.success(f"✅ Generated {len(raw_cards)} cards!")
        display_cards = raw_cards
        
        st.subheader("✏️ Review & Edit Cards")
        edited_cards = []
        for idx, card in enumerate(display_cards):
            with st.expander(f"Card {idx+1}", expanded=True):
                q = st.text_input(f"Question {idx+1}", value=card["question"], key=f"q_{idx}")
                a = st.text_input(f"Answer {idx+1}", value=card["answer"], key=f"a_{idx}")
                edited_cards.append({"question": q, "answer": a})
        
        st.subheader("📤 Export Your Cards")
        col1, col2 = st.columns(2)
        
        with col1:
            pdf_bytes = create_pdf(edited_cards)
            st.download_button(
                label="📄 Download PDF (Printable)",
                data=pdf_bytes,
                file_name="my_flashcards.pdf",
                mime="application/pdf"
            )
        
        with col2:
            df = pd.DataFrame(edited_cards)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="🃏 Download CSV (Anki-ready)",
                data=csv,
                file_name="my_flashcards.csv",
                mime="text/csv"
            )

# ----------------------
# 🔐 ADMIN PANEL
# ----------------------
st.divider()
pin_input = st.text_input("Admin — View Stats", type="password", key="admin_pin")
if pin_input == ADMIN_PIN:
    stats = get_stats()
    if stats:
        st.subheader("📊 Live Usage Dashboard")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Total Visits", stats.get("total_loads", 0))
        col_b.metric("Card Generations", stats.get("total_generations", 0))
        col_c.metric("Total Cards Created", stats.get("total_cards_made", 0))
        
        st.caption("✅ Data synced to Google Sheets — permanent & accessible anywhere")
        
        if "recent" in stats and stats["recent"]:
            with st.expander("📋 Recent Activity"):
                for row in reversed(stats["recent"]):
                    if isinstance(row, list) and len(row) >= 2:
                        st.write(f"{row[0]} — {row[1]} {f'({row[2]} cards)' if len(row)>=3 and row[2] else ''}")
