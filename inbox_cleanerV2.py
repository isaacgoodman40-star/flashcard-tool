import streamlit as st

st.set_page_config(
  page_title="Inbox Cleaner",
)

st.title("Inbox Cleaner")
st.write("A privacy-first way to clean your inbox.")
st.success("The application is running.")
st.divider()
st.subheader("privacy")
st.write("Your email will only be accessed when you explicitly connect it.")
if st.button("Disconnect and clear session"):
  st.session_state.clear()
  st.rerun()
  
