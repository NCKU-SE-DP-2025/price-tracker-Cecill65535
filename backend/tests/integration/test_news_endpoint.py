import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker
import json
from jose import jwt
from src.main import create_app

app = create_app()
from src.news.models import NewsArticle
from src.database import Base, get_db
from src.auth.models import User
from src.news.schemas import NewsSummaryRequestSchema
from src.auth.dependencies import auth_service
from unittest.mock import Mock
from src.auth.dependencies import get_current_user
from src.auth.models import User

# 引入爬蟲
from src.crawler.udn_crawler import UDNCrawler

SECRET_KEY = "1892dhianiandowqd0n"
ALGORITHM = "HS256"

# -------------------------------------------------------------
# *** 核心修復 1: 將資料庫連接改為記憶體模式 ***
# -------------------------------------------------------------
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)
pwd_context = auth_service.pwd_context


def override_session_opener():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


_prev_get_db_override = app.dependency_overrides.get(get_db)
app.dependency_overrides[get_db] = override_session_opener


def override_get_current_user():
    return User(id=1, username="testuser")


_prev_get_current_user_override = app.dependency_overrides.get(get_current_user)
app.dependency_overrides[get_current_user] = override_get_current_user


@pytest.fixture(scope="module", autouse=True)
def restore_overrides():
    # Ensure other test modules do not clobber our overrides permanently.
    try:
        yield
    finally:
        # restore previous overrides (None if not present)
        if _prev_get_db_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = _prev_get_db_override

        if _prev_get_current_user_override is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = _prev_get_current_user_override


client = TestClient(app)


# -------------------------------------------------------------
# *** 核心修復 2: 新增自動清空 NewsArticle 表的 Fixture ***
# -------------------------------------------------------------
@pytest.fixture(scope="function", autouse=True)
def clean_news_articles():
    """在每個測試開始和結束後自動清空 NewsArticle 表格"""
    db = next(override_session_opener())
    try:
        # 測試開始前清空
        db.query(NewsArticle).delete()
        db.commit()
        yield db  # 執行測試
    finally:
        # 測試結束後再次清空
        db.query(NewsArticle).delete()
        db.commit()
        db.close()


# -------------------------------------------------------------
# *** 以下 Fixtures 保持不變，或已根據上次的修改調整 ***
# -------------------------------------------------------------


@pytest.fixture(scope="module")
def clear_users():
    with next(override_session_opener()) as db:
        db.query(User).delete()
        db.commit()


@pytest.fixture(scope="module")
def test_user(clear_users):
    hashed_password = pwd_context.hash("testpassword")
    with next(override_session_opener()) as db:
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


# test_articles 移除內部的清理邏輯，讓 clean_news_articles 處理
@pytest.fixture(scope="function")
def test_articles():
    db = next(override_session_opener())
    try:
        article_1 = NewsArticle(
            url="https://example.com/test-news-1",
            title="Test News 1",
            content="This is test content 1",
            time="2024-01-01",
            summary="Test summary 1",
            reason="Test reason 1",
        )
        article_2 = NewsArticle(
            url="https://example.com/test-news-2",
            title="Test News 2",
            content="This is test content 2",
            time="2024-01-02",
            summary="Test summary 2",
            reason="Test reason 2",
        )
        db.add_all([article_1, article_2])
        db.commit()
        db.refresh(article_1)
        db.refresh(article_2)
        yield [article_1, article_2]
    finally:
        # 由於 clean_news_articles 已經處理了清理，這裡 close 即可。
        db.close()


@pytest.fixture(scope="function")
def test_user_and_articles(test_user, test_articles):
    return test_user, test_articles


# -------------------------------------------------------------
# *** 測試函式部分保持不變 ***
# -------------------------------------------------------------


def test_read_news(test_articles):
    response = client.get("/api/v1/news/news")
    assert response.status_code == 200
    json_response = response.json()
    # 由於 clean_news_articles 運行在前，test_articles 寫入 2 篇，這裡應為 2
    assert len(json_response) == 2


def test_read_user_news(test_user, test_token, test_articles):
    headers = {"Authorization": f"Bearer {test_token}"}
    response = client.get("/api/v1/news/user_news", headers=headers)
    assert response.status_code == 200
    json_response = response.json()
    assert len(json_response) == 2


def mock_openai(mocker, return_content):
    # Mock OpenAI，路徑要正確
    mock_openai_client = mocker.patch("src.core.ai.OpenAI")
    mock_message = Mock()
    mock_message.content = return_content
    mock_choice = Mock()
    mock_choice.message = mock_message
    mock_completion = Mock()
    mock_completion.choices = [mock_choice]
    mock_openai_client.return_value.chat.completions.create.return_value = (
        mock_completion
    )
    return mock_openai_client


def test_search_news(mocker):
    # 1. Mock OpenAI 關鍵字提取
    mock_openai(mocker, "keywords")

    # 2. Mock 爬蟲的 get_headline
    from src.crawler.crawler_base import Headline, News

    mock_headline_data = [Headline(title="Test Title", url="http://example.com/news1")]
    mocker.patch(
        "src.crawler.udn_crawler.UDNCrawler.get_headline",
        return_value=mock_headline_data,
    )

    # 3. Mock 爬蟲的 parse
    mock_parsed_data = News(
        title="Test Title",
        url="http://example.com/news1",
        time="2024-09-10",
        content="This is a test paragraph.",
    )
    mocker.patch(
        "src.crawler.udn_crawler.UDNCrawler.parse", return_value=mock_parsed_data
    )

    # 4. 發送請求
    request_body = {"prompt": "Test search prompt"}
    response = client.post("/api/v1/news/search_news", json=request_body)

    # 5. 驗證結果
    assert response.status_code == 200
    data = response.json()
    # clean_news_articles 已經確保資料庫是空的，所以 search 應該只回傳 1 篇爬蟲找到的
    assert len(data) == 1
    assert data[0]["title"] == "Test Title"
    assert data[0]["time"] == "2024-09-10"
    assert data[0]["content"] == "This is a test paragraph."


def test_news_summary(mocker, test_token):
    headers = {"Authorization": f"Bearer {test_token}"}
    openai_response = json.dumps({"影響": "test impact", "原因": "test reason"})
    mock_openai(mocker, openai_response)

    request_body = NewsSummaryRequestSchema(content="Test news content")
    response = client.post(
        "/api/v1/news/news_summary", json=request_body.dict(), headers=headers
    )

    assert response.status_code == 200
    json_response = response.json()
    assert json_response["summary"] == "test impact"
    assert json_response["reason"] == "test reason"


def test_upvote_article(test_user_and_articles, test_token):
    user, articles = test_user_and_articles
    headers = {"Authorization": f"Bearer {test_token}"}
    response = client.post(f"/api/v1/news/{articles[0].id}/upvote", headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Article upvoted"


def test_downvote_article(test_user_and_articles, test_token):
    user, articles = test_user_and_articles
    headers = {"Authorization": f"Bearer {test_token}"}
    response = client.post(f"/api/v1/news/{articles[0].id}/upvote", headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Upvote removed"
