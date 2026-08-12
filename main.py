from fastapi import FastAPI, HTTPException
import requests
import uvicorn

app = FastAPI()

@app.get("/api/v1/reservations")
def get_live_reservations(ship_id: str = "1359", yyyymm: str = "202609", debug: bool = False):
    target_url = f"https://service.sunsang24.com/v1/customer/event_list/{ship_id}"
    
    params = {
        "rows": 100,
        "yyyymm": yyyymm
    }
    
    # 일반 한국 브라우저 접속으로 완벽하게 위장하는 헤더
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://seojin.sunsang24.com/',
        'Origin': 'https://seojin.sunsang24.com',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    
    try:
        response = requests.get(target_url, params=params, headers=headers, timeout=8)
        
        if response.status_code != 200:
            return {"status": "error", "http_code": response.status_code, "msg": "선상24 응답 실패"}
            
        raw_data = response.json()
        
        # ?debug=true 로 접속 시 선상24에서 온 날것의 데이터 그대로 확인
        if debug:
            return {
                "status": "debug_mode", 
                "raw_data_type": str(type(raw_data)),
                "raw_data": raw_data
            }
            
        cleaned_results = []
        
        if isinstance(raw_data, list):
            for item in raw_data:
                # 공지사항이나 팝업도 포함하되 구분 표시
                is_notice = bool(item.get('is_notice') or item.get('is_popup'))
                
                cleaned_results.append({
                    "schedule_no": item.get("no"),
                    "ship_name": item.get("ship_name", ""),
                    "event_date": item.get("event_sdate", "") or item.get("date", "") or "",
                    "title": item.get("title", ""),
                    "max_seat": int(item.get("max_cnt", 0) or item.get("total_seat", 0) or 0),
                    "rem_seat": int(item.get("rem_cnt", 0) or item.get("left_seat", 0) or 0),
                    "price": int(item.get("price", 0) or item.get("fee", 0) or 0),
                    "is_notice": is_notice,
                    "booking_url": f"https://service.sunsang24.com/v1/customer/event_list/{ship_id}"
                })
        
        return {
            "status": "success", 
            "count": len(cleaned_results), 
            "data": cleaned_results
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
