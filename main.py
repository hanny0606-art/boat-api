from fastapi import FastAPI, HTTPException
import requests
import uvicorn

app = FastAPI()

@app.get("/api/v1/reservations")
def get_live_reservations(ship_id: str, yyyymm: str):
    target_url = f"https://service.sunsang24.com/v1/customer/event_list/{ship_id}"
    params = {"rows": 100, "yyyymm": yyyymm}
    
    # 선상24 API 차단 우회를 위한 필수 헤더 추가
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': f'https://sunsang24.com/',
        'Origin': 'https://sunsang24.com'
    }
    
    try:
        response = requests.get(target_url, params=params, headers=headers, timeout=8)
        
        if response.status_code == 200:
            raw_data = response.json()
            cleaned_results = []
            
            if isinstance(raw_data, list):
                for item in raw_data:
                    # 팝업 전용 공지사항만 제외하고 실제 일정 데이터 포함
                    if item.get('is_popup') is True and item.get('is_notice') is True and not item.get('event_sdate'):
                        continue
                    
                    # 수집 데이터 정리
                    cleaned_results.append({
                        "schedule_no": item.get("no"),
                        "ship_name": item.get("ship_name", ""),
                        "event_date": item.get("event_sdate", "") or item.get("date", ""),
                        "title": item.get("title", ""),
                        "max_seat": int(item.get("max_cnt", 0) or item.get("total_seat", 0) or 0),
                        "rem_seat": int(item.get("rem_cnt", 0) or item.get("left_seat", 0) or 0),
                        "price": int(item.get("price", 0) or item.get("fee", 0) or 0),
                        "booking_url": f"https://service.sunsang24.com/v1/customer/event_list/{ship_id}"
                    })
            
            return {"status": "success", "count": len(cleaned_results), "data": cleaned_results}
        else:
            raise HTTPException(status_code=response.status_code, detail="외부 API 응답 에러")
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
