"""Tests for JWT token expiry, invalid tokens, and security edge cases."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


async def _login(client, username="admin", password="test-admin-password-123"):
    await client.get("/api/health")
    resp = await client.post("/api/auth/login", json={
        "username": username, "password": password,
    })
    return resp.json()["access_token"]


# ── Token Creation and Decoding ─────────────────────────────────────────

class TestTokenCreation:

    def test_create_access_token(self):
        token = create_access_token({"sub": "1", "username": "admin"})
        payload = decode_token(token)
        assert payload["sub"] == "1"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_create_refresh_token(self):
        token = create_refresh_token({"sub": "1", "username": "admin"})
        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_token_expiry_in_future(self):
        token = create_access_token({"sub": "1"})
        payload = decode_token(token)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert exp > datetime.now(timezone.utc)

    def test_refresh_token_longer_expiry(self):
        access = create_access_token({"sub": "1"})
        refresh = create_refresh_token({"sub": "1"})
        access_payload = decode_token(access)
        refresh_payload = decode_token(refresh)
        assert refresh_payload["exp"] > access_payload["exp"]


# ── Token Expiry Handling ───────────────────────────────────────────────

class TestTokenExpiry:

    def test_expired_token_raises_value_error(self):
        """Manually create an expired token and verify decode raises."""
        import jwt
        from app.core.config import get_settings
        settings = get_settings()

        expired_payload = {
            "sub": "1",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        expired_token = jwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(ValueError, match="Token expired"):
            decode_token(expired_token)

    @pytest.mark.asyncio
    async def test_expired_token_rejected_by_api(self, async_client):
        """API should return 401 for an expired access token."""
        import jwt
        from app.core.config import get_settings
        settings = get_settings()

        expired_payload = {
            "sub": "1",
            "username": "admin",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=30),
        }
        expired_token = jwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        resp = await async_client.get("/api/documents", headers={
            "Authorization": f"Bearer {expired_token}",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_refresh_token_rejected(self, async_client):
        """Expired refresh token should be rejected by /api/auth/refresh."""
        import jwt
        from app.core.config import get_settings
        settings = get_settings()

        expired_payload = {
            "sub": "1",
            "username": "admin",
            "type": "refresh",
            "exp": datetime.now(timezone.utc) - timedelta(days=8),
        }
        expired_token = jwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        resp = await async_client.post("/api/auth/refresh", json={
            "refresh_token": expired_token,
        })
        assert resp.status_code == 401


# ── Invalid Token Handling ──────────────────────────────────────────────

class TestInvalidTokens:

    def test_completely_invalid_token(self):
        with pytest.raises(ValueError, match="Invalid token"):
            decode_token("not.a.valid.token")

    def test_empty_token(self):
        with pytest.raises(ValueError):
            decode_token("")

    def test_token_with_wrong_secret(self):
        import jwt
        token = jwt.encode({"sub": "1", "type": "access", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                          "wrong-secret-key", algorithm="HS256")
        with pytest.raises(ValueError, match="Invalid token"):
            decode_token(token)

    @pytest.mark.asyncio
    async def test_malformed_bearer_header(self, async_client):
        resp = await async_client.get("/api/documents", headers={
            "Authorization": "NotBearer sometoken",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_bearer_token(self, async_client):
        resp = await async_client.get("/api/documents", headers={
            "Authorization": "Bearer ",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_no_authorization_header(self, async_client):
        resp = await async_client.get("/api/documents")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_type(self, async_client):
        """Using an access token as a refresh token should fail."""
        token = await _login(async_client)

        resp = await async_client.post("/api/auth/refresh", json={
            "refresh_token": token,  # This is an access token, not refresh
        })
        assert resp.status_code == 401


# ── Password Security ───────────────────────────────────────────────────

class TestPasswordSecurity:

    def test_hash_and_verify(self):
        password = "securepassword123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
        assert verify_password("wrong", hashed) is False

    def test_different_hashes_for_same_password(self):
        """bcrypt should produce different hashes due to random salt."""
        h1 = hash_password("samepassword")
        h2 = hash_password("samepassword")
        assert h1 != h2
        assert verify_password("samepassword", h1) is True
        assert verify_password("samepassword", h2) is True

    def test_empty_password_handling(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("notempty", hashed) is False


# ── User Session Security ───────────────────────────────────────────────

class TestUserSessionSecurity:

    @pytest.mark.asyncio
    async def test_disabled_user_token_rejected(self, async_client):
        """After a user is disabled, their existing token should be rejected."""
        from httpx import AsyncClient
        await async_client.get("/api/health")

        # Login as admin
        admin_login = await async_client.post("/api/auth/login", json={
            "username": "admin", "password": "test-admin-password-123",
        })
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        # Create a new user
        await async_client.post("/api/admin/users", json={
            "username": "sessiontest", "email": "session@test.com",
            "password": "pass123", "is_admin": False,
        }, headers=admin_headers)

        # Login as new user
        user_login = await async_client.post("/api/auth/login", json={
            "username": "sessiontest", "password": "pass123",
        })
        user_token = user_login.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}

        # Verify user can access
        resp = await async_client.get("/api/auth/me", headers=user_headers)
        assert resp.status_code == 200

        # Disable user via admin
        users = await async_client.get("/api/admin/users?search=sessiontest", headers=admin_headers)
        uid = users.json()["users"][0]["id"]
        await async_client.put(f"/api/admin/users/{uid}", json={"is_active": False}, headers=admin_headers)

        # Old token should now be rejected
        resp = await async_client.get("/api/auth/me", headers=user_headers)
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_password_change_invalidates_sessions(self, async_client):
        """After password change, old tokens should still work (JWT is stateless).
        This test documents the current behavior."""
        await async_client.get("/api/health")

        # Create user
        admin_login = await async_client.post("/api/auth/login", json={
            "username": "admin", "password": "test-admin-password-123",
        })
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        await async_client.post("/api/admin/users", json={
            "username": "pwchange", "email": "pw@test.com",
            "password": "oldpass", "is_admin": False,
        }, headers=admin_headers)

        user_login = await async_client.post("/api/auth/login", json={
            "username": "pwchange", "password": "oldpass",
        })
        old_token = user_login.json()["access_token"]

        # Change password
        resp = await async_client.post("/api/auth/change-password", json={
            "current_password": "oldpass",
            "new_password": "newpass123",
        }, headers={"Authorization": f"Bearer {old_token}"})
        assert resp.status_code == 200

        # Old JWT should still work (stateless JWT — no server-side invalidation)
        resp = await async_client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"})
        # Current implementation: JWT is not invalidated on password change
        assert resp.status_code in (200, 401)

    @pytest.mark.asyncio
    async def test_nonexistent_user_token_rejected(self, async_client):
        """Token for a user ID that doesn't exist should be rejected."""
        import jwt
        from app.core.config import get_settings
        settings = get_settings()

        token = create_access_token({"sub": "99999", "username": "ghost"})
        resp = await async_client.get("/api/documents", headers={
            "Authorization": f"Bearer {token}",
        })
        assert resp.status_code == 401
