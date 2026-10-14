"""Authentication, JWT, password, and role tests without a real database."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, create_autospec

import pytest
import jwt
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from auth.dependencies import get_auth_service, get_current_user, require_admin, require_user
from auth.exceptions import AuthenticationException, AuthorizationException
from auth.jwt import create_access_token, decode_access_token
from auth.password import hash_password, verify_password
from config.settings import Settings
from main import app
from repositories.user_repository import UserRepository
from routers.dependencies import get_drama_service
from services.auth_service import AuthService

TEST_SECRET = "test-auth-secret-key-with-at-least-32-characters"


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        secret_key=TEST_SECRET,
        token_expire_minutes=30,
    )


def _user(
    *,
    role: str = "USER",
    status: str = "ACTIVE",
    password_hash: str | None = None,
) -> SimpleNamespace:
    now = datetime.now(UTC).replace(tzinfo=None)
    return SimpleNamespace(
        user_id=1,
        username="analyst",
        password_hash=password_hash or hash_password("correct-password"),
        display_name="Analyst",
        role_code=role,
        status=status,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )


def _request(
    method: str,
    path: str,
    **kwargs: Any,
) -> tuple[int, Any, dict[str, str]]:
    async def perform() -> tuple[int, Any, dict[str, str]]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.request(method, path, **kwargs)
            return response.status_code, response.json(), dict(response.headers)

    return asyncio.run(perform())


def test_password_hash_and_verify() -> None:
    password_hash = hash_password("correct-password")

    assert password_hash != "correct-password"
    assert password_hash.startswith("$2")
    assert verify_password("correct-password", password_hash) is True
    assert verify_password("wrong-password", password_hash) is False
    assert verify_password("x" * 73, password_hash) is False


def test_jwt_generation_and_strict_parsing() -> None:
    token = create_access_token(
        user_id=7,
        username="admin",
        role="ADMINISTRATOR",
        secret_key=TEST_SECRET,
        expires_minutes=30,
    )
    claims = decode_access_token(token, secret_key=TEST_SECRET)

    assert claims.sub == "7"
    assert claims.user_id == 7
    assert claims.username == "admin"
    assert claims.role == "ADMINISTRATOR"
    assert "password" not in token.lower()
    with pytest.raises(AuthenticationException):
        decode_access_token(token, secret_key=f"{TEST_SECRET}-wrong")


def test_expired_jwt_is_rejected() -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "1",
            "user_id": 1,
            "username": "analyst",
            "role": "USER",
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
        },
        TEST_SECRET,
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationException):
        decode_access_token(token, secret_key=TEST_SECRET)


def test_settings_require_environment_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)

    settings = _settings()
    assert settings.secret_key.get_secret_value() == TEST_SECRET
    assert TEST_SECRET not in repr(settings.secret_key)


def test_legacy_revision_settings_require_one_complete_bundle() -> None:
    with pytest.raises(ValidationError, match="all Data Quality legacy"):
        Settings(
            _env_file=None,
            secret_key=TEST_SECRET,
            data_quality_legacy_revision_database="isolated",
        )


def test_legacy_revision_settings_reject_aware_fingerprint_timestamps() -> None:
    with pytest.raises(ValidationError, match="must be naive"):
        Settings(
            _env_file=None,
            secret_key=TEST_SECRET,
            data_quality_legacy_revision_database="isolated",
            data_quality_legacy_revision_max_id=10,
            data_quality_legacy_revision_expected_count=10,
            data_quality_legacy_revision_expected_min_changed_at=datetime(
                2026, 9, 1, tzinfo=UTC
            ),
            data_quality_legacy_revision_expected_max_changed_at=datetime(
                2026, 9, 2, tzinfo=UTC
            ),
        )


def test_active_user_login_returns_valid_token() -> None:
    session = create_autospec(Session, instance=True)
    users = UserRepository(session)
    active_user = _user()
    users.get_by_username = MagicMock(return_value=active_user)
    service = AuthService(session, users, _settings())

    token, expires_in_seconds = service.login("analyst", "correct-password")
    claims = decode_access_token(token, secret_key=TEST_SECRET)

    assert expires_in_seconds == 1800
    assert claims.user_id == active_user.user_id
    assert claims.role == "USER"


@pytest.mark.parametrize("user_status", ["INACTIVE", "MISSING"])
def test_inactive_or_unknown_user_login_is_rejected(user_status: str) -> None:
    session = create_autospec(Session, instance=True)
    users = UserRepository(session)
    result = None if user_status == "MISSING" else _user(status="INACTIVE")
    users.get_by_username = MagicMock(return_value=result)
    service = AuthService(session, users, _settings())

    with pytest.raises(AuthenticationException) as raised:
        service.login("analyst", "correct-password")

    assert raised.value.message == "Authentication failed"


def test_current_user_resolution_reloads_active_database_identity() -> None:
    session = create_autospec(Session, instance=True)
    users = UserRepository(session)
    current = _user(role="ADMINISTRATOR")
    users.get_by_id = MagicMock(return_value=current)
    service = AuthService(session, users, _settings())
    token = create_access_token(
        user_id=current.user_id,
        username=current.username,
        role="USER",
        secret_key=TEST_SECRET,
        expires_minutes=30,
    )

    resolved = service.resolve_current_user(token)

    assert resolved is current
    assert resolved.role_code == "ADMINISTRATOR"


def test_token_is_rejected_after_user_becomes_inactive() -> None:
    session = create_autospec(Session, instance=True)
    users = UserRepository(session)
    inactive = _user(status="INACTIVE")
    users.get_by_id = MagicMock(return_value=inactive)
    service = AuthService(session, users, _settings())
    token = create_access_token(
        user_id=inactive.user_id,
        username=inactive.username,
        role=inactive.role_code,
        secret_key=TEST_SECRET,
        expires_minutes=30,
    )

    with pytest.raises(AuthenticationException):
        service.resolve_current_user(token)


def test_role_dependencies_enforce_admin_and_user_permissions() -> None:
    administrator = _user(role="ADMINISTRATOR")
    user = _user(role="USER")

    assert require_user(administrator) is administrator
    assert require_user(user) is user
    assert require_admin(administrator) is administrator
    with pytest.raises(AuthorizationException):
        require_admin(user)


def test_protected_routes_reject_missing_token_with_safe_401() -> None:
    status_code, body, headers = _request("GET", "/api/v1/dramas")

    assert status_code == 401
    assert body == {
        "code": "AUTHENTICATION_FAILED",
        "message": "Authentication failed",
        "details": None,
    }
    assert headers["www-authenticate"] == "Bearer"


def test_openapi_uses_http_bearer_and_has_no_registration() -> None:
    schema = app.openapi()
    security_scheme = schema["components"]["securitySchemes"]["JWTBearer"]

    assert security_scheme["type"] == "http"
    assert security_scheme["scheme"] == "bearer"
    assert schema["paths"]["/api/v1/auth/login"]["post"].get("security") is None
    assert schema["paths"]["/api/v1/dramas"]["get"]["security"] == [
        {"JWTBearer": []}
    ]
    assert not any("register" in path for path in schema["paths"])


def test_user_role_can_read_but_cannot_write() -> None:
    class FakeDramaService:
        def list_dramas(self, **filters: Any) -> SimpleNamespace:
            return SimpleNamespace(
                page=filters["page"],
                page_size=filters["page_size"],
                total=0,
                items=[],
            )

    app.dependency_overrides[get_current_user] = lambda: _user(role="USER")
    app.dependency_overrides[get_drama_service] = FakeDramaService
    try:
        read_status, _, _ = _request("GET", "/api/v1/dramas")
        write_status, write_body, _ = _request(
            "POST",
            "/api/v1/dramas",
            json={"drama_name": "Forbidden Write"},
        )
        users_status, _, _ = _request("GET", "/api/v1/users")
    finally:
        app.dependency_overrides.clear()

    assert read_status == 200
    assert write_status == 403
    assert write_body["code"] == "FORBIDDEN"
    assert users_status == 403


def test_login_and_current_user_responses_never_expose_password_hash() -> None:
    class FakeAuthService:
        def login(self, username: str, password: str) -> tuple[str, int]:
            assert username == "analyst"
            assert password == "correct-password"
            return "signed-token", 1800

    app.dependency_overrides[get_auth_service] = FakeAuthService
    try:
        login_status, login_body, _ = _request(
            "POST",
            "/api/v1/auth/login",
            json={"username": "analyst", "password": "correct-password"},
        )
    finally:
        app.dependency_overrides.clear()

    app.dependency_overrides[get_current_user] = lambda: _user()
    try:
        me_status, me_body, _ = _request("GET", "/api/v1/auth/me")
    finally:
        app.dependency_overrides.clear()

    assert login_status == 200
    assert login_body["data"] == {
        "access_token": "signed-token",
        "token_type": "bearer",
        "expires_in_seconds": 1800,
    }
    assert me_status == 200
    assert "password_hash" not in me_body["data"]
    assert "correct-password" not in str(login_body)
