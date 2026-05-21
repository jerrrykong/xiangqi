"""Game Service v2.0 - JWT Manager

JWT token generation, parsing, and refresh.
Compatible with existing Go-side JWT format (HS256 algorithm).
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import jwt

logger = logging.getLogger(__name__)


@dataclass
class TokenClaims:
    """JWT token claims."""
    user_id: int
    username: str
    is_admin: bool
    exp: int = 0
    iat: int = 0
    type: str = "access"  # access / refresh


class JWTManager:
    """Manages JWT token creation, parsing, and refresh."""

    def __init__(self, secret: str, expire_hours: int = 168,
                 refresh_expire_hours: int = 720, algorithm: str = "HS256"):
        self._secret = secret
        self._expire_hours = expire_hours
        self._refresh_expire_hours = refresh_expire_hours
        self._algorithm = algorithm

    def create_token(self, user_id: int, username: str,
                     is_admin: bool = False) -> tuple[str, int]:
        """Create an access JWT token.

        Returns:
            (token_string, expires_at_timestamp)
        """
        now = int(time.time())
        expires_at = now + self._expire_hours * 3600

        payload = {
            "user_id": user_id,
            "username": username,
            "is_admin": is_admin,
            "exp": expires_at,
            "iat": now,
            "type": "access",
        }

        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return token, expires_at

    def create_refresh_token(self, user_id: int, username: str,
                             is_admin: bool = False) -> tuple[str, int]:
        """Create a refresh JWT token.

        Returns:
            (token_string, expires_at_timestamp)
        """
        now = int(time.time())
        expires_at = now + self._refresh_expire_hours * 3600

        payload = {
            "user_id": user_id,
            "username": username,
            "is_admin": is_admin,
            "exp": expires_at,
            "iat": now,
            "type": "refresh",
        }

        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return token, expires_at

    def parse_token(self, token: str) -> Optional[TokenClaims]:
        """Parse and validate a JWT token.

        Returns TokenClaims if valid, None if invalid/expired.
        """
        try:
            payload = jwt.decode(
                token, self._secret, algorithms=[self._algorithm],
            )
            return TokenClaims(
                user_id=payload.get("user_id", 0),
                username=payload.get("username", ""),
                is_admin=payload.get("is_admin", False),
                exp=payload.get("exp", 0),
                iat=payload.get("iat", 0),
                type=payload.get("type", "access"),
            )
        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug(f"Invalid token: {e}")
            return None

    def refresh_token(self, refresh_token_str: str) -> Optional[tuple[str, int]]:
        """Validate a refresh token and create a new access token.

        Returns (new_access_token, expires_at) or None if refresh token is invalid.
        """
        claims = self.parse_token(refresh_token_str)
        if claims is None:
            return None
        if claims.type != "refresh":
            return None

        return self.create_token(claims.user_id, claims.username, claims.is_admin)
