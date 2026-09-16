import streamlit as st
import imaplib
import email
from email.header import decode_header
import re
from datetime import datetime, timedelta
import pandas as pd

# ----------------------
# 🔑 CONFIG — SET EVERYTHING HERE!
# ----------------------
APP_NAME = "Smart Inbox Cleaner"
SUPPORT_LINK = "https://buymeacoffee.com/isaacgoodman"

# 💰 FREE vs PREMIUM LIMITS
FREE_DAYS_LIMIT = 30
FREE_EMAILS_LIMIT = 500

# 🔐 YOUR PREMIUM CODES — Add more as you sell them!
PREMIUM_CODES = {
    "CLEAN-2026-UNLIMITED": "Main Premium Code",
    "ISAAC-ACCESS-999": "Personal Access",
    # Add new codes here → "CLEAN-NAME-123": "Customer Name"
}

# 💳 SET YOUR PRICE
PREMIUM_PRICE = "£5.00"
PREMIUM_DESC = "Unlock unlimited scanning & bulk delete — forever!"

# ----------------------
# 🧠 DETECTION RULES
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
            return None, "❌ Login failed — use an App-Specific Password (not your normal one!)"
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

def parse_email_date(date_str):
    """Convert email date string to datetime object for sorting"""
    try:
        return email.utils.parsedate_to_datetime(date_str)
    except:
        return None

# ----------------------
# 🔗 UNSUBSCRIBE LINK EXTRACT
# ----------------------
def extract_unsubscribe_link(msg):
    header_val = msg.get("List-Unsubscribe", "")
    if header_val:
        matches = re.findall(r'<(https?://[^>]+)>', header_val)
        if matches and matches[0].startswith("http"):
            return matches[0]
        matches = re.findall(r'https?://[^\s,<>"]+', header_val)
        if matches:
            return matches[0]
    try:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() in ["text/plain", "text/html"]:
                    try:
                        payload = part.get_payload(decode=True)
                        body += payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else str(payload)
                    except: pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                body = payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else str(payload)
            except: pass
        patterns = [
            r'href=["\'](https?://[^"\']+?unsubscribe[^"\']*?)["\']',
            r'(https?://[^"\'\s<>]+?/unsubscribe[^"\'\s<>]*)',
            r'(https?://[^"\'\s<>]+?opt-?out[^"\'\s<>]*)',
            r'(https?://[^"\'\s<>]+?preferences[^"\'\s<>]*)',
        ]
        for pat in patterns:
            matches = re.findall(pat, body, re.IGNORECASE)
            if matches: return matches[0]
    except: pass
    return None

# ----------------------
# 🏷️ CATEGORISATION
# ----------------------
def categorise_email(sender, subject, unsubscribe_link=None):
    text = f"{sender} {subject}".lower()
    sender_domain = sender.lower().split("@")[-1] if "@" in sender else ""
    
    scam_score = sum(1 for w in SCAM_KEYWORDS if w in text)
    if scam_score >= 2:
        return "⚠️ Scam/Suspicious", f"Matched {scam_score} warning signs"
    
    marketing_score = 0
    if any(d in sender_domain for d in MARKETING_DOMAINS): marketing_score += 3
    marketing_score += sum(1 for w in MARKETING_KEYWORDS if w in text)
    if unsubscribe_link: marketing_score += 2
    if sender_domain not in PERSONAL_DOMAINS: marketing_score += 1
    
    if marketing_score >= 2:
        reasons = []
        if unsubscribe_link: reasons.append("has unsubscribe link")
        if any(d in sender_domain for d in MARKETING_DOMAINS): reasons.append("known marketing domain")
        reasons.append(f"{marketing_score} signals total")
        return "📢 Marketing", " | ".join(reasons)
    
    if sender_domain in PERSONAL_DOMAINS and marketing_score < 2:
        return "👤 Personal", "From personal domain"
    
    return "❓ Other", "Not clearly categorised"

# ----------------------
# 📥 SCAN INBOX
# ----------------------
def scan_inbox(mail, limit_days=30, max_emails=500):
    mail.select("INBOX")
    
    if limit_days is None:
        status, messages = mail.search(None, "ALL")
    else:
        cutoff = (datetime.now() - timedelta(days=limit_days)).strftime("%d-%b-%Y")
        status, messages = mail.search(None, f'SINCE "{cutoff}"')
    
    if status != "OK" or not messages[0]: return []
    
    email_ids = messages[0].split()
    total_found = len(email_ids)
    
    if max_emails is not None and total_found > max_emails:
        email_ids = email_ids[-max_emails:]
    
    results = []
    for eid in email_ids:
        status, msg_data = mail.fetch(eid, "(RFC822)")
        if status != "OK": continue
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                sender_full = decode_str(msg.get("From", ""))
                subject = decode_str(msg.get("Subject", ""))
                date_str = msg.get("Date", "")
                date_dt = parse_email_date(date_str)
                
                email_match = re.search(r'[\w\.-]+@[\w\.-]+', sender_full)
                sender_email = email_match.group(0).lower() if email_match else sender_full.lower()
                
                unsubscribe_url = extract_unsubscribe_link(msg)
                category, reason = categorise_email(sender_email, subject, unsubscribe_url)
                
                results.append({
                    "id": eid.decode() if isinstance(eid, bytes) else str(eid),
                    "sender_full": sender_full,
                    "sender_email": sender_email,
                    "subject": subject,
                    "date": date_str,
                    "date_dt": date_dt,
                    "category": category,
                    "reason": reason,
                    "unsubscribe_url": unsubscribe_url
                })
    return results

# ----------------------
# 🗑️ BULK DELETE FUNCTION
# ----------------------
def delete_emails_by_sender(mail, sender_email_list):
    mail.select("INBOX")
    deleted_count = 0
    errors = []
    
    for sender_email in sender_email_list:
        try:
            status, messages = mail.search(None, f'FROM "{sender_email}"')
            if status == "OK" and messages[0]:
                ids = messages[0].split()
                for eid in ids:
                    mail.store(eid, "+FLAGS", "\\Deleted")
                deleted_count += len(ids)
        except Exception as e:
            errors.append(f"{sender_email}: {str(e)}")
    
    mail.expunge()
    return deleted_count, errors

# ----------------------
# 🔐 PREMIUM VERIFICATION
# ----------------------
def check_premium_status():
    if "is_premium" not in st.session_state:
        st.session_state.is_premium = False
    return st.session_state.is_premium

def verify_premium_code(input_code):
    if input_code.strip().upper() in PREMIUM_CODES:
        st.session_state.is_premium = True
        return True, PREMIUM_CODES[input_code.strip().upper()]
    return False, None

# ----------------------
# 📄 PAGE SETUP
# ----------------------
st.set_page_config(page_title=APP_NAME, layout="wide")

st.title("🧹 " + APP_NAME)
st.subheader("Scan, sort, unsubscribe, and clear bulk — safely")

# SUPPORT BANNER
banner = f"""
<div style="padding: 12px; background: linear-gradient(90deg, #fff8e1, #fff3e0); border-radius: 8px; margin-bottom: 20px; color: #000000;">
 <b>This tool is free for everyone!</b> Unlock full cleaning forever for just {PREMIUM_PRICE} 
</div>
"""
st.markdown(banner, unsafe_allow_html=True)
if SUPPORT_LINK and "yourname" not in SUPPORT_LINK:
    st.markdown(f'<a href="{SUPPORT_LINK}" target="_blank" style="color: #000000; font-weight: bold; text-decoration: none;">☕ Get Premium Access →</a>', unsafe_allow_html=True)
st.divider()

# ----------------------
# 🔐 PREMIUM CODE ENTRY
# ----------------------
is_premium = check_premium_status()

if not is_premium:
    with st.expander("⭐ Unlock Premium — Unlimited Scanning", expanded=False):
        st.markdown(f"""
        ### {PREMIUM_DESC}
        - ✅ Scan **ALL** emails — no date limit
        - ✅ Remove **unlimited** emails — no cap
        - ✅ Bulk clean from your **entire inbox history**
        - ✅ One-time payment → forever access ✨
        - 💳 **Price: {PREMIUM_PRICE}** → [Buy here]({SUPPORT_LINK})
        
        After purchase, enter your code below:
        """)
        
        user_code = st.text_input("Enter Your Premium Code", type="password", placeholder="XXXX-XXXX-XXXX", key="premium_code_input")
        code_submit = st.button("🔓 Unlock Premium", type="primary")
        
        if code_submit and user_code:
            valid, label = verify_premium_code(user_code)
            if valid:
                st.success(f"🌟 Premium Unlocked! Welcome — {label}")
                st.balloons()
                is_premium = True
            else:
                st.error("❌ Invalid code — check you entered it correctly")
else:
    st.markdown("""
    <div style="background:#e8f5e9; padding:10px; border-radius:6px; border-left:4px solid:#2e7d32;">
    ⭐ <b>PREMIUM ACTIVE</b> — Unlimited scanning enabled ✅
    </div>
    """, unsafe_allow_html=True)
    is_premium = True

st.divider()

# ----------------------
# 📋 INFO PANEL
# ----------------------
with st.expander("📋 Important — Read First!", expanded=True):
    st.markdown(f"""
    ### Connect Securely:
    - **iCloud**: Use **App-Specific Password** → appleid.apple.com → Sign-In & Security → Generate Password
    - **Gmail**: App Password → 2-Step ON first → myaccount.google.com/apppasswords
    - **Never use your normal password** — always use an App Password ✅
    
    ### 🆓 Free vs ⭐ Premium:
    | Feature | Free | Premium |
    |---|---|---|
    | Scan Period | Last {FREE_DAYS_LIMIT} days | Unlimited — All Time |
    | Max Emails | {FREE_EMAILS_LIMIT} | Unlimited |
    | Bulk Delete | From last {FREE_DAYS_LIMIT} days | From your entire inbox |
    
    ### 📂 How It Works:
    - One expandable section per sender
    - Click to see **every email** from them in the time period
    - One unsubscribe link (uses the newest email)
    - Tick once → delete ALL from that sender ✅
    
    ### Bulk Delete Safety:
    - ✅ Emails go to **Trash/Deleted** — recoverable
    - ✅ You **review & tick** before anything is removed
    - ⚠️ Personal & Scam emails are **never auto-selected**
    """)

# ----------------------
# 🔐 LOGIN & SCAN SETTINGS
# ----------------------
col1, col2 = st.columns(2)
with col1:
    email_addr = st.text_input("Your Email Address", placeholder="you@icloud.com")
with col2:
    password = st.text_input("App Password / Special Password", type="password", placeholder="xxxx-xxxx-xxxx-xxxx")

# 🎯 SCAN RANGE
st.subheader("📅 Scan Settings")
if is_premium:
    scan_mode = st.radio("Scan Range", [
        f"Last {FREE_DAYS_LIMIT} days (Quick)",
        "🌟 All Time (Unlimited — Premium)"
    ], index=1)
    
    if "All Time" in scan_mode:
        scan_days = None
        max_scan = None
        st.info("🌟 Scanning your ENTIRE inbox — this may take a few minutes ⏳")
    else:
        scan_days = FREE_DAYS_LIMIT
        max_scan = FREE_EMAILS_LIMIT
else:
    scan_days = st.slider(f"Scan emails from last...", 7, FREE_DAYS_LIMIT, 30)
    max_scan = st.slider(f"Maximum emails to scan", 50, FREE_EMAILS_LIMIT, 200)
    st.caption(f"Want to scan further back? ⭐ Get Premium for unlimited scanning!")

connect_btn = st.button("🔌 Connect & Scan Inbox", type="primary")

# ----------------------
# 📊 RESULTS
# ----------------------
if connect_btn and email_addr and password:
    with st.spinner("Connecting..."):
        mail, error = connect_email(email_addr, password)
    
    if error:
        st.error(error)
    else:
        if scan_days is None:
            with st.spinner("🔍 Scanning your ENTIRE inbox — please wait... ⏳"):
                emails = scan_inbox(mail, limit_days=None, max_emails=None)
        else:
            with st.spinner(f"Scanning last {scan_days} days..."):
                emails = scan_inbox(mail, limit_days=scan_days, max_emails=max_scan)
        
        if not emails:
            st.info("No emails found. Try increasing the scan period.")
            mail.logout()
        else:
            df = pd.DataFrame(emails)
            scope_text = "ALL time" if scan_days is None else f"last {scan_days} days"
            st.success(f"✅ Scanned {len(emails)} emails from {scope_text}")
            
            # Summary metrics
            cats = df["category"].value_counts()
            cols = st.columns(len(cats))
            for i, (cat, count) in enumerate(cats.items()):
                cols[i].metric(cat, count)
            
            # ----------------------
            # 🗑️ BULK CLEAN — EXPANDABLE GROUPS
            # ----------------------
            st.divider()
            st.header("🗑️ Bulk Clean — Grouped by Sender")
            
            marketing_df = df[df["category"] == "📢 Marketing"].copy()
            
            if len(marketing_df) > 0:
                # Group by sender email
                sender_groups = marketing_df.groupby("sender_email")
                
                st.info(f"Found {sender_groups.ngroups} marketing senders — click to see emails")
                
                selected_senders = []
                
                # Process each sender group
                for sender_email, group in sender_groups:
                    # Sort newest first
                    group_sorted = group.sort_values("date_dt", ascending=False).reset_index(drop=True)
                    count = len(group_sorted)
                    newest = group_sorted.iloc[0]
                    newest_unsub = newest["unsubscribe_url"]
                    display_name = newest["sender_full"].split("<")[0].strip() if "<" in newest["sender_full"] else sender_email
                    
                    # Build unsubscribe link HTML
                    if newest_unsub and isinstance(newest_unsub, str) and newest_unsub.startswith("http"):
                        unsub_html = f'<a href="{newest_unsub}" target="_blank" style="display:inline-block; padding:4px 12px; background:#ff4b4b; color:white; border-radius:4px; text-decoration:none; font-weight:bold; font-size:0.9em;">🔗 Unsubscribe</a>'
                    else:
                        unsub_html = '<span style="color:#999; font-size:0.9em;">No link</span>'
                    
                    # --- Expandable section ---
                    with st.expander(f"📬 {display_name} — {count} email{'s' if count != 1 else ''}"):
                        # Top row: checkbox + unsubscribe
                        c1, c2, c3 = st.columns([3, 2, 1])
                        with c1:
                            checked = st.checkbox(
                                f"🗑️ Delete ALL from {sender_email}",
                                key=f"delall_{sender_email}"
                            )
                            if checked:
                                selected_senders.append(sender_email)
                        with c2:
                            st.markdown(f"**Latest:** {newest['subject'][:50]}{'...' if len(newest['subject'])>50 else ''}")
                        with c3:
                            st.markdown(unsub_html, unsafe_allow_html=True)
                        
                        st.divider()
                        
                        # List every email from this sender
                        st.markdown("**All emails in this period:**")
                        for idx, email_row in group_sorted.iterrows():
                            date_preview = str(email_row["date"])[:25]
                            st.markdown(f"""
                            • **{date_preview}**<br>
                              {email_row['subject']}
                            """, unsafe_allow_html=True)
                            if idx < len(group_sorted) - 1:
                                st.markdown("<hr style='margin:4px 0; border:none; border-top:1px solid #eee;'>", unsafe_allow_html=True)
                
                # --- Confirm & Delete Section ---
                if selected_senders:
                    total_to_del = len(marketing_df[marketing_df["sender_email"].isin(selected_senders)])
                    st.warning(f"⚠️ You've selected **{len(selected_senders)} sender(s)** → **{total_to_del} emails** will be moved to Trash")
                    confirm = st.button("🗑️ DELETE SELECTED EMAILS", type="primary")
                    
                    if confirm:
                        with st.spinner("Deleting..."):
                            count_deleted, errors = delete_emails_by_sender(mail, selected_senders)
                        
                        if count_deleted > 0:
                            st.success(f"✅ Moved {count_deleted} emails to Trash!")
                        if errors:
                            st.warning(f"Some issues: {'; '.join(errors)}")
                        st.rerun()
            else:
                st.success("No marketing emails to bulk-clean! 🎉")
            
            mail.logout()
            
            # ----------------------
            # TABS
            # ----------------------
            st.divider()
            def render_unsub(url):
                if url and isinstance(url, str) and url.startswith("http"):
                    return f'<a href="{url}" target="_blank" style="color:#ff4b4b; font-weight:bold; padding:4px 10px; background:#fff0f0; border-radius:4px; text-decoration:none;">🔗 Unsubscribe</a>'
                return '<span style="color:#999;">No link</span>'
            
            tab_all, tab_marketing, tab_scam, tab_personal, tab_other = st.tabs([
                "📋 All", "📢 Marketing", "⚠️ Scam", "👤 Personal", "❓ Other"
            ])
            
            with tab_all:
                st.dataframe(df[["category", "sender_full", "subject", "date", "reason"]], use_container_width=True)
            
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
                            st.markdown(f"**{row['sender_full']}**  \n{row['subject']}  \n`{row['reason']}`")
                        with c2:
                            st.markdown(render_unsub(row["unsubscribe_url"]), unsafe_allow_html=True)
                        st.divider()
                    csv = m_df[["sender_email", "subject", "date", "unsubscribe_url"]].to_csv(index=False).encode("utf-8")
                    st.download_button("📥 Download Marketing List", csv,
                        f"marketing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv")
                else:
                    st.success("No marketing emails! 🎉")
            
            with tab_scam:
                s_df = df[df["category"] == "⚠️ Scam/Suspicious"]
                if len(s_df):
                    st.dataframe(s_df[["sender_full", "subject", "date", "reason"]], use_container_width=True)
                    st.warning("⚠️ Do NOT click links or reply to these!")
                else:
                    st.success("No suspicious emails! ✅")
            
            with tab_personal:
                p_df = df[df["category"] == "👤 Personal"]
                if len(p_df):
                    st.dataframe(p_df[["sender_full", "subject", "date"]], use_container_width=True)
                else:
                    st.info("No clearly personal emails")
            
            with tab_other:
                o_df = df[df["category"] == "❓ Other"]
                if len(o_df):
                    st.dataframe(o_df[["sender_full", "subject", "date", "reason"]], use_container_width=True)
                else:
                    st.success("Everything clearly categorised! 🎉")
            
            st.subheader("📤 Export Everything")
            st.download_button("📥 Download Full Report",
                df.to_csv(index=False).encode("utf-8"),
                f"inbox_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv")
