import streamlit as st
import imaplib
import email
from email.header import decode_header
import re
from datetime import datetime, timedelta
import pandas as pd

# ----------------------
# 🔑 CONFIG
# ----------------------
ADMIN_PIN = "1234"

# ----------------------
# 🧠 DETECTION RULES
# ----------------------
MARKETING_KEYWORDS = {
    "newsletter", "subscribe", "unsubscribe", "offer", "discount", "sale", "deal",
    "promo", "coupon", "limited time", "exclusive", "shop now", "new arrival",
    "membership", "update", "digest", "weekly", "monthly", "special offer",
    "best seller", "just for you", "recommended", "trending", "last chance"
}

MARKETING_DOMAINS = {
    "mailer.com", "mailchimp.com", "sendgrid.net", "hubspot.com", "klaviyo.com",
    "convertkit.com", "activecampaign.com", "emailsender.net", "newsletter.com",
    "marketing.com", "promo-email.com", "mailerlite.com", "brevo.com"
}

SCAM_KEYWORDS = {
    "urgent", "verify your account", "suspended", "unusual activity", "login attempt",
    "click here", "confirm now", "won", "prize", "lottery", "inheritance", "bank",
    "payment failed", "update details", "security alert", "verify identity",
    "claim your", "free gift", "click to claim", "do not ignore", "action required",
    "account locked", "password expired", "validate now", "you have received"
}

PERSONAL_SIGNALS = {"@gmail.com", "@outlook.com", "@yahoo.com", "@hotmail.com", "@icloud.com", "@protonmail.com"}

# ----------------------
# 📧 IMAP CONNECTION
# ----------------------
def get_imap_settings(email_addr):
    """Return IMAP server & port for major providers"""
    domain = email_addr.lower().split("@")[-1]
    settings = {
        "gmail.com": ("imap.gmail.com", 993),
        "googlemail.com": ("imap.gmail.com", 993),
        "outlook.com": ("imap-mail.outlook.com", 993),
        "hotmail.com": ("imap-mail.outlook.com", 993),
        "live.com": ("imap-mail.outlook.com", 993),
        "yahoo.com": ("imap.mail.yahoo.com", 993),
        "icloud.com": ("imap.mail.me.com", 993),
        "protonmail.com": ("127.0.0.1", 1143),  # Local bridge — note shown
    }
    return settings.get(domain, ("imap." + domain, 993))

def connect_email(email_addr, password):
    """Secure IMAP connection — returns connection or error message"""
    try:
        server, port = get_imap_settings(email_addr)
        mail = imaplib.IMAP4_SSL(server, port)
        mail.login(email_addr, password)
        return mail, None
    except imaplib.IMAP4.error as e:
        if "Authentication failed" in str(e):
            return None, "Login failed. Did you use an App Password? See instructions below."
        return None, f"Connection error: {str(e)}"
    except Exception as e:
        return None, f"Error: {str(e)}"

def decode_str(s):
    """Decode email subject/sender safely"""
    if not s: return ""
    decoded = decode_header(s)
    parts = []
    for content, encoding in decoded:
        if isinstance(content, bytes):
            parts.append(content.decode(encoding or "utf-8", errors="replace"))
        else:
            parts.append(str(content))
    return "".join(parts)

# ----------------------
# 🏷️ CATEGORISATION
# ----------------------
def categorise_email(sender, subject, snippet=""):
    """Classify each email — returns category & confidence"""
    text = f"{sender} {subject} {snippet}".lower()
    
    # Scam check
    scam_score = sum(1 for w in SCAM_KEYWORDS if w in text)
    if scam_score >= 2:
        return "⚠️ Scam/Suspicious", f"Matched {scam_score} warning signs"
    
    # Marketing domain check
    sender_domain = sender.lower().split("@")[-1] if "@" in sender else ""
    if any(d in sender_domain for d in MARKETING_DOMAINS):
        return "📢 Marketing", "Known bulk sender domain"
    
    # Marketing keyword check
    marketing_score = sum(1 for w in MARKETING_KEYWORDS if w in text)
    if marketing_score >= 2:
        return "📢 Marketing", f"Matched {marketing_score} marketing terms"
    
    # Personal check
    if sender_domain in PERSONAL_SIGNALS and not any(c in text for c in MARKETING_KEYWORDS):
        return "👤 Personal", "From personal email domain"
    
    return "❓ Other", "Not clearly categorised"

# ----------------------
# 📥 SCAN INBOX
# ----------------------
def scan_inbox(mail, limit_days=30, max_emails=500):
    """Scan recent inbox messages — categorise each one"""
    mail.select("INBOX")
    
    # Calculate date cutoff
    cutoff = (datetime.now() - timedelta(days=limit_days)).strftime("%d-%b-%Y")
    status, messages = mail.search(None, f'SINCE "{cutoff}"')
    
    if status != "OK" or not messages[0]:
        return []
    
    email_ids = messages[0].split()[-max_emails:]  # Most recent N emails
    results = []
    
    for eid in email_ids:
        status, msg_data = mail.fetch(eid, "(RFC822)")
        if status != "OK":
            continue
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                sender = decode_str(msg.get("From", ""))
                subject = decode_str(msg.get("Subject", ""))
                date_str = msg.get("Date", "")
                
                # Get unsubscribe link if present
                unsubscribe = msg.get("List-Unsubscribe", "")
                
                category, reason = categorise_email(sender, subject)
                
                results.append({
                    "id": eid.decode() if isinstance(eid, bytes) else str(eid),
                    "from": sender,
                    "subject": subject,
                    "date": date_str,
                    "category": category,
                    "reason": reason,
                    "unsubscribe": unsubscribe[1:-1].split(",")[0] if unsubscribe.startswith("<") else unsubscribe
                })
    
    return results

# ----------------------
# 📄 PAGE SETUP
# ----------------------
st.set_page_config(page_title="Smart Inbox Cleaner", layout="wide")

st.title("🧹 Smart Inbox Cleaner")
st.subheader("Scan, sort, and clear your inbox — fast")
st.info("✨ Your login details never leave your browser — they're only used to connect securely")

# ----------------------
# 🔐 LOGIN SECTION
# ----------------------
with st.expander("📋 Important — Read First!", expanded=True):
    st.markdown("""
    ### How To Connect Securely:
    1. **Gmail**: Create an **App Password** (requires 2-Step Verification ON) → [Google Account → Security → App Passwords]
    2. **Outlook/Hotmail**: Create an **App Password** → Account Settings → Privacy
    3. **Yahoo**: Generate **App Password** → Account Info → Account Security
    4. **iCloud**: Use **App-Specific Password** → Apple ID → Password & Security
    
    ⚠️ **Do NOT use your main everyday password** — always use an App Password.
    """)

col1, col2 = st.columns(2)
with col1:
    email_addr = st.text_input("Your Email Address", placeholder="you@gmail.com")
with col2:
    password = st.text_input("App Password / Special Password", type="password", placeholder="xxxx-xxxx-xxxx-xxxx")

scan_days = st.slider("Scan emails from last...", 7, 90, 30)
max_scan = st.slider("Maximum emails to scan", 50, 500, 200)

connect_btn = st.button("🔌 Connect & Scan Inbox", type="primary")

# ----------------------
# 📊 RESULTS
# ----------------------
if connect_btn and email_addr and password:
    with st.spinner("Connecting to your inbox..."):
        mail, error = connect_email(email_addr, password)
    
    if error:
        st.error(error)
    else:
        with st.spinner(f"Scanning your last {scan_days} days..."):
            emails = scan_inbox(mail, limit_days=scan_days, max_emails=max_scan)
            mail.logout()
        
        if not emails:
            st.info("No emails found in this time range. Try increasing the scan period.")
        else:
            df = pd.DataFrame(emails)
            
            # Summary
            cats = df["category"].value_counts()
            st.success(f"✅ Scanned {len(emails)} emails")
            
            cols = st.columns(len(cats))
            for i, (cat, count) in enumerate(cats.items()):
                cols[i].metric(cat, count)
            
            # Tabs by category
            tab_all, tab_marketing, tab_scam, tab_personal, tab_other = st.tabs([
                "📋 All", "📢 Marketing", "⚠️ Scam", "👤 Personal", "❓ Other"
            ])
            
            with tab_all:
                st.dataframe(df[["category", "from", "subject", "date", "reason"]], use_container_width=True)
            
            with tab_marketing:
                m_df = df[df["category"] == "📢 Marketing"]
                if len(m_df):
                    st.dataframe(m_df[["from", "subject", "date", "unsubscribe"]], use_container_width=True)
                    st.subheader("Quick Actions")
                    st.download_button(
                        "📥 Download Marketing List",
                        m_df.to_csv(index=False).encode("utf-8"),
                        f"marketing_{datetime.now().strftime('%Y%m%d')}.csv",
                        "text/csv"
                    )
                else:
                    st.success("No marketing emails found! 🎉")
            
            with tab_scam:
                s_df = df[df["category"] == "⚠️ Scam/Suspicious"]
                if len(s_df):
                    st.dataframe(s_df[["from", "subject", "date", "reason"]], use_container_width=True)
                    st.warning("⚠️ Be extra careful with these — do NOT click links or reply!")
                else:
                    st.success("No suspicious emails found! ✅")
            
            with tab_personal:
                p_df = df[df["category"] == "👤 Personal"]
                if len(p_df):
                    st.dataframe(p_df[["from", "subject", "date"]], use_container_width=True)
                else:
                    st.info("No clearly personal emails found")
            
            with tab_other:
                o_df = df[df["category"] == "❓ Other"]
                if len(o_df):
                    st.dataframe(o_df[["from", "subject", "date", "reason"]], use_container_width=True)
                else:
                    st.success("Everything clearly categorised! 🎉")
            
            # Full export
            st.subheader("📤 Export Everything")
            st.download_button(
                "📥 Download Full Report",
                df.to_csv(index=False).encode("utf-8"),
                f"inbox_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv"
            )

# ----------------------
# 🔐 ADMIN PANEL
# ----------------------
st.divider()
pin_input = st.text_input("Admin - View Stats", type="password", key="admin_pin")
if pin_input == ADMIN_PIN:
    st.subheader("📊 App Info")
    st.info("Inbox Cleaner — Active")
    st.caption("Usage stats tracking can be added here next")
