from fastapi import FastAPI, HTTPException
import requests
import uvicorn

app = FastAPI()

# 일반적인 브라우저 헤더 설정
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*'
}

@app.get("/api/v1/reservations")
def get_live_reservations(ship_id: str, yyyymm: str):
    """
    앱에서 ship_id와 조회할 연월(yyyymm)을 전달받아
    실시간으로 데이터를 가져온 뒤 정제하여 앱으로 반환하는 중계 API
    """
    target_url = f"https://service.sunsang24.com/v1/customer/event_list/{ship_id}"
    params = {"rows": 100, "yyyymm": yyyymm}
    
    try:
        response = requests.get(target_url, params=params, headers=HEADERS, timeout=5)
        
        if response.status_code == 200:
            raw_data = response.json()
            cleaned_results = []
            
            # 앱에서 쓰기 좋게 필요 데이터만 추출
            if isinstance(raw_data, list):
                for item in raw_data:
                    if item.get('is_notice') or item.get('is_popup'):
                        continue
                    
                    cleaned_results.append({
                        "schedule_no": item.get("no"),
                        "ship_name": item.get("ship_name", ""),
                        "event_date": item.get("event_sdate", ""),
                        "title": item.get("title", ""),
                        "max_seat": int(item.get("max_cnt", 0) or 0),
                        "rem_seat": int(item.get("rem_cnt", 0) or 0),
                        "price": int(item.get("price", 0) or 0),
                        "booking_url": f"https://service.sunsang24.com/v1/customer/event_list/{ship_id}"
                    })
            
            return {"status": "success", "count": len(cleaned_results), "data": cleaned_results}
        else:
            raise HTTPException(status_code=response.status_code, detail="외부 서버 응답 오류")
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)