from fastapi import APIRouter, Query, HTTPException
import requests
import json # 匯入 json 模組

router = APIRouter(
    prefix="/prices",
    tags=["prices"]
)

@router.get("/necessities-price")
def get_necessities_prices(category: str = Query(None), commodity: str = Query(None)):
    try:
        res = requests.get(
            "https://opendata.ey.gov.tw/api/ConsumerProtection/NecessitiesPrice",
            params={"CategoryName": category, "Name": commodity},
        )
        # ⭐️ 檢查狀態碼，如果不是 200 (OK)，就主動報錯
        if res.status_code != 200:
            raise HTTPException(
                status_code=502, # 502 Bad Gateway
                detail=f"External API failed with status {res.status_code}"
            )
        
        # ⭐️ 嘗試解析 JSON
        return res.json()
    
    except json.JSONDecodeError: # 修正：使用更精確的例外
        raise HTTPException(
            status_code=502, # 502 Bad Gateway
            detail="Failed to decode JSON response from external API"
        )
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=503, # 503 Service Unavailable
            detail=f"Error connecting to external API: {e}"
        )