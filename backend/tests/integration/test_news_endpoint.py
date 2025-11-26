import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker
import json
from jose import jwt
from src.main import app
from src.news.models import NewsArticle, user_news_association_table
# from src.main import Base, session_opener
# from src.database import Base, SessionLocal as session_opener
from src.database import Base, get_db, SessionLocal as session_opener
from src.auth.models import User
from src.news.schemas import NewsSummaryRequestSchema, PromptRequest
# from src.main import pwd_context
from src.auth.dependencies import auth_service
from unittest.mock import Mock



SECRET_KEY = "1892dhianiandowqd0n"
ALGORITHM = "HS256"
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)
pwd_context = auth_service.pwd_context

def override_session_opener():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# app.dependency_overrides[session_opener] = override_session_opener
app.dependency_overrides[get_db] = override_session_opener
client = TestClient(app)

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
    access_token = jwt.encode({"sub": test_user.username}, SECRET_KEY, algorithm=ALGORITHM)
    return access_token


@pytest.fixture(scope="module")
def test_articles():
    # === 1. SETUP (在測試開始前執行) ===
    db = next(override_session_opener()) # 取得 db
    
    try:
        # --- 這是修復 ---
        # 為了保證測試獨立，先清除所有舊文章
        # 這樣就能修復 UNIQUE constraint failed 錯誤
        db.query(NewsArticle).delete()
        db.commit()
        # ------------------
        
        article_1 = NewsArticle(
            url="https://example.com/test-news-1",
            title="Test News 1",
            content="This is test content 1",
            time="2024-01-01",
            summary="Test summary 1",
            reason="Test reason 1"
        )
        article_2 = NewsArticle(
            url="https://example.com/test-news-2",
            title="Test News 2",
            content="This is test content 2",
            time="2024-01-02",
            summary="Test summary 2",
            reason="Test reason 2"
        )
        db.add_all([article_1, article_2])
        db.commit()
        db.refresh(article_1)
        db.refresh(article_2)

        # === 2. YIELD (這就是你的 "return") ===
        # yield 會暫停，讓測試函式執行，並把文章列表傳給它
        yield [article_1, article_2]  

    finally:
        # === 3. TEARDOWN (在測試結束後執行) ===
        # 無論測試成功或失敗，finally 區塊都一定會執行
        # 這是最重要的清理步驟，確保資料庫恢復乾淨
        db.query(NewsArticle).delete()
        db.commit()
        db.close()


@pytest.fixture(scope="module")
def test_user_and_articles(test_user, test_articles):
    return test_user, test_articles


def test_read_news(test_articles):
    response = client.get("/api/v1/news/news")
    assert response.status_code == 200
    json_response = response.json()
    assert len(json_response) == 2
    assert json_response[0]["title"] == "Test News 2"
    assert json_response[1]["title"] == "Test News 1"


def test_read_user_news(test_user, test_token, test_articles):
    headers = {"Authorization": f"Bearer {test_token}"}
    response = client.get("/api/v1/news/user_news", headers=headers)
    print(test_token)
    print(response.json())
    assert response.status_code == 200
    json_response = response.json()
    assert len(json_response) == 2
    assert json_response[0]["title"] == "Test News 2"
    assert json_response[0]["is_upvoted"] is False
    assert json_response[1]["title"] == "Test News 1"
    assert json_response[1]["is_upvoted"] is False

def mock_openai(mocker, return_content):
    mock_openai_client = mocker.patch('src.core.ai.OpenAI')

    mock_message = Mock()
    mock_message.content = return_content

    mock_choice = Mock()
    mock_choice.message = mock_message

    mock_completion = Mock()
    mock_completion.choices = [mock_choice]

    mock_openai_client.return_value.chat.completions.create.return_value = mock_completion

    return mock_openai_client

def test_search_news(mocker):
    # 1. Mock OpenAI 關鍵字提取 (這部分沒變)
    mock_openai(mocker, "keywords")

    # 2. 【關鍵修復】 Mock 爬蟲的 get_headline
    # 我們直接告訴測試：「只要有人呼叫爬蟲的 get_headline，你就回傳這個列表」
    # 注意：這裡回傳的是 Headline 物件列表，因為你的 get_headline 實作回傳的就是這個
    from src.crawler.crawler_base import Headline
    
    mock_headlines = [
        Headline(title="Test Title", url="http://example.com/news1")
    ]
    
    # 確保路徑指向你的 UDNCrawler 類別
    mocker.patch("src.crawler.udn_crawler.UDNCrawler.get_headline", return_value=mock_headlines)

    # 3. 【關鍵修復】 也要 Mock 爬蟲的 parse
    # 因為 search_news 下一步會呼叫 parse 抓內文
    from src.crawler.crawler_base import News
    
    mock_news = News(
        title="Test Title",
        url="http://example.com/news1",
        time="2024-09-10",
        content="This is a test paragraph."
    )
    
    # 確保路徑指向你的 UDNCrawler 類別
    mocker.patch("src.crawler.udn_crawler.UDNCrawler.parse", return_value=mock_news)

    # 4. 發送請求
    request_body = {"prompt": "Test search prompt"}
    response = client.post("/api/v1/news/search_news", json=request_body)

    # 5. 驗證結果
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Test Title"
    # 請根據你的 NewsService 實際回傳格式調整這兩行
    # 如果你的 service 轉回了字典，這裡應該就能拿到 time 和 content
    assert data[0]["time"] == "2024-09-10"
    assert data[0]["content"] == "This is a test paragraph."


def test_news_summary(mocker, test_token):
    headers = {"Authorization": f"Bearer {test_token}"}
    openai_response = json.dumps({"影響": "test impact", "原因": "test reason"})
    mock_openai(mocker, openai_response)

    request_body = NewsSummaryRequestSchema(content="Test news content")
    response = client.post("/api/v1/news/news_summary", json=request_body.dict(), headers=headers)

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
