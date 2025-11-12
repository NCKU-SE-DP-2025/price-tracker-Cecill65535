# src/auth/router.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from src.database import get_db
from src.auth.schemas import UserAuthSchema
from src.auth.service import AuthService, UserRepository
from src.config import Config
from src.auth.dependencies import get_current_user, auth_service
from .models import User # 為了 read_users_me 的 response type

# 1. 建立一個 APIRouter
# 這會取代 @self.app
router = APIRouter(
    prefix="/users",  # 所有路徑都會自動加上 /users
    tags=["auth"]     # 在 API 文件中分類
)

# 2. 讀取設定 (為了 token)
config = Config()

# 3. 這是【註冊】路由 (重構版)
@router.post("/register", response_model_exclude={"hashed_password"}) 
def register(user: UserAuthSchema, db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    
    # 檢查用戶是否已存在 (這是一個好習慣)
    db_user = user_repo.get_user_by_username(user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
        
    hashed_password = auth_service.hash_password(user.password)
    new_user = user_repo.create_user(user.username, hashed_password)
    return new_user

# 4. 這是【登入】路由 (重構版)
@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = auth_service.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token = auth_service.create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=30)
    )
    return {"access_token": access_token, "token_type": "bearer"}

# 5. 這是【讀取使用者】路由 (重構版)
@router.get("/me", response_model_exclude={"hashed_password"})
def read_users_me(current_user: User = Depends(get_current_user)):
    # get_current_user 依賴項已經幫我們處理好一切
    return current_user