import pytest
from datetime import datetime, timedelta
from fastapi import Request, HTTPException

from app.models.db import AuthToken, UserRole
from app.routes.auth import get_current_user, require_role


def test_verify_token_success(client, db_session, test_user):
    # Setup a valid unused token
    token_str = "valid-magic-link-token"
    token = AuthToken(
        user_id=test_user.id,
        token=token_str,
        used=False,
        expires_at=datetime.utcnow() + timedelta(minutes=15)
    )
    db_session.add(token)
    db_session.commit()

    response = client.get(f"/auth/verify?token={token_str}", allow_redirects=False)

    # Should redirect to "/"
    assert response.status_code == 302
    assert response.headers["location"] == "/"

    # Should set a cookie
    assert "session_token" in response.cookies
    assert response.cookies["session_token"] == token_str

    # Token should now be marked as used in DB
    db_token = db_session.query(AuthToken).filter_by(token=token_str).first()
    assert db_token.used is True


def test_verify_token_expired_or_invalid(client, db_session, test_user):
    # Setup an expired token
    token_str = "expired-token"
    token = AuthToken(
        user_id=test_user.id,
        token=token_str,
        used=False,
        expires_at=datetime.utcnow() - timedelta(minutes=1)
    )
    db_session.add(token)
    db_session.commit()

    response = client.get(f"/auth/verify?token={token_str}", allow_redirects=False)

    # Should redirect to login with error message
    assert response.status_code == 302
    assert "/login?message=" in response.headers["location"]


def test_logout(auth_client, db_session):
    token_str = auth_client.cookies.get("session_token")

    response = auth_client.post("/auth/logout", allow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/login"

    # Token should be deleted from DB
    db_token = db_session.query(AuthToken).filter_by(token=token_str).first()
    assert db_token is None

    # Cookie should be cleared (FastAPI handles this via max-age=0 or empty value)
    assert not response.cookies.get("session_token")


# ==========================================
# --- DEPENDENCY TESTS (get_current_user) ---
# ==========================================

def test_get_current_user_no_token(db_session):
    """Test that a request with no session cookie is rejected."""
    # Create a mock FastAPI request with empty headers
    request = Request(scope={"type": "http", "headers": []})

    with pytest.raises(HTTPException) as exc:
        get_current_user(request, db_session)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Not authenticated"


def test_get_current_user_invalid_token(db_session):
    """Test that a request with a fake session cookie is rejected."""
    request = Request(scope={
        "type": "http",
        "headers": [(b"cookie", b"session_token=fake-token")]
    })

    with pytest.raises(HTTPException) as exc:
        get_current_user(request, db_session)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid or expired session"


def test_get_current_user_expired_token(db_session, test_user):
    """Test that an expired session token is rejected."""
    token_str = "expired-used-token"
    token = AuthToken(
        user_id=test_user.id,
        token=token_str,
        used=True,  # Used implies it's an active session
        expires_at=datetime.utcnow() - timedelta(minutes=1)  # Expired
    )
    db_session.add(token)
    db_session.commit()

    request = Request(scope={
        "type": "http",
        "headers": [(b"cookie", f"session_token={token_str}".encode("utf-8"))]
    })

    with pytest.raises(HTTPException) as exc:
        get_current_user(request, db_session)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid or expired session"


def test_get_current_user_success(db_session, test_user):
    """Test that a valid session token successfully retrieves the user."""
    token_str = "valid-used-token"
    token = AuthToken(
        user_id=test_user.id,
        token=token_str,
        used=True,
        expires_at=datetime.utcnow() + timedelta(minutes=15)
    )
    db_session.add(token)
    db_session.commit()

    request = Request(scope={
        "type": "http",
        "headers": [(b"cookie", f"session_token={token_str}".encode("utf-8"))]
    })

    user = get_current_user(request, db_session)
    assert user.id == test_user.id


# ==========================================
# --- DEPENDENCY TESTS (require_role) ---
# ==========================================

def test_require_role_success(test_user):
    """Test the role checker allows users with the exact required role."""
    # test_user is defined as UserRole.STUDENT in conftest.py
    checker = require_role(UserRole.STUDENT)

    # Manually execute the dependency injection closure
    result = checker(current_user=test_user)
    assert result.id == test_user.id


def test_require_role_forbidden(test_user):
    """Test the role checker blocks users with the wrong role."""
    # test_user is UserRole.STUDENT, but we require UserRole.TEACHER
    checker = require_role(UserRole.TEACHER)

    with pytest.raises(HTTPException) as exc:
        checker(current_user=test_user)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Insufficient permissions"
