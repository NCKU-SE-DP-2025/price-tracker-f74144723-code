import json
import itertools
import requests
from typing import Optional
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import quote
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session
from openai import OpenAI

from src.config import settings
from src.database import User, NewsArticle, user_news_association_table

# ==================== Auth Service ====================
class AuthService:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    def verify_password(self, plain: str, hashed: str) -> bool:
        return self.pwd_context.verify(plain, hashed)
    
    def hash_password(self, password: str) -> str:
        return self.pwd_context.hash(password)
    
    def authenticate_user(self, db: Session, username: str, password: str):
        user = db.query(User).filter(User.username == username).first()
        if not user or not self.verify_password(password, user.hashed_password):
            return None
        return user
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    def decode_token(self, token: str):
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

# ==================== User Service ====================
class UserService:
    def __init__(self, db: Session, auth_service: AuthService):
        self.db = db
        self.auth = auth_service
    
    def create_user(self, username: str, password: str) -> User:
        hashed = self.auth.hash_password(password)
        user = User(username=username, hashed_password=hashed)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def get_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()
    
    def get_by_token(self, token: str) -> Optional[User]:
        try:
            payload = self.auth.decode_token(token)
            return self.get_by_username(payload.get("sub"))
        except JWTError:
            return None

# ==================== AI Service ====================
class AIService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-3.5-turbo"
    
    def generate_summary(self, content: str) -> dict:
        messages = [
            {"role": "system", "content": "你是一個新聞摘要生成機器人,請統整新聞中提及的影響及主要原因 (影響、原因各50個字,請以json格式回答 {'影響': '...', '原因': '...'})"},
            {"role": "user", "content": content}
        ]
        completion = self.client.chat.completions.create(model=self.model, messages=messages)
        return json.loads(completion.choices[0].message.content)
    
    def extract_keywords(self, prompt: str) -> str:
        messages = [
            {"role": "system", "content": "你是一個關鍵字提取機器人,用戶將會輸入一段文字,表示其希望看見的新聞內容,請提取出用戶希望看見的關鍵字,請截取最重要的關鍵字即可,避免出現「新聞」、「資訊」等混淆搜尋引擎的字詞。(僅須回答關鍵字,若有多個關鍵字,請以空格分隔)"},
            {"role": "user", "content": prompt}
        ]
        completion = self.client.chat.completions.create(model=self.model, messages=messages)
        return completion.choices[0].message.content
    
    def assess_relevance(self, title: str) -> str:
        messages = [
            {"role": "system", "content": "你是一個關聯度評估機器人,請評估新聞標題是否與「民生用品的價格變化」相關,並給予'high'、'medium'、'low'評價。(僅需回答'high'、'medium'、'low'三個詞之一)"},
            {"role": "user", "content": title}
        ]
        completion = self.client.chat.completions.create(model=self.model, messages=messages)
        return completion.choices[0].message.content

# ==================== News Scraper ====================
class NewsScraperService:
    UDN_API_URL = "https://udn.com/api/more"
    
    @staticmethod
    def fetch_news_metadata(search_term: str, is_initial: bool = False) -> list:
        all_news = []
        pages = range(1, 10) if is_initial else [1]
        
        for page in pages:
            params = {
                "page": page,
                "id": f"search:{quote(search_term)}",
                "channelId": 2,
                "type": "searchword",
            }
            response = requests.get(NewsScraperService.UDN_API_URL, params=params)
            all_news.extend(response.json()["lists"])
        
        return all_news
    
    @staticmethod
    def scrape_article_details(url: str) -> dict:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        
        title = soup.find("h1", class_="article-content__title").text
        time = soup.find("time", class_="article-content__time").text
        content_section = soup.find("section", class_="article-content__editor")
        paragraphs = [p.text for p in content_section.find_all("p") if p.text.strip() and "▪" not in p.text]
        
        return {"url": url, "title": title, "time": time, "content": paragraphs}

# ==================== News Service ====================
class NewsService:
    def __init__(self, db: Session, ai_service: AIService):
        self.db = db
        self.ai = ai_service
        self.scraper = NewsScraperService()
        self.id_counter = itertools.count(start=1000000)
    
    def add_news_to_db(self, news_data: dict):
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
        news_items = self.scraper.fetch_news_metadata("價格", is_initial=is_initial)
        
        for news in news_items:
            if self.ai.assess_relevance(news["title"]) == "high":
                try:
                    detailed = self.scraper.scrape_article_details(news["titleLink"])
                    summary = self.ai.generate_summary(" ".join(detailed["content"]))
                    detailed["summary"] = summary["影響"]
                    detailed["reason"] = summary["原因"]
                    self.add_news_to_db(detailed)
                except Exception as e:
                    print(f"Error: {e}")
    
    def search_news(self, prompt: str) -> list:
        keywords = self.ai.extract_keywords(prompt)
        news_items = self.scraper.fetch_news_metadata(keywords, is_initial=False)
        
        news_list = []
        for news in news_items:
            try:
                detailed = self.scraper.scrape_article_details(news["titleLink"])
                detailed["content"] = " ".join(detailed["content"])
                detailed["id"] = next(self.id_counter)
                news_list.append(detailed)
            except Exception as e:
                print(f"Error: {e}")
        
        return sorted(news_list, key=lambda x: x["time"], reverse=True)
    
    def get_all_news(self, user_id: Optional[int] = None) -> list:
        articles = self.db.query(NewsArticle).order_by(NewsArticle.time.desc()).all()
        result = []
        for article in articles:
            upvotes, upvoted = self.get_upvote_details(article.id, user_id)
            result.append({**article.__dict__, "upvotes": upvotes, "is_upvoted": upvoted})
        return result
    
    def get_upvote_details(self, article_id: int, user_id: Optional[int]) -> tuple:
        count = self.db.query(user_news_association_table).filter_by(news_articles_id=article_id).count()
        voted = False
        if user_id:
            voted = self.db.query(user_news_association_table).filter_by(
                news_articles_id=article_id, user_id=user_id
            ).first() is not None
        return count, voted
    
    def toggle_upvote(self, article_id: int, user_id: int) -> str:
        existing = self.db.execute(
            select(user_news_association_table).where(
                user_news_association_table.c.news_articles_id == article_id,
                user_news_association_table.c.user_id == user_id,
            )
        ).scalar()
        
        if existing:
            self.db.execute(delete(user_news_association_table).where(
                user_news_association_table.c.news_articles_id == article_id,
                user_news_association_table.c.user_id == user_id,
            ))
            self.db.commit()
            return "Upvote removed"
        else:
            self.db.execute(insert(user_news_association_table).values(
                news_articles_id=article_id, user_id=user_id
            ))
            self.db.commit()
            return "Article upvoted"

# ==================== External API Service ====================
class ExternalAPIService:
    @staticmethod
    def get_necessities_prices(category: Optional[str] = None, commodity: Optional[str] = None):
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

# Service Instances
auth_service = AuthService()
ai_service = AIService()