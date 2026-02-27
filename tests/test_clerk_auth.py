"""Tests for Clerk-based authentication dependency.

All tests mock the Clerk SDK so no real API keys or network are needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api.auth.clerk_auth import get_current_user

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app() -> FastAPI:
    """Minimal FastAPI app with a protected route."""
    _app = FastAPI()

    @_app.get("/protected")
    async def protected(user: dict = Depends(get_current_user)):
        return {"user": user}

    @_app.get("/public")
    async def public():
        return {"status": "ok"}

    return _app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helper to build a mock RequestState
# ---------------------------------------------------------------------------


def _mock_request_state(
    *, is_signed_in: bool, payload: dict | None = None
) -> MagicMock:
    state = MagicMock()
    state.is_signed_in = is_signed_in
    state.payload = payload or {}
    return state


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetCurrentUser:
    """Unit tests for the get_current_user FastAPI dependency."""

    @patch.dict("os.environ", {"CLERK_SECRET_KEY": ""}, clear=False)
    def test_missing_secret_key_returns_500(
        self, client: TestClient
    ) -> None:
        """If CLERK_SECRET_KEY is empty, return 500."""
        resp = client.get(
            "/protected",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert resp.status_code == 500
        assert "CLERK_SECRET_KEY" in resp.json()["detail"]

    @patch.dict(
        "os.environ", {"CLERK_SECRET_KEY": "sk_test_xxx"}, clear=False
    )
    @patch("src.api.auth.clerk_auth.Clerk")
    def test_no_auth_header_returns_401(
        self, mock_clerk_cls: MagicMock, client: TestClient
    ) -> None:
        """Request without Authorization header should be rejected."""
        mock_instance = mock_clerk_cls.return_value
        mock_instance.authenticate_request.return_value = (
            _mock_request_state(is_signed_in=False)
        )

        resp = client.get("/protected")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Unauthorized"

    @patch.dict(
        "os.environ", {"CLERK_SECRET_KEY": "sk_test_xxx"}, clear=False
    )
    @patch("src.api.auth.clerk_auth.Clerk")
    def test_invalid_token_returns_401(
        self, mock_clerk_cls: MagicMock, client: TestClient
    ) -> None:
        """Request with an invalid/expired token should be rejected."""
        mock_instance = mock_clerk_cls.return_value
        mock_instance.authenticate_request.return_value = (
            _mock_request_state(is_signed_in=False)
        )

        resp = client.get(
            "/protected",
            headers={"Authorization": "Bearer bad-token"},
        )
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers

    @patch.dict(
        "os.environ", {"CLERK_SECRET_KEY": "sk_test_xxx"}, clear=False
    )
    @patch("src.api.auth.clerk_auth.Clerk")
    def test_valid_token_returns_payload(
        self, mock_clerk_cls: MagicMock, client: TestClient
    ) -> None:
        """Valid session token should return the JWT payload."""
        expected_payload = {
            "sub": "user_abc123",
            "email": "test@zsxq.com",
        }
        mock_instance = mock_clerk_cls.return_value
        mock_instance.authenticate_request.return_value = (
            _mock_request_state(
                is_signed_in=True, payload=expected_payload
            )
        )

        resp = client.get(
            "/protected",
            headers={"Authorization": "Bearer valid-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["user"] == expected_payload

    @patch.dict(
        "os.environ", {"CLERK_SECRET_KEY": "sk_test_xxx"}, clear=False
    )
    @patch("src.api.auth.clerk_auth.Clerk")
    def test_authenticate_request_is_called(
        self, mock_clerk_cls: MagicMock, client: TestClient
    ) -> None:
        """Verify that authenticate_request is invoked."""
        mock_instance = mock_clerk_cls.return_value
        mock_instance.authenticate_request.return_value = (
            _mock_request_state(
                is_signed_in=True, payload={"sub": "user_1"}
            )
        )

        client.get(
            "/protected",
            headers={"Authorization": "Bearer tok"},
        )

        mock_instance.authenticate_request.assert_called_once()

    def test_public_route_no_auth_needed(
        self, client: TestClient
    ) -> None:
        """Public endpoints should work without any auth."""
        resp = client.get("/public")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestAuthorizedParties:
    """Tests for _get_authorized_parties helper."""

    @patch.dict(
        "os.environ", {"CLERK_AUTHORIZED_PARTIES": ""}, clear=False
    )
    def test_default_parties(self) -> None:
        from src.api.auth.clerk_auth import _get_authorized_parties

        parties = _get_authorized_parties()
        assert parties == [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
        ]

    @patch.dict(
        "os.environ",
        {
            "CLERK_AUTHORIZED_PARTIES": (
                "https://app.example.com, https://staging.example.com"
            )
        },
        clear=False,
    )
    def test_custom_parties(self) -> None:
        from src.api.auth.clerk_auth import _get_authorized_parties

        parties = _get_authorized_parties()
        assert parties == [
            "https://app.example.com",
            "https://staging.example.com",
        ]

    @patch.dict(
        "os.environ",
        {"CLERK_AUTHORIZED_PARTIES": "  ,  , "},
        clear=False,
    )
    def test_empty_entries_filtered(self) -> None:
        from src.api.auth.clerk_auth import _get_authorized_parties

        parties = _get_authorized_parties()
        assert parties == [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
        ]
