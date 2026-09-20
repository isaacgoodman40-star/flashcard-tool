import secrets
import time
from urllib.parse import urlencode
from itsdangerous import URLSafeTimedSerializer

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.metadata"
STATE_MAX_AGE = 600


def create_oauth_state(secret_key):
    serializer = URLSafeTimedSerializer(secret_key)

    random_value = secrets.token_urlsafe(32)

    return serializer.dumps(random_value)


def verify_oauth_state(state, secret_key):
    serializer = URLSafeTimedSerializer(secret_key)

    return serializer.loads(
        state,
        max_age=STATE_MAX_AGE,
    )
