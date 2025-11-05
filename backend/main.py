import json
import sentry_sdk
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi.middleware.cors import CORSMiddleware
import itertools
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session, sessionmaker
from typing import List, Optional
import requests
from fastapi import APIRouter, HTTPException, Query, Depends, status, FastAPI
import os
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, AnyHttpUrl
from sqlalchemy import (Column, ForeignKey, Integer, String, Table, Text, create_engine)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from urllib.parse import quote
from bs4 import BeautifulSoup
from openai import OpenAI

# ==================== Database Models ====================
Base = declarative_base()

user_news_association_table = Table(
    "user_news_upvotes", Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("news_articles_id", Integer, ForeignKey("news_articles.id"), primary_key=True),
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    upvoted_news = relationship(
        "NewsArticle", secondary=user_news_association_table, back_populates="upvoted_by_users",
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
class AppConfig:
    DATABASE_URL = "sqlite:///news_database.db"
    SENTRY_DSN = "https://4001ffe917ccb261aa0e0c34026dc343@o4505702629834752.ingest.us.sentry.io/4507694792704000"
    JWT_SECRET_KEY = '1892dhianiandowqd0n'
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    OPENAI_API_KEY = "xxx"
    CORS_ORIGINS = ["http://localhost:8080"]

# ==================== Database Setup ====================
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
        self.model = "gpt-3.5-turbo"
    
    def generate_summary(self, content: str) -> dict:
        """Generate summary with impact and reason from content"""
        messages = [
            {
                "role": "system",
                "content": "你是一個新聞摘要生成機器人,請統整新聞中提及的影響及主要原因 (影響、原因各50個字,請以json格式回答 {'影響': '...', '原因': '...'})",
            },
            {"role": "user", "content": content},
        ]
        
        completion = self.client.chat.completions.create(
            model=self.model,
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
            model=self.model,
            messages=messages,
        )
        return completion.choices[0].message.content
    
    def assess_relevance(self, title: str) -> str:
        """Assess if news title is relevant to price changes"""
        messages = [
            {
                "role": "system",
                "content": "你是一個關聯度評估機器人,請評估新聞標題是否與「民生用品的價格變化」相關,並給予'high'、'medium'、'low'評價。(僅需回答'high'、'medium'、'low'三個詞之一)",
            },
            {"role": "user", "content": title},
        ]
        
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return completion.choices[0].message.content

# ==================== News Scraper ====================
class NewsScraperService:
    UDN_API_URL = "https://udn.com/api/more"
    
    @staticmethod
    def fetch_news_metadata(search_term: str, is_initial: bool = False) -> list:
        """Fetch news metadata from UDN API"""
        all_news_data = []
        
        if is_initial:
            for page in range(1, 10):
                params = {
                    "page": page,
                    "id": f"search:{quote(search_term)}",
                    "channelId": 2,
                    "type": "searchword",
                }
                response = requests.get(NewsScraperService.UDN_API_URL, params=params)
                all_news_data.extend(response.json()["lists"])
        else:
            params = {
                "page": 1,
                "id": f"search:{quote(search_term)}",
                "channelId": 2,
                "type": "searchword",
            }
            response = requests.get(NewsScraperService.UDN_API_URL, params=params)
            all_news_data = response.json()["lists"]
        
        return all_news_data
    
    @staticmethod
    def scrape_article_details(url: str) -> dict:
        """Scrape detailed article content from URL"""
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        
        title = soup.find("h1", class_="article-content__title").text
        time = soup.find("time", class_="article-content__time").text
        content_section = soup.find("section", class_="article-content__editor")
        paragraphs = [
            p.text for p in content_section.find_all("p")
            if p.text.strip() != "" and "▪" not in p.text
        ]
        
        return {
            "url": url,
            "title": title,
            "time": time,
            "content": paragraphs,
        }

# ==================== News Service ====================
class NewsService:
    def __init__(self, db_session: Session, ai_service: AIService):
        self.db = db_session
        self.ai_service = ai_service
        self.scraper = NewsScraperService()
        self.id_counter = itertools.count(start=1000000)
    
    def add_news_to_db(self, news_data: dict):
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
    
    def fetch_and_process_news(self, is_initial: bool = False):
        """Fetch news from UDN and process relevant articles"""
        news_items = self.scraper.fetch_news_metadata("價格", is_initial=is_initial)
        
        for news in news_items:
            title = news["title"]
            relevance = self.ai_service.assess_relevance(title)
            
            if relevance == "high":
                try:
                    detailed_news = self.scraper.scrape_article_details(news["titleLink"])
                    summary_data = self.ai_service.generate_summary(" ".join(detailed_news["content"]))
                    
                    detailed_news["summary"] = summary_data["影響"]
                    detailed_news["reason"] = summary_data["原因"]
                    
                    self.add_news_to_db(detailed_news)
                except Exception as e:
                    print(f"Error processing news: {e}")
    
    def search_news(self, prompt: str) -> list:
        """Search for news based on user prompt"""
        keywords = self.ai_service.extract_keywords(prompt)
        news_items = self.scraper.fetch_news_metadata(keywords, is_initial=False)
        news_list = []
        
        for news in news_items:
            try:
                detailed_news = self.scraper.scrape_article_details(news["titleLink"])
                detailed_news["content"] = " ".join(detailed_news["content"])
                detailed_news["id"] = next(self.id_counter)
                news_list.append(detailed_news)
            except Exception as e:
                print(f"Error scraping article: {e}")
        
        return sorted(news_list, key=lambda x: x["time"], reverse=True)
    
    def get_all_news(self, user_id: Optional[int] = None) -> list:
        """Get all news articles with upvote information"""
        news = self.db.query(NewsArticle).order_by(NewsArticle.time.desc()).all()
        result = []
        
        for article in news:
            upvotes, upvoted = self.get_article_upvote_details(article.id, user_id)
            result.append({
                **article.__dict__,
                "upvotes": upvotes,
                "is_upvoted": upvoted
            })
        
        return result
    
    def get_article_upvote_details(self, article_id: int, user_id: Optional[int]) -> tuple:
        """Get upvote count and whether user has upvoted"""
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
                .first() is not None
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
                news_articles_id=article_id,
                user_id=user_id
            )
            self.db.execute(insert_stmt)
            self.db.commit()
            return "Article upvoted"
    
    def news_exists(self, news_id: int) -> bool:
        """Check if news article exists"""
        return self.db.query(NewsArticle).filter_by(id=news_id).first() is not None

# ==================== Authentication Service ====================
class AuthService:
    def __init__(self, secret_key: str, algorithm: str):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def hash_password(self, password: str) -> str:
        """Hash a password"""
        return self.pwd_context.hash(password)
    
    def authenticate_user(self, db: Session, username: str, password: str):
        """Authenticate user with username and password"""
        user = db.query(User).filter(User.username == username).first()
        if not user or not self.verify_password(password, user.hashed_password):
            return None
        return user
    
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
    
    def decode_token(self, token: str):
        """Decode JWT token"""
        return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

# ==================== User Service ====================
class UserService:
    def __init__(self, db_session: Session, auth_service: AuthService):
        self.db = db_session
        self.auth_service = auth_service
    
    def create_user(self, username: str, password: str) -> User:
        """Create a new user"""
        hashed_password = self.auth_service.hash_password(password)
        user = User(username=username, hashed_password=hashed_password)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self.db.query(User).filter(User.username == username).first()
    
    def get_user_by_token(self, token: str) -> Optional[User]:
        """Get user from JWT token"""
        try:
            payload = self.auth_service.decode_token(token)
            username = payload.get("sub")
            return self.get_user_by_username(username)
        except JWTError:
            return None

# ==================== External API Service ====================
class ExternalAPIService:
    @staticmethod
    def get_necessities_prices(category: Optional[str] = None, commodity: Optional[str] = None):
        """Fetch necessities prices from external API"""
        params = {}
        if category:
            params["CategoryName"] = category
        if commodity:
            params["Name"] = commodity
        
        response = requests.get(
            "https://opendata.ey.gov.tw/api/ConsumerProtection/NecessitiesPrice",
            params=params
        )
        return response.json()

# ==================== Application Setup ====================
config = AppConfig()
db_manager = DatabaseManager(config.DATABASE_URL)
auth_service = AuthService(config.JWT_SECRET_KEY, config.JWT_ALGORITHM)
ai_service = AIService(config.OPENAI_API_KEY)

# Initialize Sentry
sentry_sdk.init(
    dsn=config.SENTRY_DSN,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

# Initialize FastAPI app
app = FastAPI()
background_scheduler = BackgroundScheduler()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Dependency Functions ====================
def get_db():
    return next(db_manager.get_session())

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    user_service = UserService(db, auth_service)
    user = user_service.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return user

# ==================== Scheduler Functions ====================
def scheduled_news_fetch():
    db = next(db_manager.get_session())
    try:
        news_service = NewsService(db, ai_service)
        news_service.fetch_and_process_news(is_initial=False)
    finally:
        db.close()

@app.on_event("startup")
def start_scheduler():
    db = next(db_manager.get_session())
    try:
        if db.query(NewsArticle).count() == 0:
            news_service = NewsService(db, ai_service)
            news_service.fetch_and_process_news(is_initial=True)
    finally:
        db.close()
    
    background_scheduler.add_job(scheduled_news_fetch, "interval", minutes=100)
    background_scheduler.start()

@app.on_event("shutdown")
def shutdown_scheduler():
    background_scheduler.shutdown()

# ==================== API Routes ====================

# User Authentication Routes
@app.post("/api/v1/users/login")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = auth_service.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    access_token = auth_service.create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/v1/users/register")
def create_user(user_data: UserAuthSchema, db: Session = Depends(get_db)):
    user_service = UserService(db, auth_service)
    return user_service.create_user(user_data.username, user_data.password)

@app.get("/api/v1/users/me")
def get_users_me(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username}

# News Routes
@app.get("/api/v1/news/news")
def get_news(db: Session = Depends(get_db)):
    news_service = NewsService(db, ai_service)
    return news_service.get_all_news()

@app.get("/api/v1/news/user_news")
def get_user_news(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    news_service = NewsService(db, ai_service)
    return news_service.get_all_news(user_id=current_user.id)

@app.post("/api/v1/news/search_news")
async def search_news(request: PromptRequest, db: Session = Depends(get_db)):
    news_service = NewsService(db, ai_service)
    return news_service.search_news(request.prompt)

@app.post("/api/v1/news/news_summary")
async def news_summary(
    payload: NewsSummaryRequestSchema,
    current_user: User = Depends(get_current_user)
):
    summary_data = ai_service.generate_summary(payload.content)
    return {
        "summary": summary_data["影響"],
        "reason": summary_data["原因"]
    }

@app.post("/api/v1/news/{id}/upvote")
def upvote_article(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    news_service = NewsService(db, ai_service)
    message = news_service.toggle_upvote(id, current_user.id)
    return {"message": message}

# External API Routes
@app.get("/api/v1/prices/necessities-price")
def get_necessities_prices(
    category: Optional[str] = Query(None),
    commodity: Optional[str] = Query(None)
):
    return ExternalAPIService.get_necessities_prices(category, commodity)