class CrawlerError(Exception):
    """Base exception for crawler errors"""
    pass

class DomainMismatchException(CrawlerError):
    """Raised when the URL does not match the expected domain"""
    def __init__(self, url: str):
        super().__init__(f"The URL {url} does not belong to the expected domain.")

class FetchError(CrawlerError):
    """Raised when fetching data fails"""
    pass

class ParseError(CrawlerError):
    """Raised when parsing content fails"""
    pass