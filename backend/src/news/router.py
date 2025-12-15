# src/news/router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from src.database import get_db
from src.news.schemas import PromptRequest, NewsSummaryRequestSchema
from src.news.service import NewsRepository, UpvoteService, NewsService
from src.core.ai import AIService
from src.core.scraper import NewsScraper  # 使用 core 的可被測試 patch 的爬蟲
from src.config import Config
from src.auth.dependencies import get_current_user
from src.auth.models import User

router = APIRouter(prefix="/news", tags=["news"])


def get_ai_service():
    config = Config()
    return AIService(api_key=config.OPENAI_API_KEY)


def get_scraper():
    return NewsScraper()


def get_news_service(
    ai_service: AIService = Depends(get_ai_service),
    scraper: NewsScraper = Depends(get_scraper),
):
    return NewsService(ai_service=ai_service, scraper=scraper)


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


@router.get("/user_news")
def read_user_news(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    news_repo = NewsRepository(db)
    upvote_service = UpvoteService(db)
    articles = news_repo.get_all_articles()

    result = []
    for article in articles:
        upvotes, upvoted = upvote_service.get_upvote_details(
            article.id, current_user.id
        )
        result.append({**article.__dict__, "upvotes": upvotes, "is_upvoted": upvoted})
    return result


@router.post("/search_news")
def search_news(
    request: PromptRequest, news_service: NewsService = Depends(get_news_service)
):
    return news_service.search_news(request.prompt)


@router.post("/news_summary")
def news_summary(
    payload: NewsSummaryRequestSchema,
    current_user: User = Depends(get_current_user),
    news_service: NewsService = Depends(get_news_service),  # ⭐️ 修正：注入 NewsService
):
    return news_service.generate_news_summary(payload.content)


@router.post("/{id}/upvote")
def upvote_article(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    upvote_service = UpvoteService(db)
    message = upvote_service.toggle_upvote(id, current_user.id)
    return {"message": message}
