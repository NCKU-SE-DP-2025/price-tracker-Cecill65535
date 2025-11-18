# src/news/router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from src.database import get_db
from src.news.schemas import PromptRequest, NewsSummaryRequestSchema
from src.news.service import NewsRepository, UpvoteService, NewsService
from src.core.ai import AIService
from src.core.scraper import NewsScraper
from src.config import Config
from src.auth.dependencies import get_current_user # 匯入依賴項
from src.auth.models import User # 為了 get_current_user

router = APIRouter(
    prefix="/news",  # 所有路徑都會自動加上 /news
    tags=["news"]
)

# ===================================================================
# === 步驟 1：建立 Service 的「依賴項函式」(Factories) ===
# ===================================================================

def get_ai_service():
    """AIService 的依賴項"""
    config = Config() 
    return AIService(api_key=config.OPENAI_API_KEY)

def get_scraper():
    """NewsScraper 的依賴項"""
    return NewsScraper()

def get_news_service(
    ai_service: AIService = Depends(get_ai_service),
    scraper: NewsScraper = Depends(get_scraper)
):
    """NewsService 的依賴項"""
    return NewsService(ai_service=ai_service, scraper=scraper)

# ===================================================================
# === 步驟 2：刪除在「全域」建立的實例 ===
# ===================================================================

# (我們把這幾行刪除或註解掉，因為它們是 Bug 的來源)
# config = Config()
# ai_service_instance = AIService(config.OPENAI_API_KEY)
# news_service_instance = NewsService(ai_service_instance, NewsScraper())


# ===================================================================
# === 步驟 3：在路由中「注入」依賴項 ===
# ===================================================================

# 3. 這是【讀取所有新聞】路由 (這個路由OK，不需要 NewsService)
@router.get("/news")
def read_all_news(db: Session = Depends(get_db)):
    news_repo = NewsRepository(db)
    upvote_service = UpvoteService(db)
    articles = news_repo.get_all_articles()
    
    result = []
    for article in articles:
        upvotes, upvoted = upvote_service.get_upvote_details(article.id, None) 
        result.append({**article.__dict__, "upvotes": upvotes, "is_upvoted": upvoted})
    return result

# 4. 這是【讀取用戶相關新聞】路由 (這個路由OK，不需要 NewsService)
@router.get("/user_news")
def read_user_news(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) 
):
    news_repo = NewsRepository(db)
    upvote_service = UpvoteService(db)
    articles = news_repo.get_all_articles()
    
    result = []
    for article in articles:
        upvotes, upvoted = upvote_service.get_upvote_details(article.id, current_user.id)
        result.append({**article.__dict__, "upvotes": upvoted, "is_upvoted": upvoted})
    return result

# 5. 這是【搜尋新聞】路由 (重構版)
@router.post("/search_news")
def search_news(
    request: PromptRequest,
    news_service: NewsService = Depends(get_news_service) # ⭐️ 修正：注入 NewsService
):
    # ⭐️ 修正：使用被注入的 news_service
    return news_service.search_news(request.prompt)

# 6. 這是【新聞摘要】路由 (重構版)
@router.post("/news_summary")
def news_summary(
    payload: NewsSummaryRequestSchema,
    current_user: User = Depends(get_current_user), 
    news_service: NewsService = Depends(get_news_service) # ⭐️ 修正：注入 NewsService
):
    # ⭐️ 修正：使用被注入的 news_service
    return news_service.generate_news_summary(payload.content)

# 7. 這是【按讚】路由 (這個路由OK，不需要 NewsService)
@router.post("/{id}/upvote")
def upvote_article(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) 
):
    upvote_service = UpvoteService(db)
    message = upvote_service.toggle_upvote(id, current_user.id)
    return {"message": message}