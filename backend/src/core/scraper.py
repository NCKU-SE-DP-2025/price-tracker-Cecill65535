import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
class NewsScraper:
    BASE_URL = "https://udn.com/api/more"
    
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
        }

