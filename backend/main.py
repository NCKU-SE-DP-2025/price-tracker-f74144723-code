import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from src.config import settings
from src.database import db_manager, NewsArticle
from src.services import NewsService, ai_service
from src.routers import user_router, news_router, price_router

# Sentry
sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=1.0, profiles_sample_rate=1.0)

# FastAPI App
app = FastAPI(title="News Price Tracker API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(user_router)
app.include_router(news_router)
app.include_router(price_router)

# Scheduler
scheduler = BackgroundScheduler()

def scheduled_news_fetch():
    db = next(db_manager.get_session())
    try:
        NewsService(db, ai_service).fetch_and_process_news(is_initial=False)
    finally:
        db.close()

@app.on_event("startup")
async def startup():
    # Initial data load
    db = next(db_manager.get_session())
    try:
        if db.query(NewsArticle).count() == 0:
            NewsService(db, ai_service).fetch_and_process_news(is_initial=True)
    finally:
        db.close()
    
    # Start scheduler
    scheduler.add_job(scheduled_news_fetch, "interval", minutes=100)
    scheduler.start()

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()

@app.get("/")
async def root():
    return {"message": "News Price Tracker API", "version": "1.0.0"}