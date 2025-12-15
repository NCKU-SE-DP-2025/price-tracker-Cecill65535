import unittest


class TestNewsCrawlerBase(unittest.TestCase):
    """
    NewsCrawlerBase 現在只是一個抽象介面 (Abstract Base Class)，
    沒有實際邏輯需要測試。
    所有的邏輯測試都已經移到具體的爬蟲測試 (test_udn_news_crawler.py) 中。
    """

    def test_interface_exists(self):
        # 只要確認測試檔案能執行即可，不做任何檢查
        pass


if __name__ == "__main__":
    unittest.main()
