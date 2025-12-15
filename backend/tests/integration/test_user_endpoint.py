import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker
from src.main import create_app

app = create_app()

# 修正 1: 改用 get_db
from src.database import Base, get_db
from src.auth.models import User
from jose import jwt
from src.auth.dependencies import auth_service

SECRET_KEY = "1892dhianiandowqd0n"
ALGORITHM = "HS256"
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

# 設定測試用的 SQLite
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

pwd_context = auth_service.pwd_context


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# 修正 2: 覆蓋正確的依賴 (get_db)
_prev_get_db_override = app.dependency_overrides.get(get_db)
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module", autouse=True)
def restore_get_db_override():
    try:
        yield
    finally:
        if _prev_get_db_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = _prev_get_db_override


client = TestClient(app)


@pytest.fixture(scope="module")
def clear_users():
    # 修正 3: 使用 override_get_db
    with next(override_get_db()) as db:
        db.query(User).delete()
        db.commit()


@pytest.fixture(scope="module")
def test_user(clear_users):
    hashed_password = pwd_context.hash("testpassword")

    # 修正 4: 使用 override_get_db
    with next(override_get_db()) as db:
        user = User(username="testuser", hashed_password=hashed_password)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


@pytest.fixture(scope="module")
def test_token(test_user):
    access_token = jwt.encode(
        {"sub": test_user.username}, SECRET_KEY, algorithm=ALGORITHM
    )
    return access_token


def test_register_user():
    response = client.post(
        "/api/v1/users/register",
        json={"username": "newuser", "password": "newpassword"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser"


def test_login_for_access_token(test_user):
    response = client.post(
        "/api/v1/users/login", data={"username": "testuser", "password": "testpassword"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_read_users_me(test_token):
    headers = {"Authorization": f"Bearer {test_token}"}
    response = client.get("/api/v1/users/me", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
