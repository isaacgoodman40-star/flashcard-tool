import streamlit as st

st.set_page_config(
  page_title="Inbox Cleaner",
)

st.title("Inbox Cleaner")
st.write("A privacy-first way to clean your inbox.")
st.success("The application is running.")
st.divider()
st.subheader("Connect your mailbox")
st.write("connect your email account securely using your provider's sign-in page.")
if st.button("Connect Gmail"):
    try:
      google_config = st.secrets["google_oauth"]
      client_id = google_config["client_id"]
      client_secret = google_config["client_secret"]
      redirect_uri = google_config["redirect_uri"]
      if client_id and client_secret and redirect_uri:
        st.success("Google OAuth configuration loaded successfully.")
      else:
        st.error("Google OAuth configuration is incomplete.")
    except (KeyError, FileNotFoundError):
      st.error("Google OAuth configuration could not be found.")


  

  
