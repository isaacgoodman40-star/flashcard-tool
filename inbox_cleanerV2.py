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
    st.info("Gmail connection will be added in the next step.")
  

  
