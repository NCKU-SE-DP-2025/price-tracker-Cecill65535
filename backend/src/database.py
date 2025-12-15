from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import Config

# 1. 讀取設定
config = Config()

# 2. 建立資料庫引擎
engine = create_engine(config.DATABASE_URL, echo=True)

# 3. 建立 SessionLocal，這是 session 的 "工廠"
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. 建立 Base (從舊 main.py 的 line 21 搬過來)
Base = declarative_base()


# 5. 這是新的 "Dependency" (依賴項)，用來取代 DatabaseManager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
