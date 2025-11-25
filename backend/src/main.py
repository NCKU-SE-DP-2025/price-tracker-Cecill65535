from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk
from apscheduler.schedulers.background import BackgroundScheduler

# 匯入 階段 1 的檔案
from src.database import Base, engine, get_db
from src.config import Config

# 匯入 階段 3 的檔案 (為了 startup)
from src.core.ai import AIService
from src.core.scraper import NewsScraper
from src.news.service import NewsService, NewsRepository

# 匯入 階段 4 的 Router 檔案
from src.auth.router import router as auth_router
from src.news.router import router as news_router
from src.prices.router import router as prices_router

# 1. 建立資料庫表格
# (註：在生產環境中，你應該使用 Alembic 來管理)
Base.metadata.create_all(bind=engine)

# 2. 讀取設定
config = Config()

# 3. 建立 FastAPI App 實例
app = FastAPI()

# 4. 設定 Sentry (來自舊的 _setup_sentry)
sentry_sdk.init(
    dsn=config.SENTRY_DSN,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

# 5. 設定 Middleware (來自舊的 _setup_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 6. 【關鍵】載入 (Include) 所有的 Routers
#    這會把 auth, news, prices 的 API 路徑全部加到 app 中
app.include_router(auth_router, prefix="/api/v1")
app.include_router(news_router, prefix="/api/v1")
app.include_router(prices_router, prefix="/api/v1")


# 7. 設定背景任務 (來自舊的 _setup_events)
scheduler = BackgroundScheduler()
# 建立需要的 Service 實例 (給背景任務用)
ai_service_instance = AIService(config.OPENAI_API_KEY)
news_service_instance = NewsService(ai_service_instance, NewsScraper())

@app.on_event("startup")
def start_scheduler():
    # db = next(get_db()) # 使用我們新的 get_db()
    # news_repo = NewsRepository(db)
    
    # if news_repo.count_articles() == 0:
    #     print("資料庫為空，開始抓取初始新聞... (此功能已暫時停用)")
    #     # news_service_instance.fetch_and_process_initial_news(db, is_initial=True)
    
    # db.close() # 記得關閉
    
    # 我們也暫時停掉背景任務
    # scheduler.add_job(
    #     lambda: news_service_instance.fetch_and_process_initial_news(
    #         next(get_db()) # 每次都拿一個新的 db session
    #     ),
    #     "interval",
    #     minutes=100
    # )
    # scheduler.start()
    print("FastAPI 啟動完成！(已跳過啟動爬蟲任務)") # 新增一行提示

@app.on_event("shutdown")
def shutdown_scheduler():
    # scheduler.shutdown() # 因為沒啟動，所以也關掉
    print("FastAPI 關閉中...")