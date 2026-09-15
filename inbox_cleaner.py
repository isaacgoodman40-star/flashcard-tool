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
# 🧠 DETECTION RULES — EXPANDED & MORE ACCURATE
# ----------------------
MARKETING_KEYWORDS = {
   "newsletter", "subscribe", "unsubscribe", "offer", "discount", "sale", "deal",
   "promo", "coupon", "limited time", "exclusive", "shop now", "new arrival",
   "membership", "update", "digest", "weekly", "monthly", "special offer",
   "best seller", "just for you", "recommended", "trending", "last chance",
   "save", "off", "order", "purchase", "basket", "cart", "checkout",
   "view in browser", "preferences", "email settings", "delivered by",
   "powered by", "mail from", "this email was sent by", "campaign", "broadcast",
   "edition", "issue", "news", "latest", "what's new", "coming soon",
   "don't miss", "reminder", "expires", "ending soon", "today only"
}

MARKETING_DOMAINS = {
   "mailchimp.com", "sendgrid.net", "hubspot.com", "klaviyo.com",
   "convertkit.com", "activecampaign.com", "mailerlite.com", "brevo.com",
   "emarsys.net", "salesforce.com", "marketo.com", "pardot.com",
   "constantcontact.com", "campaignmonitor.com", "ontraport.com",
   "drip.com", "convertkit-mail.com", "newsletter", "marketing"
}

SCAM_KEYWORDS = {
   "urgent", "verify your account", "suspended", "unusual activity", "login attempt",
   "click here", "confirm now", "won", "prize", "lottery", "inheritance", "bank",
   "payment failed", "update details", "security alert", "verify identity",
   "claim your", "free gift", "click to claim", "do not ignore", "action required",
   "account locked", "password expired", "validate now", "you have received"
}

PERSONAL_DOMAINS = {"gmail.com", "outlook.com", "yahoo.com", "hotmail.com", "icloud.com", "protonmail.com", "pm.me"}

# ----------------------
# 📧 IMAP CONNECTION
# ----------------------
def get_imap_settings(email_addr):
   domain = email_addr.lower().split("@")[-1]
   settings = {
       "gmail.com": ("imap.gmail.com", 993),
       "googlemail.com": ("imap.gmail.com", 993),
       "outlook.com": ("imap-mail.outlook.com", 993),
       "hotmail.com": ("imap-mail.outlook.com", 993),
       "live.com": ("imap-mail.outlook.com", 993),
       "yahoo.com": ("imap.mail.yahoo.com", 993),
       "icloud.com": ("imap.mail.me.com", 993),
   }
   return settings.get(domain, ("imap." + domain, 993))

def connect_email(email_addr, password):
   try:
       server, port = get_imap_settings(email_addr)
       mail = imaplib.IMAP4_SSL(server, port)
       mail.login(email_addr, password)
       return mail, None
   except imaplib.IMAP4.error as e:
       if "Authentication failed" in str(e):
           return None, "Login failed. Did you use an App Password?"
       return None, f"Connection error: {str(e)}"
   except Exception as e:
       return None, f"Error: {str(e)}"

def decode_str(s):
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
# 🔗 FIND UNSUBSCRIBE — NOW SEARCHES BOTH HEADER + BODY
# ----------------------
def extract_unsubscribe_link(msg):
   """Find unsubscribe link — header FIRST (most reliable), then search body"""
   # Method 1: Official List-Unsubscribe header (most reliable)
   header_val = msg.get("List-Unsubscribe", "")
   if header_val:
       matches = re.findall(r'<(https?://[^>]+)>', header_val)
       if matches and matches[0].startswith("http"):
           return matches[0]
       matches = re.findall(r'https?://[^\s,<>"]+', header_val)
       if matches:
           return matches[0]

   # Method 2: Search email body for unsubscribe links
   try:
       body = ""
       if msg.is_multipart():
           for part in msg.walk():
               if part.get_content_type() in ["text/plain", "text/html"]:
                   try:
                       payload = part.get_payload(decode=True)
                       if isinstance(payload, bytes):
                           body += payload.decode("utf-8", errors="ignore")
                       else:
                           body += str(payload)
                   except:
                       pass
       else:
           try:
               payload = msg.get_payload(decode=True)
               if isinstance(payload, bytes):
                   body = payload.decode("utf-8", errors="ignore")
               else:
                   body = str(payload)
           except:
               pass

       # Search body for unsubscribe links — most common patterns
       patterns = [
           r'href=["\'](https?://[^"\']+?unsubscribe[^"\']*?)["\']',
           r'(https?://[^"\'\s<>]+?/unsubscribe[^"\'\s<>]*)',
           r'(https?://[^"\'\s<>]+?opt-?out[^"\'\s<>]*)',
           r'(https?://[^"\'\s<>]+?preferences[^"\'\s<>]*)',
       ]
       for pat in patterns:
           matches = re.findall(pat, body, re.IGNORECASE)
           if matches:
               return matches[0]
   except:
       pass

   return None

# ----------------------
# 🏷️ CATEGORISATION — IMPROVED LOGIC
# ----------------------
def categorise_email(sender, subject, unsubscribe_link=None):
   text = f"{sender} {subject}".lower()
   sender_domain = sender.lower().split("@")[-1] if "@" in sender else ""

   # SCAM CHECK
   scam_score = sum(1 for w in SCAM_KEYWORDS if w in text)
   if scam_score >= 2:
       return "⚠️ Scam/Suspicious", f"Matched {scam_score} warning signs"

   # MARKETING CHECK — IMPROVED: unsub link = STRONG signal
   marketing_score = 0

   # Signal 1: Known marketing domain
   if any(d in sender_domain for d in MARKETING_DOMAINS):
       marketing_score += 3

   # Signal 2: Keywords in subject/sender
   marketing_score += sum(1 for w in MARKETING_KEYWORDS if w in text)

   # Signal 3: HAS unsubscribe link = DEFINITELY marketing!
   if unsubscribe_link:
       marketing_score += 2

   # Signal 4: NOT from a personal domain
   if sender_domain not in PERSONAL_DOMAINS:
       marketing_score += 1

   # DECISION
   if marketing_score >= 2:
       reasons = []
       if unsubscribe_link: reasons.append("has unsubscribe link")
       if any(d in sender_domain for d in MARKETING_DOMAINS): reasons.append("known marketing domain")
       reasons.append(f"{marketing_score} signals total")
       return "📢 Marketing", " | ".join(reasons)

   # PERSONAL CHECK
   if sender_domain in PERSONAL_DOMAINS and marketing_score < 2:
       return "👤 Personal", "From personal domain"

   return "❓ Other", "Not clearly categorised"

# ----------------------
# 📥 SCAN INBOX
# ----------------------
def scan_inbox(mail, limit_days=30, max_emails=500):
   mail.select("INBOX")
   cutoff = (datetime.now() - timedelta(days=limit_days)).strftime("%d-%b-%Y")
   status, messages = mail.search(None, f'SINCE "{cutoff}"')

   if status != "OK" or not messages[0]:
       return []

   email_ids = messages[0].split()[-max_emails:]
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

               # Find unsubscribe FIRST — use it for categorisation!
               unsubscribe_url = extract_unsubscribe_link(msg)

               # Pass unsubscribe link to categoriser
               category, reason = categorise_email(sender, subject, unsubscribe_url)

               results.append({
                   "id": str(eid),
                   "from": sender,
                   "subject": subject,
                   "date": date_str,
                   "category": category,
                   "reason": reason,
                   "unsubscribe_url": unsubscribe_url
               })

   return results

# ----------------------
# 📄 PAGE SETUP
# ----------------------
st.set_page_config(page_title="Smart Inbox Cleaner", layout="wide")

st.title("🧹 Smart Inbox Cleaner")
st.subheader("Scan, sort, and clear your inbox — fast")
st.info("✨ Your login details never leave your browser — used only for this session")

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
           st.info("No emails found. Try increasing the scan period.")
       else:
           df = pd.DataFrame(emails)

           st.success(f"✅ Scanned {len(emails)} emails")
           cats = df["category"].value_counts()
           cols = st.columns(len(cats))
           for i, (cat, count) in enumerate(cats.items()):
               cols[i].metric(cat, count)

           def render_unsub(url):
               if url and isinstance(url, str) and url.startswith("http"):
                   return f'<a href="{url}" target="_blank" style="color:#ff4b4b; font-weight:bold; padding:4px 10px; background:#fff0f0; border-radius:4px; text-decoration:none; display:inline-block;">🔗 Unsubscribe</a>'
               return '<span style="color:#999; font-size:0.8em;">No link</span>'

           tab_all, tab_marketing, tab_scam, tab_personal, tab_other = st.tabs([
               "📋 All", "📢 Marketing", "⚠️ Scam", "👤 Personal", "❓ Other"
           ])

           with tab_all:
               st.dataframe(df[["category", "from", "subject", "date", "reason"]], use_container_width=True)

           with tab_marketing:
               m_df = df[df["category"] == "📢 Marketing"].reset_index(drop=True)
               if len(m_df):
                   st.subheader(f"Found {len(m_df)} marketing emails")
                   unsub_count = m_df["unsubscribe_url"].notna().sum()
                   st.caption(f"✅ Has unsubscribe link: {unsub_count} / {len(m_df)}")
                   st.divider()

                   for _, row in m_df.iterrows():
                       c1, c2 = st.columns([5, 1])
                       with c1:
                           st.markdown(f"**{row['from']}**  \n{row['subject']}  \n`{row['reason']}`")
                       with c2:
                           st.markdown(render_unsub(row["unsubscribe_url"]), unsafe_allow_html=True)
                       st.divider()

                   csv = m_df[["from", "subject", "date", "unsubscribe_url"]].to_csv(index=False).encode("utf-8")
                   st.download_button(
                       "📥 Download Marketing List",
                       csv,
                       f"marketing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                       "text/csv"
                   )
               else:
                   st.success("No marketing emails found! 🎉")

           with tab_scam:
               s_df = df[df["category"] == "⚠️ Scam/Suspicious"]
               if len(s_df):
                   st.dataframe(s_df[["from", "subject", "date", "reason"]], use_container_width=True)
                   st.warning("⚠️ Do NOT click links or reply to these!")
               else:
                   st.success("No suspicious emails! ✅")

           with tab_personal:
               p_df = df[df["category"] == "👤 Personal"]
               if len(p_df):
                   st.dataframe(p_df[["from", "subject", "date"]], use_container_width=True)
               else:
                   st.info("No clearly personal emails")

           with tab_other:
               o_df = df[df["category"] == "❓ Other"]
               if len(o_df):
                   st.dataframe(o_df[["from", "subject", "date", "reason"]], use_container_width=True)
               else:
                   st.success("Everything clearly categorised! 🎉")

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
   st.info("Inbox Cleaner — Enhanced Detection")
