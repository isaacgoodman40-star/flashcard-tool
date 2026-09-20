import streamlit as st
import requests

st.set_page_config(
    page_title="Inbox Cleaner",
)

st.title("Inbox Cleaner")
st.write("A privacy-first way to clean your inbox.")
st.success("The application is running.")

st.divider()

st.subheader("Connect your mailbox")
st.write(
    "Connect your email account securely using your provider's sign-in page."
)

if not st.user.is_logged_in:
    if st.button("Sign in with Google"):
        st.login("google")

else:
    st.success("Google sign-in successful.")

    if st.button("Test Gmail connection"):
        try:
            token = st.user.tokens.access

            if not isinstance(token, str) or not token:
                st.warning("No Google access token is available.")

            else:
                response = requests.get(
                    "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                    headers={
                        "Authorization": f"Bearer {token}",
                    },
                    timeout=10,
                )

                if response.status_code == 200:
                    st.success("Gmail API connection successful!")

                elif response.status_code == 401:
                    st.error(
                        "Google rejected the access token. "
                        "Try signing out and signing back in."
                    )

                elif response.status_code == 403:
                    st.error(
                        "Gmail access was denied. "
                        "We need to check the API permissions."
                    )

                else:
                    st.error(
                        "Gmail connection failed. "
                        f"HTTP status: {response.status_code}"
                    )

        except (AttributeError, KeyError):
            st.error("Google access token is unavailable.")

        except requests.RequestException:
            st.error("Could not reach the Gmail API.")

    if st.button("Sign out"):
        st.logout()

st.divider()

st.subheader("Gmail access")
st.info("Gmail mailbox access has not been connected yet.")
st.warning(
    "Gmail connection is temporarily disabled "
    "while we finish the secure authorisation process."
)
