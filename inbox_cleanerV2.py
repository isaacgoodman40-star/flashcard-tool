import streamlit as st
from google_auth_oauthlib.flow import Flow

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.metadata"]

def create_gmail_flow():
    google_config = st.secrets["google_oauth"]

    client_config = {
        "web": {
            "client_id": google_config["client_id"],
            "client_secret": google_config["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=GMAIL_SCOPES,
        redirect_uri=google_config["redirect_uri"],
    )

    return flow

st.set_page_config(
  page_title="Inbox Cleaner",
)

st.title("Inbox Cleaner")
st.write("A privacy-first way to clean your inbox.")
st.success("The application is running.")
st.divider()
st.subheader("Connect your mailbox")
st.write("connect your email account securely using your provider's sign-in page.")

if not st.user.is_logged_in:
  if st.button("Sign in with Google"):
    st.login("google")

else:
  st.success("Google sign-in successful.")
  if st.button("Sign out"):
      st.logout()

st.divider()
st.subheader("Gmail access")
st.info("Gmail mailbox access has not been connected yet.")
if st.button("connect Gmail mailbox"):
    st.info("Gmail authorisation is not configured yet.")
