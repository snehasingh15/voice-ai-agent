"""JWT & OAuth2 Authentication Module for Voice AI API.

Provides:
1. Secure JWT token issuance and signature verification (HMAC-SHA256).
2. Constant-time password verification against secure admin secrets.
3. FastAPI dependency injection (get_current_admin) to guard enterprise admin routes.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .config import ADMIN_PASSWORD, JWT_SECRET_KEY, ACCESS_TOKEN_EXPIRE_HOURS

security_bearer = HTTPBearer(auto_error=False)


def _b64_url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_url_decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding < 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def create_access_token(subject: str = "admin", role: str = "admin", expires_delta: Optional[timedelta] = None) -> str:
    """Create a cryptographically signed JWT access token."""
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    payload = {
        "sub": subject,
        "role": role,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(expire.timestamp()),
    }

    try:
        import jwt
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")
    except ImportError:
        # High-security standard HMAC-SHA256 fallback if pyjwt package is not yet compiled
        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = _b64_url_encode(json.dumps(header).encode("utf-8"))
        payload_b64 = _b64_url_encode(json.dumps(payload).encode("utf-8"))
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        signature = hmac.new(JWT_SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
        sig_b64 = _b64_url_encode(signature)
        return f"{header_b64}.{payload_b64}.{sig_b64}"


def verify_access_token(token: str) -> dict:
    """Validate a JWT token, verify signature, and ensure it has not expired."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        import jwt
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
        return payload
    except ImportError:
        # Standard HMAC-SHA256 verification fallback
        try:
            parts = token.split(".")
            if len(parts) != 3:
                raise ValueError("Invalid JWT format")
            header_b64, payload_b64, sig_b64 = parts
            signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
            expected_sig = hmac.new(JWT_SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
            actual_sig = _b64_url_decode(sig_b64)
            if not hmac.compare_digest(expected_sig, actual_sig):
                raise ValueError("Invalid signature")
            payload = json.loads(_b64_url_decode(payload_b64).decode("utf-8"))
            if payload.get("exp", 0) < int(datetime.now(timezone.utc).timestamp()):
                raise ValueError("Token expired")
            return payload
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token validation failed: {exc}",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def verify_password(plain_password: str) -> bool:
    """Verify password against configured ADMIN_PASSWORD using constant-time comparison."""
    if not ADMIN_PASSWORD or not plain_password:
        return False
    return hmac.compare_digest(plain_password.strip(), ADMIN_PASSWORD.strip())


async def get_current_admin(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)) -> dict:
    """FastAPI dependency to protect enterprise endpoints."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required (Bearer token)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    payload = verify_access_token(token)
    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for admin resource",
        )
    return payload
