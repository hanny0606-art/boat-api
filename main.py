from fastapi import FastAPI, HTTPException
import requests
import uvicorn
from datetime import datetime
import calendar

app = FastAPI()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

@app.get("/api/v1/reservations")
def get_live_reservations(
    subdomain: str = "seojin", 
    yyyymm: str = "202611", 
    start_date: str = None, 
    end_date: str = None
):
    # 날짜 범위가 지정되지 않은 경우 해당 연월(yyyymm)의 1일~말일 자동 계산
    if not start_date or not end_date:
        try:
            year = int(yyyymm[:4])
            month = int(yyyymm[4:6])
            last_day = calendar.monthrange(year, month)[1]
            start_date = f"{year}-{month:02d}-01"
            end_date = f"{year}-{month:02d}-{last_day:02d}"
        except Exception:
            start_date = "2026-11-01"
            end_date = "2026-11-30"

    target_url = f"https://{subdomain}.sunsang24.com/ship/schedule_fleet_reservation/{start_date}/{end_date}"
    
    req_headers = HEADERS.copy()
    req_headers['Referer'] = f"https://{subdomain}.sunsang24.com/"
    req_headers['Origin'] = f"https://{subdomain}.sunsang24.com"

    try:
        response = requests.get(target_url, headers=req_headers, timeout=8)
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="선상24 API 응답 실패")
            
        json_data = response.json()
        raw_list = json_data.get("data", [])
        
        cleaned_results = []
        for item in raw_list:
            cleaned_results.append({
                "schedule_no": item.get("ship_schedule_no") or item.get("no"),
                "ship_name": item.get("ship_name") or item.get("ship", {}).get("name", ""),
                "event_date": item.get("sdate") or item.get("event_sdate", ""),
                "title": item.get("title") or item.get("fish_type", ""),
                "max_seat": int(item.get("max_cnt") or item.get("total_seat") or item.get("person_limit") or 0),
                "rem_seat": int(item.get("rem_cnt") or item.get("left_seat") or item.get("person_rem") or 0),
                "price": int(item.get("price") or item.get("fee") or 0),
                "ready": item.get("reservation_fishing_ready", False),
                "booking_url": f"https://{subdomain}.sunsang24.com/"
            })
            
        return {
            "status": "success",
            "subdomain": subdomain,
            "period": f"{start_date} ~ {end_date}",
            "count": len(cleaned_results),
            "data": cleaned_results
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
