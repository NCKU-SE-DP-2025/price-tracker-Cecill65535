import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
from typing import List, Optional
from datetime import datetime


# 定義一個簡單的資料結構 (DTO)，讓 Service 可以用 .title 存取
class NewsData:
    def __init__(
        self,
        title: str,
        url: str,
        time: Optional[str] = None,
        content: Optional[str] = None,
    ):
        self.title = title
        self.url = url
        self.time = time
        self.content = content


class NewsScraper:
    BASE_URL = "https://udn.com/api/more"
<<<<<<< HEAD

    def get_headline(self, search_term: str, page: int = 1) -> List[NewsData]:
        """
        根據關鍵字搜尋新聞列表
        """
        all_news = []
        params = {
            "page": page,
            "id": f"search:{quote(search_term)}",
            "channelId": 2,
            "type": "searchword",
=======
    
    @staticmethod
    def fetch_news_list(search_term: str, is_initial: bool = False) -> list:
        """Fetch news list from UDN API"""
        all_news_data = []
        
        if is_initial:
            for page in range(1, 10):
                params = {
                    "page": page,
                    "id": f"search:{quote(search_term)}",
                    "channelId": 2,
                    "type": "searchword",
                }
                response = requests.get(NewsScraper.BASE_URL, params=params)
                all_news_data.extend(response.json()["lists"])
        else:
            params = {
                "page": 1,
                "id": f"search:{quote(search_term)}",
                "channelId": 2,
                "type": "searchword",
            }
            response = requests.get(NewsScraper.BASE_URL, params=params)
            all_news_data = response.json()["lists"]
        
        return all_news_data
    
    @staticmethod
    def fetch_article_content(url: str) -> dict:
        """Fetch detailed article content from URL"""
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        
        title = soup.find("h1", class_="article-content__title").text
        time = soup.find("time", class_="article-content__time").text
        content_section = soup.find("section", class_="article-content__editor")
        
        paragraphs = [
            page.text
            for page in content_section.find_all("p")
            if page.text.strip() != "" and "▪" not in page.text
        ]
        
        return {
            "url": url,
            "title": title,
            "time": time,
            "content": paragraphs,
>>>>>>> dec8e24dce679b9468ba0f1b894422b452b9f266
        }

        try:
            # 直接請求，讓 requests 處理連線問題
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            if "lists" in data:
                for item in data["lists"]:
                    # 轉換成物件格式
                    news_item = NewsData(
                        title=item.get("title", "No Title"),
                        url=item.get("titleLink", ""),
                    )
                    all_news.append(news_item)
        except Exception as e:
            print(f"[Scraper Error] Get headline failed: {e}")

        return all_news

    def parse(self, url: str) -> NewsData:
        """
        解析單篇新聞內文
        """
        try:
            # 移除所有多餘的網址檢查，直接請求
            response = requests.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # 1. 抓標題
            title_tag = soup.find("h1", class_="article-content__title")
            title = title_tag.text.strip() if title_tag else "Unknown Title"

            # 2. 抓時間
            time_tag = soup.find("time", class_="article-content__time")
            # 抓不到就用現在時間當備案
            news_time = (
                time_tag.text.strip()
                if time_tag
                else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            # 3. 抓內文
            content_section = soup.find("section", class_="article-content__editor")
            if not content_section:
                # 這裡丟出錯誤是正常的，讓 Service 去過濾掉非新聞格式的網頁
                raise ValueError("Content section not found")

            paragraphs = [
                p.text.strip()
                for p in content_section.find_all("p")
                if p.text.strip() and "▪" not in p.text
            ]
            content = "\n".join(paragraphs)

            return NewsData(title=title, url=url, time=news_time, content=content)

        except Exception as e:
            # 將錯誤往上拋，讓 Service 的 Log 紀錄
            raise ValueError(f"Failed to parse article: {e}")
