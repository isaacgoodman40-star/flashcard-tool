import re
from collections import defaultdict
from urllib.parse import urlparse

import requests
import streamlit as st


# -------------------------------------------------
# Page configuration
# -------------------------------------------------

st.set_page_config(
    page_title="Inbox Cleaner",
)


# -------------------------------------------------
# Helper functions
# -------------------------------------------------

def extract_https_unsubscribe_urls(header_value):
    """
    Extract HTTPS URLs from a List-Unsubscribe header.

    Example header:
    <https://example.com/unsubscribe>, <mailto:unsubscribe@example.com>
    """

    if not header_value:
        return []

    candidates = re.findall(r"<([^>]+)>", header_value)

    https_urls = []

    for candidate in candidates:
        candidate = candidate.strip()

        try:
            parsed = urlparse(candidate)

            if (
                parsed.scheme.lower() == "https"
                and parsed.netloc
            ):
                https_urls.append(candidate)

        except ValueError:
            continue

    return https_urls


# -------------------------------------------------
# Session state
# -------------------------------------------------

if "scan_results" not in st.session_state:
    st.session_state.scan_results = []

if "scan_message_count" not in st.session_state:
    st.session_state.scan_message_count = 0

if "more_messages_available" not in st.session_state:
    st.session_state.more_messages_available = False


# -------------------------------------------------
# Page header
# -------------------------------------------------

st.title("Inbox Cleaner")
st.write("A privacy-first way to clean your inbox.")
st.success("The application is running.")

st.divider()

st.subheader("Connect your mailbox")

st.write(
    "Connect your email account securely using your provider's sign-in page."
)


# -------------------------------------------------
# Google sign-in
# -------------------------------------------------

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

                st.warning(
                    "No Google access token is available."
                )

            else:

                response = requests.get(
                    "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                    headers={
                        "Authorization": f"Bearer {token}",
                    },
                    timeout=10,
                )

                if response.status_code == 200:

                    st.success(
                        "Gmail API connection successful!"
                    )

                elif response.status_code == 401:

                    st.error(
                        "Google rejected the access token. "
                        "Try signing out and signing back in."
                    )

                elif response.status_code == 403:

                    st.error(
                        "Gmail access was denied."
                    )

                else:

                    st.error(
                        "Gmail connection failed. "
                        f"HTTP status: {response.status_code}"
                    )

        except (AttributeError, KeyError):

            st.error(
                "Google access token is unavailable."
            )

        except requests.RequestException:

            st.error(
                "Could not reach the Gmail API."
            )

    # -------------------------------------------------
    # Mailing-list scan
    # -------------------------------------------------

    st.divider()

    st.subheader("Mailing-list scan")

    st.write(
        "Scan your inbox and group messages by sender. "
        "Only selected Gmail metadata is requested."
    )

    scan_limit = st.selectbox(
        "How many emails would you like to scan?",
        options=[10, 25, 50, 100],
        index=2,
    )

    if st.button("Scan inbox"):

        try:

            token = st.user.tokens.access

            if not isinstance(token, str) or not token:

                st.warning(
                    "No Google access token is available."
                )

            else:

                response = requests.get(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                    headers={
                        "Authorization": f"Bearer {token}",
                    },
                    params={
                        "maxResults": scan_limit,
                        "labelIds": "INBOX",
                    },
                    timeout=10,
                )

                if response.status_code == 200:

                    data = response.json()

                    messages = data.get(
                        "messages",
                        [],
                    )

                    next_page_token = data.get(
                        "nextPageToken"
                    )

                    # -------------------------------------------------
                    # Temporary sender data
                    # -------------------------------------------------

                    senders = defaultdict(
                        lambda: {
                            "count": 0,
                            "unsubscribe": False,
                            "one_click_header": False,
                            "unsubscribe_url": None,
                            "one_click_eligible": False,
                        }
                    )

                    failed_metadata_requests = 0

                    # -------------------------------------------------
                    # Inspect message metadata
                    # -------------------------------------------------

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
                                (
                                    "format",
                                    "metadata",
                                ),
                                (
                                    "metadataHeaders",
                                    "From",
                                ),
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
                            header.get(
                                "name",
                                "",
                            ).lower():
                            header.get(
                                "value",
                                "",
                            )
                            for header in headers
                        }

                        sender = header_values.get(
                            "from",
                            "Unknown sender",
                        )

                        unsubscribe_header = (
                            header_values.get(
                                "list-unsubscribe",
                                "",
                            )
                        )

                        unsubscribe_post_header = (
                            header_values.get(
                                "list-unsubscribe-post",
                                "",
                            )
                        )

                        has_unsubscribe = bool(
                            unsubscribe_header
                        )

                        has_one_click_header = (
                            unsubscribe_post_header
                            .strip()
                            .lower()
                            == "list-unsubscribe=one-click"
                        )

                        https_urls = (
                            extract_https_unsubscribe_urls(
                                unsubscribe_header
                            )
                        )

                        unsubscribe_url = None

                        if https_urls:
                            unsubscribe_url = https_urls[0]

                        one_click_eligible = (
                            has_one_click_header
                            and unsubscribe_url is not None
                        )

                        # -------------------------------------------------
                        # Update sender information
                        # -------------------------------------------------

                        senders[sender]["count"] += 1

                        if has_unsubscribe:

                            senders[sender][
                                "unsubscribe"
                            ] = True

                        if has_one_click_header:

                            senders[sender][
                                "one_click_header"
                            ] = True

                        if (
                            unsubscribe_url
                            and senders[sender][
                                "unsubscribe_url"
                            ] is None
                        ):

                            senders[sender][
                                "unsubscribe_url"
                            ] = unsubscribe_url

                        if one_click_eligible:

                            senders[sender][
                                "one_click_eligible"
                            ] = True

                            senders[sender][
                                "unsubscribe_url"
                            ] = unsubscribe_url

                    # -------------------------------------------------
                    # Sort sender results
                    # -------------------------------------------------

                    sorted_senders = sorted(
                        senders.items(),
                        key=lambda item: item[1]["count"],
                        reverse=True,
                    )

                    # -------------------------------------------------
                    # Save temporary results
                    # -------------------------------------------------

                    st.session_state.scan_results = [
                        {
                            "sender": sender,
                            "count": details["count"],
                            "unsubscribe": (
                                details["unsubscribe"]
                            ),
                            "one_click_header": (
                                details["one_click_header"]
                            ),
                            "unsubscribe_url": (
                                details["unsubscribe_url"]
                            ),
                            "one_click_eligible": (
                                details["one_click_eligible"]
                            ),
                        }
                        for sender, details
                        in sorted_senders
                    ]

                    st.session_state.scan_message_count = (
                        len(messages)
                    )

                    st.session_state.more_messages_available = (
                        bool(next_page_token)
                    )

                    # -------------------------------------------------
                    # Clear previous selections
                    # -------------------------------------------------

                    keys_to_remove = [
                        key
                        for key
                        in st.session_state.keys()
                        if key.startswith(
                            "sender_select_"
                        )
                    ]

                    for key in keys_to_remove:
                        del st.session_state[key]

                    st.success(
                        f"Scan returned "
                        f"{len(messages)} inbox message(s)."
                    )

                    if failed_metadata_requests:

                        st.warning(
                            f"{failed_metadata_requests} "
                            "message(s) could not be inspected."
                        )

                elif response.status_code == 401:

                    st.error(
                        "Your Google access token was rejected. "
                        "Try signing out and signing back in."
                    )

                elif response.status_code == 403:

                    st.error(
                        "Gmail denied permission "
                        "to list messages."
                    )

                else:

                    st.error(
                        "Inbox scan failed. "
                        f"HTTP status: {response.status_code}"
                    )

        except (AttributeError, KeyError):

            st.error(
                "Google access token is unavailable."
            )

        except (
            requests.RequestException,
            ValueError,
        ):

            st.error(
                "Could not complete the inbox scan."
            )

    # -------------------------------------------------
    # Persistent scan results
    # -------------------------------------------------

    if st.session_state.scan_results:

        st.divider()

        st.subheader("Senders found")

        st.write(
            f"{st.session_state.scan_message_count} "
            "email(s) were included in the latest scan."
        )

        if st.session_state.more_messages_available:

            st.info(
                "More inbox messages are available "
                "beyond this scan."
            )

        selected_senders = []

        # -------------------------------------------------
        # Sender selection
        # -------------------------------------------------

        for index, result in enumerate(
            st.session_state.scan_results
        ):

            sender = result["sender"]

            st.markdown("---")

            selected = st.checkbox(
                sender,
                key=f"sender_select_{index}",
            )

            st.write(
                f"{result['count']} email(s) "
                "in this scan"
            )

            if result["one_click_eligible"]:

                st.success(
                    "One-click unsubscribe candidate."
                )

            elif result["unsubscribe"]:

                st.info(
                    "Manual unsubscribe information detected."
                )

            else:

                st.caption(
                    "No standard unsubscribe information detected."
                )

            if selected:
                selected_senders.append(result)

        # -------------------------------------------------
        # Selection summary
        # -------------------------------------------------

        st.divider()

        if selected_senders:

            total_selected_emails = sum(
                sender["count"]
                for sender
                in selected_senders
            )

            st.write(
                f"**{len(selected_senders)} "
                "sender(s) selected**"
            )

            st.write(
                "These senders represent "
                f"**{total_selected_emails} email(s)** "
                "in this scan."
            )

        # -------------------------------------------------
        # Review selected senders
        # -------------------------------------------------

        if st.button(
            "Review selected",
            disabled=not selected_senders,
        ):

            st.subheader(
                "Review selected senders"
            )

            total_selected_emails = 0

            one_click_count = 0
            manual_count = 0
            unavailable_count = 0

            for result in selected_senders:

                st.markdown("---")

                st.write(
                    f"**{result['sender']}**"
                )

                st.write(
                    f"{result['count']} email(s)"
                )

                total_selected_emails += (
                    result["count"]
                )

                if result["one_click_eligible"]:

                    one_click_count += 1

                    st.success(
                        "Eligible for further "
                        "one-click unsubscribe review."
                    )

                elif result["unsubscribe"]:

                    manual_count += 1

                    st.info(
                        "Unsubscribe information exists, "
                        "but this sender is not currently "
                        "eligible for automated one-click."
                    )

                else:

                    unavailable_count += 1

                    st.caption(
                        "No standard unsubscribe method "
                        "was detected."
                    )

            # -------------------------------------------------
            # Review summary
            # -------------------------------------------------

            st.divider()

            st.subheader("Review summary")

            st.write(
                f"Selected senders: "
                f"**{len(selected_senders)}**"
            )

            st.write(
                f"Emails represented: "
                f"**{total_selected_emails}**"
            )

            st.write(
                f"One-click candidates: "
                f"**{one_click_count}**"
            )

            st.write(
                f"Manual unsubscribe only: "
                f"**{manual_count}**"
            )

            st.write(
                f"No standard unsubscribe method: "
                f"**{unavailable_count}**"
            )

            st.warning(
                "Review only — Inbox Cleaner has not "
                "visited any unsubscribe links, sent any "
                "unsubscribe requests, deleted any emails, "
                "or modified your Gmail account."
            )

    # -------------------------------------------------
    # Sign out
    # -------------------------------------------------

    st.divider()

    if st.button("Sign out"):

        st.session_state.scan_results = []
        st.session_state.scan_message_count = 0
        st.session_state.more_messages_available = False

        st.logout()


# -------------------------------------------------
# Gmail access information
# -------------------------------------------------

st.divider()

st.subheader("Gmail access")

st.info(
    "Inbox Cleaner currently uses "
    "read-only Gmail metadata access."
)

st.warning(
    "No emails will be deleted, modified or unsubscribed."
)
