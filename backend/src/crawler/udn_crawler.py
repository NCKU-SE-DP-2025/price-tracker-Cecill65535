# src/crawler/udn_crawler.py
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
from typing import List, Union, Tuple
from sqlalchemy.orm import Session

# 匯入作業提供的 Base 和 Models
from .crawler_base import NewsCrawlerBase, Headline, News
from .exceptions import FetchError, ParseError
from src.news.models import NewsArticle # 為了 save 方法

class UDNCrawler(NewsCrawlerBase):
    # 定義這個爬蟲專屬的網址
    news_website_url = "https://udn.com"
    news_website_news_child_urls = ["https://udn.com/news/story", "https://udn.com/api/more"]
    API_URL = "https://udn.com/api/more"

    def get_headline(self, search_term: str, page: Union[int, Tuple[int, int]]) -> List[Headline]:
        """
        實作取得標題列表的邏輯
        對應舊程式碼的 fetch_news_list
        """
        headlines = []
        
        # 處理 page 參數：如果是單一數字轉成 range，如果是 tuple 直接用
        if isinstance(page, int):
            page_range = range(page, page + 1)
        else:
            page_range = range(page[0], page[1] + 1)

        try:
            for p in page_range:
                params = {
                    "page": p,
                    "id": f"search:{quote(search_term)}",
                    "channelId": 2,
                    "type": "searchword",
                }
                response = requests.get(self.API_URL, params=params)
                response.raise_for_status()
                data = response.json()
                
                if "lists" in data:
                    for item in data["lists"]:
                        # 將 API 回傳的資料轉換成 Headline 物件
                        headlines.append(Headline(
                            title=item["title"],
                            url=item["titleLink"]
                        ))
            return headlines
            
        except Exception as e:
            raise FetchError(f"Failed to fetch headlines: {str(e)}")

    def parse(self, url: str) -> News:
        """
        實作解析內文的邏輯
        對應舊程式碼的 fetch_article_content
        """
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 1. 抓標題
            title_tag = soup.find("h1", class_="article-content__title")
            title = title_tag.text if title_tag else "No Title"
            
            # 2. 抓時間
            time_tag = soup.find("time", class_="article-content__time")
            time = time_tag.text if time_tag else "No Time"
            
            # 3. 抓內文 (記得用 "p" 標籤)
            content_section = soup.find("section", class_="article-content__editor")
            if not content_section:
                raise ParseError(f"Content section not found for url: {url}")

            paragraphs = [
                page.text.strip()
                for page in content_section.find_all("p")
                if page.text.strip() != "" and "▪" not in page.text
            ]
            content = "\n".join(paragraphs) # 將段落結合成一個字串

            # 回傳 Pydantic News 物件
            return News(
                title=title,
                url=url,
                time=time,
                content=content
            )
            
        except Exception as e:
            raise ParseError(f"Failed to parse article: {str(e)}")

    @staticmethod
    def save(news: News, db: Session | None):
        """
        實作存入資料庫的邏輯
        """
        if db is None:
            return

        # 檢查是否已存在 (避免重複)
        existing_article = db.query(NewsArticle).filter(NewsArticle.url == str(news.url)).first()
        if existing_article:
            return

        # 建立 SQLAlchemy Model 物件
        # 注意：這裡還沒有 summary 和 reason，因為那通常是 AI 生成的
        # 我們先存基本資料，或者給預設值
        article = NewsArticle(
            url=str(news.url),
            title=news.title,
            time=news.time,
            content=news.content,
            summary="", # 暫時留空，等待 AI 生成
            reason=""   # 暫時留空
        )
        
        db.add(article)
        db.commit()