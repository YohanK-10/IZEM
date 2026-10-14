import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from fastapi import FastAPI
from app.models.db import Base, get_db, User, UserRole, AuthToken
from sqlalchemy.pool import StaticPool

# Setup an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool  # <--- THIS IS THE MAGIC LINE
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dummy app if you don't have the main one exported in the snippet
app = FastAPI()
from app.routes.api import router as api_router
from app.routes.auth import router as auth_router

from app.routes import admin_signoff  # Register the same routes as the production app.

app.include_router(api_router)
app.include_router(auth_router)


@pytest.fixture(scope="function")
def db_session():
    """Creates a fresh database on each test case."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Dependency override for get_db to use the test database."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    """Creates a basic student test user."""
    user = User(email="student@test.com", name="Test Student", role=UserRole.STUDENT)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_client(client, db_session, test_user):
    """Returns a TestClient with an active session cookie."""
    token = AuthToken(
        user_id=test_user.id,
        token="test-valid-token-123",
        used=True,
        expires_at=datetime.utcnow() + timedelta(days=1)
    )
    db_session.add(token)
    db_session.commit()

    client.cookies.set("session_token", "test-valid-token-123")
    return client
