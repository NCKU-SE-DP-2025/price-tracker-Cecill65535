from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk
from apscheduler.schedulers.background import BackgroundScheduler
import sys

# 匯入 階段 1 的檔案
from src.database import Base, engine, get_db
from src.config import Config

# 匯入 階段 3 的檔案 (為了 startup)
from src.core.ai import AIService
from src.core.scraper import NewsScraper  # 使用 core 的可被測試 patch 的爬蟲
from src.news.service import NewsService, NewsRepository

# 匯入 階段 4 的 Router 檔案
from src.auth.router import router as auth_router
from src.news.router import router as news_router
from src.prices.router import router as prices_router

# 1. 建立資料庫表格
Base.metadata.create_all(bind=engine)

# 2. 讀取設定
config = Config()

# 3. 建立 FastAPI App 實例
app = FastAPI()

# 4. 設定 Sentry
sentry_sdk.init(
    dsn=config.SENTRY_DSN,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

# 5. 設定 Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 6. 載入所有的 Routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(news_router, prefix="/api/v1")
app.include_router(prices_router, prefix="/api/v1")


# 7. 設定背景任務與 Service
scheduler = BackgroundScheduler()
ai_service_instance = AIService(config.OPENAI_API_KEY)
# 使用 NewsScraper (雖然名字是舊的，但 Docker 裡的邏輯是新的)
news_service_instance = NewsService(ai_service_instance, NewsScraper())


@app.on_event("startup")
def start_scheduler():
    # 如果在 pytest 環境下執行，跳過啟動爬蟲與排程（避免污染測試 DB 與進行網路呼叫）
    if "pytest" in sys.modules:
        print("[Startup] Detected pytest - skipping initial fetch and scheduler.")
        return

    print("[System] Startup: 初始化爬蟲任務...")

    # 建立一個臨時的 DB Session 來做檢查
    db = next(get_db())
    try:
        news_repo = NewsRepository(db)
        if news_repo.count_articles() == 0:
            print("[Info] 資料庫為空，開始執行「初始新聞抓取」...")
            news_service_instance.fetch_and_process_initial_news(db, is_initial=True)
            print("[Success] 初始新聞抓取完成！")
        else:
            print("[Info] 資料庫已有資料，跳過初始抓取。")
    except Exception as e:
        print(f"[Error] 初始爬蟲失敗 (跳過，不影響伺服器啟動): {e}")
    finally:
        db.close()

    # 啟動排程（只有非測試環境會到這）
    try:

        def scheduled_news_job():
            print("[Scheduler] 排程任務啟動：開始背景抓取新聞...")
            job_db = next(get_db())
            try:
                news_service_instance.fetch_and_process_initial_news(
                    job_db, is_initial=False
                )
                print("[Success] 排程新聞更新完成。")
            except Exception as e:
                print(f"[Error] 排程任務執行錯誤: {e}")
            finally:
                job_db.close()

        scheduler.add_job(scheduled_news_job, "interval", minutes=100)
        scheduler.start()
        print("[System] 背景排程器 (Scheduler) 已啟動。")
    except Exception as e:
        print(f"[Error] 排程器啟動失敗: {e}")

    print("[System] FastAPI 啟動流程結束，服務準備就緒。")


@app.on_event("shutdown")
def shutdown_scheduler():
    print("[System] FastAPI 正在關閉...")
    try:
        scheduler.shutdown()
        print("[System] 排程器已安全關閉。")
    except Exception as e:
        print(f"[Error] 關閉排程器時發生錯誤: {e}")


def get_scraper():
    return NewsScraper()
