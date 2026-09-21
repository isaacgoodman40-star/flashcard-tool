import streamlit as st
import requests
from collections import defaultdict

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
    # Mailing-list scan
    # -------------------------------------------------

    st.divider()
    st.subheader("Mailing-list scan")

    st.write(
        "Scan up to 50 inbox messages and group them by sender. "
        "Only selected Gmail metadata is requested."
    )

    if st.button("Scan inbox"):
        try:
            token = st.user.tokens.access

            if not isinstance(token, str) or not token:
                st.warning("No Google access token is available.")

            else:
                response = requests.get(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                    headers={
                        "Authorization": f"Bearer {token}",
                    },
                    params={
                        "maxResults": 50,
                        "labelIds": "INBOX",
                    },
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()

                    messages = data.get("messages", [])
                    next_page_token = data.get("nextPageToken")

                    st.success(
                        f"Scan returned {len(messages)} inbox message(s)."
                    )

                    if next_page_token:
                        st.info(
                            "More inbox messages are available. "
                            "This scan only processed the first page."
                        )
                    else:
                        st.caption(
                            "Gmail did not return another page for this scan."
                        )

                    senders = defaultdict(
                        lambda: {
                            "count": 0,
                            "unsubscribe": False,
                            "one_click": False,
                        }
                    )

                    failed_metadata_requests = 0

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
                                (
                                    "metadataHeaders",
                                    "List-Unsubscribe",
                                ),
                                (
                                    "metadataHeaders",
                                    "List-Unsubscribe-Post",
                                ),
                            ],
                            timeout=10,
                        )

                        if metadata_response.status_code != 200:
                            failed_metadata_requests += 1
                            continue

                        message_data = metadata_response.json()

                        headers = (
                            message_data
                            .get("payload", {})
                            .get("headers", [])
                        )

                        header_values = {
                            header.get("name", "").lower():
                            header.get("value", "")
                            for header in headers
                        }

                        sender = header_values.get(
                            "from",
                            "Unknown sender",
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

                        senders[sender]["count"] += 1

                        if has_unsubscribe:
                            senders[sender]["unsubscribe"] = True

                        if has_one_click:
                            senders[sender]["one_click"] = True

                    # Sort senders by number of messages.
                    sorted_senders = sorted(
                        senders.items(),
                        key=lambda item: item[1]["count"],
                        reverse=True,
                    )

                    st.subheader("Senders found")

                    if not sorted_senders:
                        st.info(
                            "No sender metadata was found in this scan."
                        )

                    for sender, details in sorted_senders:
                        st.markdown("---")

                        st.write(f"**{sender}**")

                        st.write(
                            f"{details['count']} email(s) "
                            "in this scan"
                        )

                        if details["one_click"]:
                            st.success(
                                "One-click unsubscribe supported."
                            )

                        elif details["unsubscribe"]:
                            st.info(
                                "Unsubscribe information detected."
                            )

                        else:
                            st.caption(
                                "No standard unsubscribe information "
                                "detected."
                            )

                    if failed_metadata_requests:
                        st.warning(
                            f"{failed_metadata_requests} message(s) "
                            "could not be inspected."
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
                        "Inbox scan failed. "
                        f"HTTP status: {response.status_code}"
                    )

        except (AttributeError, KeyError):
            st.error("Google access token is unavailable.")

        except (requests.RequestException, ValueError):
            st.error("Could not complete the inbox scan.")

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
