import json
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from typing import List, Dict, Optional


class UDNCrawler:
    """UDN 新聞爬蟲類別"""
    
    def __init__(self, openai_api_key: str):
        """
        初始化爬蟲
        
        :param openai_api_key: OpenAI API 金鑰
        """
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.base_url = "https://udn.com/api/more"
    
    def get_news_list(self, search_term: str, is_initial: bool = False) -> List[Dict]:
        """
        取得新聞列表
        
        :param search_term: 搜尋關鍵字
        :param is_initial: 是否為初始化（取得多頁資料）
        :return: 新聞列表
        """
        all_news_data = []
        
        if is_initial:
            # 初始化時取得多頁資料
            for page in range(1, 10):
                params = {
                    "page": page,
                    "id": f"search:{quote(search_term)}",
                    "channelId": 2,
                    "type": "searchword",
                }
                response = requests.get(self.base_url, params=params)
                all_news_data.extend(response.json()["lists"])
        else:
            # 一般情況只取第一頁
            params = {
                "page": 1,
                "id": f"search:{quote(search_term)}",
                "channelId": 2,
                "type": "searchword",
            }
            response = requests.get(self.base_url, params=params)
            all_news_data = response.json()["lists"]
        
        return all_news_data
    
    def extract_article_content(self, url: str) -> Optional[Dict]:
        """
        爬取文章完整內容
        
        :param url: 文章網址
        :return: 包含標題、時間、內容的字典，失敗則返回 None
        """
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 提取標題
            title_element = soup.find("h1", class_="article-content__title")
            if not title_element:
                return None
            title = title_element.text
            
            # 提取時間
            time_element = soup.find("time", class_="article-content__time")
            if not time_element:
                return None
            time = time_element.text
            
            # 提取內容段落
            content_section = soup.find("section", class_="article-content__editor")
            if not content_section:
                return None
            
            paragraphs = [
                p.text
                for p in content_section.find_all("p")
                if p.text.strip() != "" and "▪" not in p.text
            ]
            
            return {
                "url": url,
                "title": title,
                "time": time,
                "content": paragraphs,
            }
        except Exception as e:
            print(f"Error extracting article from {url}: {e}")
            return None
    
    def assess_relevance(self, title: str, topic: str = "民生用品的價格變化") -> str:
        """
        評估新聞標題與主題的關聯度
        
        :param title: 新聞標題
        :param topic: 主題描述
        :return: 'high', 'medium', 或 'low'
        """
        messages = [
            {
                "role": "system",
                "content": f"你是一個關聯度評估機器人，請評估新聞標題是否與「{topic}」相關，並給予'high'、'medium'、'low'評價。(僅需回答'high'、'medium'、'low'三個詞之一)",
            },
            {"role": "user", "content": title},
        ]
        
        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )
        
        return response.choices[0].message.content.strip()
    
    def generate_summary(self, content: str) -> Dict[str, str]:
        """
        生成新聞摘要（影響和原因）
        
        :param content: 新聞內容
        :return: 包含 '影響' 和 '原因' 的字典
        """
        messages = [
            {
                "role": "system",
                "content": "你是一個新聞摘要生成機器人，請統整新聞中提及的影響及主要原因 (影響、原因各50個字，請以json格式回答 {'影響': '...', '原因': '...'})",
            },
            {"role": "user", "content": content},
        ]
        
        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )
        
        result = response.choices[0].message.content
        return json.loads(result)
    
    def extract_keywords(self, user_input: str) -> str:
        """
        從使用者輸入中提取搜尋關鍵字
        
        :param user_input: 使用者輸入的文字
        :return: 提取的關鍵字
        """
        messages = [
            {
                "role": "system",
                "content": "你是一個關鍵字提取機器人，用戶將會輸入一段文字，表示其希望看見的新聞內容，請提取出用戶希望看見的關鍵字，請截取最重要的關鍵字即可，避免出現「新聞」、「資訊」等混淆搜尋引擎的字詞。(僅須回答關鍵字，若有多個關鍵字，請以空格分隔)",
            },
            {"role": "user", "content": user_input},
        ]
        
        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
        )
        
        return response.choices[0].message.content.strip()
    
    def crawl_and_process_news(
        self, 
        search_term: str, 
        is_initial: bool = False,
        filter_by_relevance: bool = True,
        relevance_threshold: str = "high"
    ) -> List[Dict]:
        """
        爬取並處理新聞（包含完整內容和摘要）
        
        :param search_term: 搜尋關鍵字
        :param is_initial: 是否為初始化
        :param filter_by_relevance: 是否過濾相關度
        :param relevance_threshold: 相關度閾值
        :return: 處理後的新聞列表
        """
        news_list = self.get_news_list(search_term, is_initial)
        processed_news = []
        
        for news in news_list:
            # 評估相關度
            if filter_by_relevance:
                relevance = self.assess_relevance(news["title"])
                if relevance != relevance_threshold:
                    continue
            
            # 爬取完整內容
            article = self.extract_article_content(news["titleLink"])
            if not article:
                continue
            
            # 生成摘要
            content_text = " ".join(article["content"])
            summary_result = self.generate_summary(content_text)
            
            article["summary"] = summary_result["影響"]
            article["reason"] = summary_result["原因"]
            article["content"] = content_text
            
            processed_news.append(article)
        
        return processed_news