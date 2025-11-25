# src/news/service.py
import itertools
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import delete, insert, select

# 匯入我們自己寫的 .models
from .models import NewsArticle, user_news_association_table

# 匯入 core 裡的 service
from src.core.ai import AIService
# ⭐️ 修正：匯入正確的 Base Class
from src.crawler.crawler_base import NewsCrawlerBase

# ==================== News Repository ====================
# (這部分沒變，保持原樣)
class NewsRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def add_article(self, news_data: dict):
        """Add news article to database"""
        article = NewsArticle(
            url=news_data["url"],
            title=news_data["title"],
            time=news_data["time"],
            content=" ".join(news_data["content"]) if isinstance(news_data["content"], list) else news_data["content"],
            summary=news_data["summary"],
            reason=news_data["reason"],
        )
        self.db.add(article)
        self.db.commit()
    
    def get_all_articles(self) -> List[NewsArticle]:
        """Get all articles ordered by time"""
        return self.db.query(NewsArticle).order_by(NewsArticle.time.desc()).all()
    
    def get_article_by_id(self, article_id: int) -> Optional[NewsArticle]:
        """Get article by ID"""
        return self.db.query(NewsArticle).filter_by(id=article_id).first()
    
    def article_exists(self, article_id: int) -> bool:
        """Check if article exists"""
        return self.get_article_by_id(article_id) is not None
    
    def count_articles(self) -> int:
        """Count total articles"""
        return self.db.query(NewsArticle).count()
    
# ==================== Upvote Service ====================
# (這部分沒變，保持原樣)
class UpvoteService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_upvote_details(self, article_id: int, user_id: Optional[int] = None) -> tuple:
        """Get upvote count and user's upvote status"""
        count = (
            self.db.query(user_news_association_table)
            .filter_by(news_articles_id=article_id)
            .count()
        )
        
        voted = False
        if user_id:
            voted = (
                self.db.query(user_news_association_table)
                .filter_by(news_articles_id=article_id, user_id=user_id)
                .first()
                is not None
            )
        
        return count, voted
    
    def toggle_upvote(self, article_id: int, user_id: int) -> str:
        """Toggle upvote for an article"""
        existing_upvote = self.db.execute(
            select(user_news_association_table).where(
                user_news_association_table.c.news_articles_id == article_id,
                user_news_association_table.c.user_id == user_id,
            )
        ).scalar()
        
        if existing_upvote:
            delete_stmt = delete(user_news_association_table).where(
                user_news_association_table.c.news_articles_id == article_id,
                user_news_association_table.c.user_id == user_id,
            )
            self.db.execute(delete_stmt)
            self.db.commit()
            return "Upvote removed"
        else:
            insert_stmt = insert(user_news_association_table).values(
                news_articles_id=article_id, user_id=user_id
            )
            self.db.execute(insert_stmt)
            self.db.commit()
            return "Article upvoted"

# ==================== News Service ====================
class NewsService:
    # ⭐️ 修正：Type Hint 改成 NewsCrawlerBase
    def __init__(self, ai_service: AIService, scraper: NewsCrawlerBase):
        self.ai_service = ai_service
        self.scraper = scraper
        self._id_counter = itertools.count(start=1000000)
    
    def fetch_and_process_initial_news(self, db: Session, is_initial: bool = False):
        """Fetch and process initial news about prices"""
        news_repo = NewsRepository(db)
        
        # ⭐️ 修正 1: 把 is_initial 轉換成 page 參數
        # 因為 get_headline 不接受 is_initial
        page_param = (1, 10) if is_initial else 1
        news_list = self.scraper.get_headline("價格", page=page_param)
        
        for news in news_list:
            # ⭐️ 修正 2: news 是 Headline 物件，要用 .title 存取 (不是 ["title"])
            title = news.title
            relevance = self.ai_service.evaluate_relevance(title)
            
            if relevance == "high":
                try:
                    # ⭐️ 修正 3: 改用 parse 方法，並傳入 news.url
                    # parse 回傳的是 News 物件
                    news_obj = self.scraper.parse(news.url)
                    
                    # news_obj.content 已經是處理好的字串了
                    content_text = news_obj.content
                    
                    summary_result = self.ai_service.generate_summary(content_text)
                    
                    # ⭐️ 修正 4: 把 News 物件轉成 dict 餵給 NewsRepository
                    news_data_dict = {
                        "url": str(news_obj.url),
                        "title": news_obj.title,
                        "time": news_obj.time,
                        "content": news_obj.content,
                        "summary": summary_result["影響"],
                        "reason": summary_result["原因"]
                    }
                    
                    news_repo.add_article(news_data_dict)
                except Exception as e:
                    print(f"Error processing news: {e}")
    
    def search_news(self, prompt: str) -> list:
        """Search news based on user prompt"""
        keywords = self.ai_service.extract_keywords(prompt)
        
        # ⭐️ 修正 5: 改用 get_headline，並指定 page=1
        news_items = self.scraper.get_headline(keywords, page=1)
        news_list = []
        
        for news in news_items:
            try:
                # ⭐️ 修正 6: 改用 parse，且 news 是 Headline 物件
                news_obj = self.scraper.parse(news.url)
                
                # ⭐️ 修正 7: 建立回傳給前端的字典
                detailed_news = {
                    "url": str(news_obj.url),
                    "title": news_obj.title,
                    "time": news_obj.time,
                    "content": news_obj.content,
                    "id": next(self._id_counter)
                }
                news_list.append(detailed_news)
            except Exception as e:
                print(f"Error fetching news: {e}")
        
        return sorted(news_list, key=lambda x: x["time"], reverse=True)
    
    def generate_news_summary(self, content: str) -> dict:
        """Generate summary for news content"""
        result = self.ai_service.generate_summary(content)
        return {
            "summary": result["影響"],
            "reason": result["原因"]
        }