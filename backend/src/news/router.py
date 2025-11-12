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

# 2. 建立需要的 Service 實例
# (這是簡易作法，未來可以用 Depends 注入)
config = Config()
ai_service_instance = AIService(config.OPENAI_API_KEY)
news_service_instance = NewsService(ai_service_instance, NewsScraper())


# 3. 這是【讀取所有新聞】路由 (重構版)
@router.get("/news")
def read_all_news(db: Session = Depends(get_db)):
    news_repo = NewsRepository(db)
    upvote_service = UpvoteService(db)
    articles = news_repo.get_all_articles()
    
    result = []
    for article in articles:
        # 我們在這裡不需要 user_id，所以傳 None
        upvotes, upvoted = upvote_service.get_upvote_details(article.id, None) 
        result.append({**article.__dict__, "upvotes": upvotes, "is_upvoted": upvoted})
    return result

# 4. 這是【讀取用戶相關新聞】路由 (重構版)
@router.get("/user_news")
def read_user_news(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # ⭐️ 使用新的依賴項
):
    news_repo = NewsRepository(db)
    upvote_service = UpvoteService(db)
    articles = news_repo.get_all_articles()
    
    result = []
    for article in articles:
        # 傳入 current_user.id 來檢查用戶是否按讚
        upvotes, upvoted = upvote_service.get_upvote_details(article.id, current_user.id)
        result.append({**article.__dict__, "upvotes": upvotes, "is_upvoted": upvoted})
    return result

# 5. 這是【搜尋新聞】路由 (重構版)
@router.post("/search_news")
def search_news(request: PromptRequest):
    # 注意：這裡不再有 self.news_service
    return news_service_instance.search_news(request.prompt)

# 6. 這是【新聞摘要】路由 (重構版)
@router.post("/news_summary")
def news_summary(
    payload: NewsSummaryRequestSchema,
    # 驗證使用者是否登入
    current_user: User = Depends(get_current_user) 
):
    return news_service_instance.generate_news_summary(payload.content)

# 7. 這是【按讚】路由 (重構版)
@router.post("/{id}/upvote")
def upvote_article(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # ⭐️ 使用新的依賴項
):
    upvote_service = UpvoteService(db)
    message = upvote_service.toggle_upvote(id, current_user.id)
    return {"message": message}