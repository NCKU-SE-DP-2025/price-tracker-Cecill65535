# src/auth/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError

# 匯入我們在 階段 1, 3 建立的檔案
from src.database import get_db
from src.config import Config
from src.auth.service import AuthService, UserRepository

# 1. 讀取設定
config = Config()

# 2. 建立 AuthService 實例 (取代 self.auth_service)
auth_service = AuthService(config.JWT_SECRET, config.JWT_ALGORITHM)

# 3. 建立 OAuth2 方案 (取代 self.auth_service.oauth2_scheme)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")

def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
):
    """
    Dependency to get current authenticated user
    (這是從 _get_current_user 重構來的)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = auth_service.decode_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user_repo = UserRepository(db)
    user = user_repo.get_user_by_username(username)
    if user is None:
        raise credentials_exception
    return user