"""Checking that a webhook delivery really comes from Eleza.

Every delivery is signed: HMAC-SHA256 over ``"<timestamp>.<delivery id>.<raw body>"``
with the webhook secret. The timestamp is part of what is signed, so an old
delivery cannot be replayed.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Mapping, Optional, Union

from .errors import ElezaError, WebhookError
from .update import Update

HEADER_SIGNATURE = "X-Eleza-Signature"
HEADER_TIMESTAMP = "X-Eleza-Timestamp"
#: The update id; the same on every retry of a delivery.
HEADER_DELIVERY_ID = "X-Eleza-Delivery-Id"
HEADER_ATTEMPT = "X-Eleza-Delivery-Attempt"
HEADER_BOT_ID = "X-Eleza-Bot-Id"

#: Deliveries older (or newer) than this many seconds are refused.
DEFAULT_TOLERANCE = 300


def _bytes(value: Union[str, bytes]) -> bytes:
    return value.encode("utf-8") if isinstance(value, str) else bytes(value)


def sign(secret: Union[str, bytes], timestamp: Union[int, str], delivery_id: str, raw_body: Union[str, bytes]) -> str:
    message = f"{timestamp}.{delivery_id}.".encode("utf-8") + _bytes(raw_body)
    return "v1=" + hmac.new(_bytes(secret), message, hashlib.sha256).hexdigest()


def verify(
    secret: Union[str, bytes],
    signature: str,
    timestamp: str,
    delivery_id: str,
    raw_body: Union[str, bytes],
    tolerance: int = DEFAULT_TOLERANCE,
    now: Optional[float] = None,
) -> bool:
    """``raw_body`` is the request body exactly as received (not re-encoded)."""
    timestamp = str(timestamp or "")
    if not secret or not signature or not delivery_id or not (timestamp.isascii() and timestamp.isdigit()):
        return False
    if abs((time.time() if now is None else now) - int(timestamp)) > tolerance:
        return False
    return hmac.compare_digest(sign(secret, timestamp, delivery_id, raw_body).encode(), str(signature).encode())


def parse(secret: Union[str, bytes], raw_body: Union[str, bytes], headers: Mapping[str, Any], tolerance: int = DEFAULT_TOLERANCE) -> Update:
    """Verifies a delivery and returns its update.

    ``headers`` are the request headers, in any letter case (the header
    objects of Flask, Django, FastAPI and the like work as they are).

    Raises :class:`WebhookError` when the delivery is not authentic or not an update.
    """
    h = {}
    for name, value in headers.items():
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        h[str(name).lower()] = str(value)
    delivery_id = h.get(HEADER_DELIVERY_ID.lower(), "")
    if not verify(secret, h.get(HEADER_SIGNATURE.lower(), ""), h.get(HEADER_TIMESTAMP.lower(), ""), delivery_id, raw_body, tolerance):
        raise WebhookError("The webhook signature is missing, wrong or too old")
    try:
        update = Update.from_json(raw_body)
    except ElezaError as e:
        raise WebhookError("The webhook body is not an update") from e
    if str(update.id) != delivery_id:
        raise WebhookError("The delivery id does not match the update")
    return update
