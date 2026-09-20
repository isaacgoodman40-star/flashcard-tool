import streamlit as st
import requests

GMAIL_METADATA_SCOPE = "https://www.googleapis.com/auth/gmail.metadata"

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

    if st.button("Verify Gmail permission"):
        try:
            token = st.user.tokens.access

            if not isinstance(token, str) or not token:
                st.warning("No Google access token was returned.")

            else:
                response = requests.get(
                    "https://oauth2.googleapis.com/tokeninfo",
                    params={"access_token": token},
                    timeout=10,
                )
                response.raise_for_status()

                granted_scopes = response.json().get("scope", "").split()

                if GMAIL_METADATA_SCOPE in granted_scopes:
                    st.success("Gmail metadata permission confirmed!")
                else:
                    st.warning(
                        "Google access token found, but Gmail metadata "
                        "permission was not confirmed."
                    )

        except (AttributeError, KeyError):
            st.error("Token access is not available in this configuration.")

        except requests.RequestException:
            st.error("Could not verify the permission with Google.")

    if st.button("Sign out"):
        st.logout()

st.divider()

st.subheader("Gmail access")
st.info("Gmail mailbox access has not been connected yet.")
st.warning(
    "Gmail connection is temporarily disabled "
    "while we finish the secure authorisation process."
)
