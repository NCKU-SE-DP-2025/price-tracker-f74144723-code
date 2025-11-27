# 在 main.py 開頭加入
from udn_crawler import UDNCrawler

# 初始化爬蟲（在全域或適當位置）
crawler = UDNCrawler(openai_api_key="xxx")

# 重構後的 add_news 函數
def add_news(news_data):
    """
    將新聞加入資料庫
    
    :param news_data: 新聞資料
    """
    session = Session()
    session.add(NewsArticle(
        url=news_data["url"],
        title=news_data["title"],
        time=news_data["time"],
        content=news_data["content"],
        summary=news_data["summary"],
        reason=news_data["reason"],
    ))
    session.commit()
    session.close()


# 重構後的 get_news 函數
def get_news(is_initial=False):
    """
    取得並處理新聞
    
    :param is_initial: 是否為初始化
    """
    processed_news = crawler.crawl_and_process_news(
        search_term="價格",
        is_initial=is_initial,
        filter_by_relevance=True,
        relevance_threshold="high"
    )
    
    for news in processed_news:
        add_news(news)


# 重構後的 search_news endpoint
@app.post("/api/v1/news/search_news")
async def search_news(request: PromptRequest):
    """
    根據使用者輸入搜尋新聞
    """
    prompt = request.prompt
    
    # 提取關鍵字
    keywords = crawler.extract_keywords(prompt)
    
    # 取得新聞列表
    news_items = crawler.get_news_list(keywords, is_initial=False)
    
    news_list = []
    for news in news_items:
        article = crawler.extract_article_content(news["titleLink"])
        if article:
            article["id"] = next(_id_counter)
            news_list.append(article)
    
    return sorted(news_list, key=lambda x: x["time"], reverse=True)


# 重構後的 news_summary endpoint
@app.post("/api/v1/news/news_summary")
async def news_summary(
    payload: NewsSumaryRequestSchema, 
    u=Depends(authenticate_user_token)
):
    """
    生成新聞摘要
    """
    summary_result = crawler.generate_summary(payload.content)
    
    return {
        "summary": summary_result["影響"],
        "reason": summary_result["原因"]
    }