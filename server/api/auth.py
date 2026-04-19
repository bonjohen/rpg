"""Telegram WebApp initData validation via HMAC-SHA256."""

from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import parse_qs, unquote

from server.api.responses import AuthResult


def validate_init_data(init_data: str, bot_token: str) -> AuthResult:
    """Validate Telegram WebApp initData and extract user info.

    The initData string is a URL-encoded set of key=value pairs.
    The ``hash`` parameter is an HMAC-SHA256 of the remaining fields
    sorted alphabetically and newline-joined, keyed with a secret
    derived from the bot token.

    Returns an AuthResult with ``valid=True`` and user fields populated
    on success, or ``valid=False`` with an error message on failure.
    """
    if not init_data or not bot_token:
        return AuthResult(valid=False, error="Missing initData or bot token.")

    try:
        parsed = parse_qs(init_data, keep_blank_values=True)
    except Exception:
        return AuthResult(valid=False, error="Malformed initData.")

    received_hash = parsed.pop("hash", [None])[0]  # type: ignore[arg-type]
    if not received_hash:
        return AuthResult(valid=False, error="Missing hash in initData.")

    # Build the data-check string: sorted key=value pairs joined by \n
    data_check_parts = []
    for key in sorted(parsed.keys()):
        # parse_qs returns lists; take the first value
        val = parsed[key][0] if parsed[key] else ""
        data_check_parts.append(f"{key}={val}")
    data_check_string = "\n".join(data_check_parts)

    # Derive secret key: HMAC-SHA256 of bot_token with key "WebAppData"
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256
    ).digest()

    # Compute expected hash
    expected_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        return AuthResult(valid=False, error="Invalid hash.")

    # Extract user info
    user_json = parsed.get("user", [""])[0]
    if not user_json:
        return AuthResult(valid=False, error="No user data in initData.")

    try:
        user_data = json.loads(unquote(user_json))
    except (json.JSONDecodeError, TypeError):
        return AuthResult(valid=False, error="Invalid user JSON.")

    user_id = str(user_data.get("id", ""))
    first_name = user_data.get("first_name", "")
    last_name = user_data.get("last_name", "")
    display_name = f"{first_name} {last_name}".strip() or user_id

    return AuthResult(
        valid=True,
        player_id=user_id,
        display_name=display_name,
    )
