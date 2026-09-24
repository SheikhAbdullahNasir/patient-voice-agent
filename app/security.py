"""Checks that requests to /vapi/* really come from Vapi (shared-secret check)."""
import hmac

from fastapi import Header, HTTPException

from app.config import settings


def verify_vapi_secret(
    authorization: str | None = Header(default=None),
    x_vapi_secret: str | None = Header(default=None),
) -> None:
    expected = settings.vapi_secret
    if not expected:
        return  # auth disabled (local development only)

    supplied = None
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()  # Vapi Bearer-token credential
    elif x_vapi_secret:
        supplied = x_vapi_secret.strip()  # legacy header

    # compare_digest avoids leaking information through timing differences
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")