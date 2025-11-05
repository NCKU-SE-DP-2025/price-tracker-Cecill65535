import json
import sentry_sdk
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi.middleware.cors import CORSMiddleware
import itertools
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session, sessionmaker, relationship
from typing import List, Optional
import requests
from fastapi import APIRouter, HTTPException, Query, Depends, status, FastAPI
import os
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, AnyHttpUrl
from sqlalchemy import (Column, ForeignKey, Integer, String, Table, Text,
                        create_engine)
from sqlalchemy.ext.declarative import declarative_base
from urllib.parse import quote
from bs4 import BeautifulSoup
from openai import OpenAI

Base = declarative_base()

# ==================== Database Models ====================
user_news_association_table = Table(
    "user_news_upvotes",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("news_articles_id", Integer, ForeignKey("news_articles.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    upvoted_news = relationship(
        "NewsArticle",
        secondary=user_news_association_table,
        back_populates="upvoted_by_users",
    )


class NewsArticle(Base):
    __tablename__ = "news_articles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    time = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    upvoted_by_users = relationship(
        "User", secondary=user_news_association_table, back_populates="upvoted_news"
    )


# ==================== Pydantic Schemas ====================
class UserAuthSchema(BaseModel):
    username: str
    password: str


class PromptRequest(BaseModel):
    prompt: str


class NewsSummaryRequestSchema(BaseModel):
    content: str


# ==================== Configuration ====================
class Config:
    DATABASE_URL = "sqlite:///news_database.db"
    SENTRY_DSN = "https://4001ffe917ccb261aa0e0c34026dc343@o4505702629834752.ingest.us.sentry.io/4507694792704000"
    JWT_SECRET = "1892dhianiandowqd0n"
    JWT_ALGORITHM = "HS256"
    OPENAI_API_KEY = "xxx"
    CORS_ORIGINS = ["http://localhost:8080"]


# ==================== Database Manager ====================
class DatabaseManager:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, echo=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def get_session(self):
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()


# ==================== AI Service ====================
class AIService:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
    
    def generate_summary(self, content: str) -> dict:
        """Generate news summary with impact and reason"""
        messages = [
            {
                "role": "system",
                "content": "你是一個新聞摘要生成機器人,請統整新聞中提及的影響及主要原因 (影響、原因各50個字,請以json格式回答 {'影響': '...', '原因': '...'})",
            },
            {"role": "user", "content": content},
        ]
        
        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )
        result = completion.choices[0].message.content
        return json.loads(result)
    
    def extract_keywords(self, prompt: str) -> str:
        """Extract search keywords from user prompt"""
        messages = [
            {
                "role": "system",
                "content": "你是一個關鍵字提取機器人,用戶將會輸入一段文字,表示其希望看見的新聞內容,請提取出用戶希望看見的關鍵字,請截取最重要的關鍵字即可,避免出現「新聞」、「資訊」等混淆搜尋引擎的字詞。(僅須回答關鍵字,若有多個關鍵字,請以空格分隔)",
            },
            {"role": "user", "content": prompt},
        ]
        
        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )
        return completion.choices[0].message.content
    
    def evaluate_relevance(self, title: str) -> str:
        """Evaluate news relevance to price changes"""
        messages = [
            {
                "role": "system",
                "content": "你是一個關聯度評估機器人,請評估新聞標題是否與「民生用品的價格變化」相關,並給予'high'、'medium'、'low'評價。(僅需回答'high'、'medium'、'low'三個詞之一)",
            },
            {"role": "user", "content": title},
        ]
        
        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )
        return completion.choices[0].message.content


# ==================== News Scraper ====================
class NewsScraper:
    BASE_URL = "https://udn.com/api/more"
    
    @staticmethod
    def fetch_news_list(search_term: str, is_initial: bool = False) -> list:
        """Fetch news list from UDN API"""
        all_news_data = []
        
        if is_initial:
            for page in range(1, 10):
                params = {
                    "page": page,
                    "id": f"search:{quote(search_term)}",
                    "channelId": 2,
                    "type": "searchword",
                }
                response = requests.get(NewsScraper.BASE_URL, params=params)
                all_news_data.extend(response.json()["lists"])
        else:
            params = {
                "page": 1,
                "id": f"search:{quote(search_term)}",
                "channelId": 2,
                "type": "searchword",
            }
            response = requests.get(NewsScraper.BASE_URL, params=params)
            all_news_data = response.json()["lists"]
        
        return all_news_data
    
    @staticmethod
    def fetch_article_content(url: str) -> dict:
        """Fetch detailed article content from URL"""
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        
        title = soup.find("h1", class_="article-content__title").text
        time = soup.find("time", class_="article-content__time").text
        content_section = soup.find("section", class_="article-content__editor")
        
        paragraphs = [
            page.text
            for page in content_section.find_all("page")
            if page.text.strip() != "" and "▪" not in page.text
        ]
        
        return {
            "url": url,
            "title": title,
            "time": time,
            "content": paragraphs,
        }


# ==================== News Repository ====================
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


# ==================== User Repository ====================
class UserRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def create_user(self, username: str, hashed_password: str) -> User:
        """Create new user"""
        user = User(username=username, hashed_password=hashed_password)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self.db.query(User).filter(User.username == username).first()


# ==================== Upvote Service ====================
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


# ==================== Authentication Service ====================
class AuthService:
    def __init__(self, secret_key: str, algorithm: str):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def hash_password(self, password: str) -> str:
        """Hash password"""
        return self.pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def decode_token(self, token: str) -> dict:
        """Decode JWT token"""
        return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
    
    def authenticate_user(self, db: Session, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password"""
        user_repo = UserRepository(db)
        user = user_repo.get_user_by_username(username)
        if not user or not self.verify_password(password, user.hashed_password):
            return None
        return user


# ==================== News Service ====================
class NewsService:
    def __init__(self, ai_service: AIService, scraper: NewsScraper):
        self.ai_service = ai_service
        self.scraper = scraper
        self._id_counter = itertools.count(start=1000000)
    
    def fetch_and_process_initial_news(self, db: Session, is_initial: bool = False):
        """Fetch and process initial news about prices"""
        news_repo = NewsRepository(db)
        news_list = self.scraper.fetch_news_list("價格", is_initial=is_initial)
        
        for news in news_list:
            title = news["title"]
            relevance = self.ai_service.evaluate_relevance(title)
            
            if relevance == "high":
                try:
                    detailed_news = self.scraper.fetch_article_content(news["titleLink"])
                    content_text = " ".join(detailed_news["content"])
                    
                    summary_result = self.ai_service.generate_summary(content_text)
                    detailed_news["summary"] = summary_result["影響"]
                    detailed_news["reason"] = summary_result["原因"]
                    
                    news_repo.add_article(detailed_news)
                except Exception as e:
                    print(f"Error processing news: {e}")
    
    def search_news(self, prompt: str) -> list:
        """Search news based on user prompt"""
        keywords = self.ai_service.extract_keywords(prompt)
        news_items = self.scraper.fetch_news_list(keywords, is_initial=False)
        news_list = []
        
        for news in news_items:
            try:
                detailed_news = self.scraper.fetch_article_content(news["titleLink"])
                detailed_news["content"] = " ".join(detailed_news["content"])
                detailed_news["id"] = next(self._id_counter)
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


# ==================== Application Factory ====================
class NewsApplication:
    def __init__(self, config: Config):
        self.config = config
        self.app = FastAPI()
        self.db_manager = DatabaseManager(config.DATABASE_URL)
        self.auth_service = AuthService(config.JWT_SECRET, config.JWT_ALGORITHM)
        self.ai_service = AIService(config.OPENAI_API_KEY)
        self.news_service = NewsService(self.ai_service, NewsScraper())
        self.scheduler = BackgroundScheduler()
        
        self._setup_sentry()
        self._setup_middleware()
        self._setup_routes()
        self._setup_events()
    
    def _setup_sentry(self):
        """Setup Sentry monitoring"""
        sentry_sdk.init(
            dsn=self.config.SENTRY_DSN,
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
        )
    
    def _setup_middleware(self):
        """Setup CORS middleware"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _get_current_user(self, token: str = Depends(None), db: Session = Depends(None)):
        """Dependency to get current authenticated user"""
        if token is None:
            token = Depends(self.auth_service.oauth2_scheme)
        if db is None:
            db = Depends(self.db_manager.get_session)
        
        payload = self.auth_service.decode_token(token)
        user_repo = UserRepository(db)
        return user_repo.get_user_by_username(payload.get("sub"))
    
    def _setup_routes(self):
        """Setup all API routes"""
        
        @self.app.post("/api/v1/users/register")
        def register(user: UserAuthSchema, db: Session = Depends(self.db_manager.get_session)):
            user_repo = UserRepository(db)
            hashed_password = self.auth_service.hash_password(user.password)
            return user_repo.create_user(user.username, hashed_password)
        
        @self.app.post("/api/v1/users/login")
        def login(
            form_data: OAuth2PasswordRequestForm = Depends(),
            db: Session = Depends(self.db_manager.get_session)
        ):
            user = self.auth_service.authenticate_user(db, form_data.username, form_data.password)
            if not user:
                raise HTTPException(status_code=401, detail="Incorrect username or password")
            
            access_token = self.auth_service.create_access_token(
                data={"sub": user.username},
                expires_delta=timedelta(minutes=30)
            )
            return {"access_token": access_token, "token_type": "bearer"}
        
        @self.app.get("/api/v1/users/me")
        def read_users_me(
            token: str = Depends(self.auth_service.oauth2_scheme),
            db: Session = Depends(self.db_manager.get_session)
        ):
            payload = self.auth_service.decode_token(token)
            user_repo = UserRepository(db)
            user = user_repo.get_user_by_username(payload.get("sub"))
            return {"username": user.username}
        
        @self.app.get("/api/v1/news/news")
        def read_all_news(db: Session = Depends(self.db_manager.get_session)):
            news_repo = NewsRepository(db)
            upvote_service = UpvoteService(db)
            articles = news_repo.get_all_articles()
            
            result = []
            for article in articles:
                upvotes, upvoted = upvote_service.get_upvote_details(article.id)
                result.append({**article.__dict__, "upvotes": upvotes, "is_upvoted": upvoted})
            return result
        
        @self.app.get("/api/v1/news/user_news")
        def read_user_news(
            db: Session = Depends(self.db_manager.get_session),
            token: str = Depends(self.auth_service.oauth2_scheme)
        ):
            payload = self.auth_service.decode_token(token)
            user_repo = UserRepository(db)
            current_user = user_repo.get_user_by_username(payload.get("sub"))
            
            news_repo = NewsRepository(db)
            upvote_service = UpvoteService(db)
            articles = news_repo.get_all_articles()
            
            result = []
            for article in articles:
                upvotes, upvoted = upvote_service.get_upvote_details(article.id, current_user.id)
                result.append({**article.__dict__, "upvotes": upvotes, "is_upvoted": upvoted})
            return result
        
        @self.app.post("/api/v1/news/search_news")
        def search_news(request: PromptRequest):
            return self.news_service.search_news(request.prompt)
        
        @self.app.post("/api/v1/news/news_summary")
        def news_summary(
            payload: NewsSummaryRequestSchema,
            token: str = Depends(self.auth_service.oauth2_scheme)
        ):
            return self.news_service.generate_news_summary(payload.content)
        
        @self.app.post("/api/v1/news/{id}/upvote")
        def upvote_article(
            id: int,
            db: Session = Depends(self.db_manager.get_session),
            token: str = Depends(self.auth_service.oauth2_scheme)
        ):
            payload = self.auth_service.decode_token(token)
            user_repo = UserRepository(db)
            current_user = user_repo.get_user_by_username(payload.get("sub"))
            
            upvote_service = UpvoteService(db)
            message = upvote_service.toggle_upvote(id, current_user.id)
            return {"message": message}
        
        @self.app.get("/api/v1/prices/necessities-price")
        def get_necessities_prices(category: str = Query(None), commodity: str = Query(None)):
            return requests.get(
                "https://opendata.ey.gov.tw/api/ConsumerProtection/NecessitiesPrice",
                params={"CategoryName": category, "Name": commodity},
            ).json()
    
    def _setup_events(self):
        """Setup startup and shutdown events"""
        
        @self.app.on_event("startup")
        def start_scheduler():
            db = next(self.db_manager.get_session())
            news_repo = NewsRepository(db)
            
            if news_repo.count_articles() == 0:
                self.news_service.fetch_and_process_initial_news(db, is_initial=True)
            
            self.scheduler.add_job(
                lambda: self.news_service.fetch_and_process_initial_news(
                    next(self.db_manager.get_session())
                ),
                "interval",
                minutes=100
            )
            self.scheduler.start()
        
        @self.app.on_event("shutdown")
        def shutdown_scheduler():
            self.scheduler.shutdown()
    
    def get_app(self):
        """Get FastAPI application instance"""
        return self.app


# ==================== Application Entry Point ====================
config = Config()
news_app = NewsApplication(config)
app = news_app.get_app()