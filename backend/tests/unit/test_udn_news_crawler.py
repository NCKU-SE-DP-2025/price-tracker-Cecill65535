import unittest
from unittest.mock import MagicMock, patch
from src.crawler.udn_crawler import UDNCrawler

class TestUDNCrawler(unittest.TestCase):
    def setUp(self):
        self.crawler = UDNCrawler()

    # 測試 1: 測試抓標題 (get_headline)
    @patch("src.crawler.udn_crawler.requests.get")
    def test_get_headline(self, mock_get):
        # === 1. 準備劇本 (Mock) ===
        # 我們假裝 UDN 回傳了這串 JSON 資料
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "lists": [
                {"title": "Fake News 1", "titleLink": "http://udn.com/news1"},
                {"title": "Fake News 2", "titleLink": "http://udn.com/news2"}
            ]
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # === 2. 執行測試 ===
        headlines = self.crawler.get_headline(search_term="test", page=1)

        # === 3. 檢查結果 ===
        self.assertEqual(len(headlines), 2) # 應該抓到 2 篇
        self.assertEqual(headlines[0].title, "Fake News 1")
        self.assertEqual(headlines[0].url, "http://udn.com/news1")

    # 測試 2: 測試解析內文 (parse)
    @patch("src.crawler.udn_crawler.requests.get")
    def test_parse(self, mock_get):
        # === 1. 準備劇本 (Mock) ===
        # 我們假裝 UDN 的網頁長這樣 (HTML)
        mock_response = MagicMock()
        mock_response.text = """
        <html>
            <h1 class="article-content__title">Big Event</h1>
            <time class="article-content__time">2024-01-01</time>
            <section class="article-content__editor">
                <p>First paragraph.</p>
                <p>Second paragraph.</p>
            </section>
        </html>
        """
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # === 2. 執行測試 ===
        news = self.crawler.parse("http://udn.com/some-news")

        # === 3. 檢查結果 ===
        self.assertEqual(news.title, "Big Event")
        self.assertEqual(news.time, "2024-01-01")
        # 檢查有沒有正確把兩個 <p> 接起來
        self.assertIn("First paragraph.", news.content)
        self.assertIn("Second paragraph.", news.content)

if __name__ == '__main__':
    unittest.main()