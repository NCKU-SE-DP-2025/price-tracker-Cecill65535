import unittest
from unittest.mock import patch
from pydantic import AnyHttpUrl
from src.crawler.crawler_base import NewsCrawlerBase, News, Headline
from src.crawler.exceptions import DomainMismatchException


# --- 替身爬蟲 (Mock) ---
# 因為 BaseCrawler 是抽象的，不能直接跑，所以我們做一個假的替身來測試它
class MockNewsCrawler(NewsCrawlerBase):
    news_website_url = "https://www.example.com"
    news_website_news_child_urls = ["https://news.example.com"]

    def get_headline(self, search_term: str, page: int | tuple[int, int]):
        return [Headline(title="Test Article", url="https://www.example.com/article")]

    def parse(self, url: AnyHttpUrl | str):
        return News(
            title="Test Article",
            url=url,
            time="2023-09-08T00:00:00",
            content="This is the content of the article.",
        )

    @staticmethod
    def save(news: News, db=None):
        return True


# --- 測試案例 ---
class TestNewsCrawlerBase(unittest.TestCase):

    def setUp(self):
        self.crawler = MockNewsCrawler()

    def test_is_valid_url_valid(self):
        # 測試：正確的網址應該回傳 True
        valid_url = "https://www.example.com/article"
        self.assertTrue(self.crawler._is_valid_url(valid_url))

    def test_is_valid_url_invalid(self):
        # 測試：錯誤的網址應該回傳 False
        invalid_url = "https://www.invalid.com/article"
        self.assertFalse(self.crawler._is_valid_url(invalid_url))

    def test_validate_and_parse_raises_error(self):
        # 測試：validate_and_parse 遇到錯的網址應該報錯
        invalid_url = "https://www.invalid.com/article"
        with self.assertRaises(DomainMismatchException):
            self.crawler.validate_and_parse(invalid_url)


if __name__ == "__main__":
    unittest.main()
