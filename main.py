from fastapi import FastAPI, HTTPException
import requests
import uvicorn

app = FastAPI()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://sunsang24.com/',
    'Origin': 'https://sunsang24.com'
}

@app.get("/api/v1/reservations")
def get_live_reservations(ship_id: str = "1359", yyyymm: str = "202608"):
    """
    선박 고유 ID(ship_id)와 연월(yyyymm)을 받아
    실시간 어종, 남은자리, 가격, 출항일자를 반환합니다.
    """
    target_url = f"https://service.sunsang24.com/v1/customer/event_list/{ship_id}"
    params = {
        "rows": 100,      # 전체 일정 조회를 위해 필수
        "yyyymm": yyyymm
    }
    
    try:
        response = requests.get(target_url, params=params, headers=HEADERS, timeout=8)
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="선상24 API 응답 실패")
            
        raw_data = response.json()
        cleaned_results = []
        
        if isinstance(raw_data, list):
            for item in raw_data:
                # 1. 공지사항 / 팝업 제외 (실제 출항 일정만 수집)
                if item.get('is_notice') or item.get('is_popup'):
                    continue
                
                # 2. 필수 필드 추출
                event_date = item.get("event_sdate") or item.get("date") or ""
                if not event_date:
                    continue

                title = item.get("title") or item.get("fish_type") or ""
                max_seat = int(item.get("max_cnt") or item.get("total_seat") or 0)
                rem_seat = int(item.get("rem_cnt") or item.get("left_seat") or 0)
                price = int(item.get("price") or item.get("fee") or 0)
                ship_name = item.get("ship_name") or "선박"

                cleaned_results.append({
                    "schedule_no": item.get("no") or item.get("id"),
                    "ship_id": ship_id,
                    "ship_name": ship_name,
                    "event_date": event_date,
                    "title": title,
                    "max_seat": max_seat,
                    "rem_seat": rem_seat,
                    "price": price,
                    "ready": rem_seat > 0,
                    "booking_url": f"https://service.sunsang24.com/v1/customer/event_list/{ship_id}"
                })
        
        return {
            "status": "success",
            "ship_id": ship_id,
            "yyyymm": yyyymm,
            "count": len(cleaned_results),
            "data": cleaned_results
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
