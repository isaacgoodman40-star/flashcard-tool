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

if not st.user.is_logged_in:
  if st.button("Sign in with Google"):
    st.login("google")

else:
  st.success("Google sign-in successful.")
  if st.button("Sign out"):
      st.logout()

st.divider()
st.subheader("Gmail access")
if st.user.is_loggid_in:
    st.info("You are signed in. Gmail mailbox access has not been connected yet.")
else:
  st.warning("Please sign in with Google before connecting Gmail.")


  

  
