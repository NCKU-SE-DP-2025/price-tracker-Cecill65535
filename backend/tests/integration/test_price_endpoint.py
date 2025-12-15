import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from src.main import app

client = TestClient(app)


@pytest.fixture
def mock_necessities_data():
    return [
        {
            "類別": "鮮乳",
            "編號": 1,
            "產品名稱": "統一瑞穗高優質鮮乳",
            "規格": "1858ml/瓶",
            "統計值": "144,143,143,143,143,0,0,145,145,146,146",
            "時間起點": "2015-03-01",
            "時間終點": "2024-08-01",
        },
        {
            "類別": "鮮乳",
            "編號": 2,
            "產品名稱": "味全林鳳營鮮乳",
            "規格": "1857ml/瓶",
            "統計值": "147,136,136,148,146,147,156,147,142,139",
            "時間起點": "2015-03-01",
            "時間終點": "2024-08-01",
        },
    ]


# 修改說明: 將 Mock 目標改為 src.prices.router.requests.get
@patch("src.prices.router.requests.get")
def test_get_necessities_prices(mock_get, mock_necessities_data):
    mock_response = mock_get.return_value
    mock_response.status_code = 200
    mock_response.json.return_value = mock_necessities_data

    response = client.get("/api/v1/prices/necessities-price")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["類別"] == "鮮乳"
    assert data[0]["產品名稱"] == "統一瑞穗高優質鮮乳"
    assert data[1]["產品名稱"] == "味全林鳳營鮮乳"


# 修改說明: 將 Mock 目標改為 src.prices.router.requests.get
@patch("src.prices.router.requests.get")
def test_get_necessities_prices_with_query(mock_get, mock_necessities_data):
    mock_response = mock_get.return_value
    mock_response.status_code = 200
    mock_response.json.return_value = mock_necessities_data

    # 這裡加入 params 參數以符合測試邏輯
    response = client.get(
        "/api/v1/prices/necessities-price",
        params={"category": "鮮乳", "commodity": "統一瑞穗高優質鮮乳"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["類別"] == "鮮乳"
    assert data[0]["產品名稱"] == "統一瑞穗高優質鮮乳"
