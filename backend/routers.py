from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.database import get_db, User
from src.schemas import *
from src.services import *
from src.dependencies import get_current_user
from src.config import settings

# ==================== User Routes ====================
user_router = APIRouter(prefix="/api/v1/users", tags=["users"])

@user_router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    
    token = auth_service.create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": token, "token_type": "bearer"}

@user_router.post("/register", response_model=UserResponse)
async def register(user_data: UserAuthSchema, db: Session = Depends(get_db)):
    user_service = UserService(db, auth_service)
    user = user_service.create_user(user_data.username, user_data.password)
    return {"username": user.username}

@user_router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username}

# ==================== News Routes ====================
news_router = APIRouter(prefix="/api/v1/news", tags=["news"])

@news_router.get("/news")
async def get_news(db: Session = Depends(get_db)):
    news_service = NewsService(db, ai_service)
    return news_service.get_all_news()

@news_router.get("/user_news")
async def get_user_news(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    news_service = NewsService(db, ai_service)
    return news_service.get_all_news(user_id=current_user.id)

@news_router.post("/search_news")
async def search_news(request: PromptRequest, db: Session = Depends(get_db)):
    news_service = NewsService(db, ai_service)
    return news_service.search_news(request.prompt)

@news_router.post("/news_summary")
async def news_summary(payload: NewsSummaryRequest, current_user: User = Depends(get_current_user)):
    summary_data = ai_service.generate_summary(payload.content)
    return {"summary": summary_data["影響"], "reason": summary_data["原因"]}

@news_router.post("/{id}/upvote")
async def upvote(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    news_service = NewsService(db, ai_service)
    return {"message": news_service.toggle_upvote(id, current_user.id)}

# ==================== Price Routes ====================
price_router = APIRouter(prefix="/api/v1/prices", tags=["prices"])

@price_router.get("/necessities-price")
async def get_prices(category: Optional[str] = Query(None), commodity: Optional[str] = Query(None)):
    return ExternalAPIService.get_necessities_prices(category, commodity)