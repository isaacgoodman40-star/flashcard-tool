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

    # -------------------------------------------------
    # Test Gmail connection
    # -------------------------------------------------

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
                    st.error("Gmail access was denied.")

                else:
                    st.error(
                        "Gmail connection failed. "
                        f"HTTP status: {response.status_code}"
                    )

        except (AttributeError, KeyError):
            st.error("Google access token is unavailable.")

        except requests.RequestException:
            st.error("Could not reach the Gmail API.")

    # -------------------------------------------------
    # Read-only inbox preview
    # -------------------------------------------------

    st.divider()
    st.subheader("Read-only inbox preview")

    st.write(
        "Preview sender and mailing-list information "
        "without reading email bodies."
    )

    if st.button("Preview inbox"):
        try:
            token = st.user.tokens.access

            if not isinstance(token, str) or not token:
                st.warning("No Google access token is available.")

            else:
                # First get up to 10 message IDs from the inbox.
                response = requests.get(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                    headers={
                        "Authorization": f"Bearer {token}",
                    },
                    params={
                        "maxResults": 10,
                        "labelIds": "INBOX",
                    },
                    timeout=10,
                )

                if response.status_code == 200:
                    messages = response.json().get("messages", [])

                    st.success(
                        f"Found {len(messages)} message(s) in this preview."
                    )

                    # Retrieve metadata only for each message.
                    for message in messages:
                        message_id = message.get("id")

                        if not message_id:
                            continue

                        metadata_response = requests.get(
                            (
                                "https://gmail.googleapis.com/gmail/v1/"
                                f"users/me/messages/{message_id}"
                            ),
                            headers={
                                "Authorization": f"Bearer {token}",
                            },
                            params=[
                                ("format", "metadata"),
                                ("metadataHeaders", "From"),
                                ("metadataHeaders", "Subject"),
                                ("metadataHeaders", "List-Unsubscribe"),
                                (
                                    "metadataHeaders",
                                    "List-Unsubscribe-Post",
                                ),
                            ],
                            timeout=10,
                        )

                        if metadata_response.status_code != 200:
                            st.warning(
                                "One message's metadata could not be retrieved."
                            )
                            continue

                        message_data = metadata_response.json()

                        headers = (
                            message_data
                            .get("payload", {})
                            .get("headers", [])
                        )

                        header_values = {
                            header.get("name", "").lower(): header.get(
                                "value", ""
                            )
                            for header in headers
                        }

                        sender = header_values.get(
                            "from",
                            "Unknown sender",
                        )

                        subject = header_values.get(
                            "subject",
                            "(No subject)",
                        )

                        has_unsubscribe = bool(
                            header_values.get("list-unsubscribe")
                        )

                        has_one_click = (
                            header_values.get(
                                "list-unsubscribe-post",
                                ""
                            ).lower()
                            == "list-unsubscribe=one-click"
                        )

                        st.markdown("---")
                        st.write(f"**From:** {sender}")
                        st.write(f"**Subject:** {subject}")

                        if has_one_click:
                            st.success(
                                "One-click unsubscribe supported."
                            )

                        elif has_unsubscribe:
                            st.info(
                                "Unsubscribe information detected."
                            )

                        else:
                            st.caption(
                                "No standard unsubscribe information detected."
                            )

                elif response.status_code == 401:
                    st.error(
                        "Your Google access token was rejected. "
                        "Try signing out and signing back in."
                    )

                elif response.status_code == 403:
                    st.error(
                        "Gmail denied permission to list messages."
                    )

                else:
                    st.error(
                        "Inbox preview failed. "
                        f"HTTP status: {response.status_code}"
                    )

        except (AttributeError, KeyError):
            st.error("Google access token is unavailable.")

        except (requests.RequestException, ValueError):
            st.error("Could not retrieve the inbox preview.")

    # -------------------------------------------------
    # Sign out
    # -------------------------------------------------

    if st.button("Sign out"):
        st.logout()

st.divider()

st.subheader("Gmail access")

st.info(
    "Inbox Cleaner currently uses read-only Gmail metadata access."
)

st.warning(
    "No emails will be deleted, modified or unsubscribed."
)
