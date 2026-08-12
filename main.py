from fastapi import FastAPI, HTTPException
import requests
import uvicorn
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
    yyyymm: str = "202608", 
    start_date: str = None, 
    end_date: str = None,
    debug: bool = False
):
    if not start_date or not end_date:
        try:
            year = int(yyyymm[:4])
            month = int(yyyymm[4:6])
            last_day = calendar.monthrange(year, month)[1]
            start_date = f"{year}-{month:02d}-01"
            end_date = f"{year}-{month:02d}-{last_day:02d}"
        except Exception:
            start_date = "2026-08-01"
            end_date = "2026-08-31"

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
        
        # 디버그 모드: 원본 JSON 구조 확인용
        if debug:
            return {"status": "debug", "raw_data": raw_list}
        
        cleaned_results = []
        
        for top_item in raw_list:
            if not isinstance(top_item, dict):
                continue
            
            # 날짜 항목 내 하위 리스트(ship_schedules, schedules, events 등) 탐색
            inner_list = None
            for key in ['ship_schedules', 'schedules', 'events', 'list', 'ships', 'items']:
                if key in top_item and isinstance(top_item[key], list) and len(top_item[key]) > 0:
                    inner_list = top_item[key]
                    break
            
            # 하위 리스트가 있으면 하위 항목들을 개별 레코드로 분리
            items_to_process = []
            if inner_list:
                for sub in inner_list:
                    if isinstance(sub, dict):
                        merged = top_item.copy()
                        merged.update(sub)
                        items_to_process.append(merged)
            else:
                items_to_process.append(top_item)

            # 필드 추출 및 정제
            for item in items_to_process:
                event_date = item.get("sdate") or item.get("event_sdate") or item.get("date") or ""
                
                ship_info = item.get("ship") if isinstance(item.get("ship"), dict) else {}
                ship_name = item.get("ship_name") or ship_info.get("name") or item.get("name") or ""
                
                title = (
                    item.get("title") or 
                    item.get("subject") or 
                    item.get("fish_type") or 
                    item.get("fish_name") or 
                    item.get("notice_title") or ""
                )
                
                max_seat = int(
                    item.get("person_limit") or 
                    item.get("max_cnt") or 
                    item.get("total_seat") or 
                    item.get("max_person") or 0
                )
                rem_seat = int(
                    item.get("person_rem") or 
                    item.get("rem_cnt") or 
                    item.get("left_seat") or 
                    item.get("rem_person") or 0
                )
                price = int(
                    item.get("person_price") or 
                    item.get("price") or 
                    item.get("fee") or 0
                )
                
                ready = bool(
                    item.get("reservation_fishing_ready") or 
                    item.get("is_ready") or 
                    (rem_seat > 0) or 
                    bool(title)
                )

                cleaned_results.append({
                    "schedule_no": item.get("ship_schedule_no") or item.get("no") or item.get("id"),
                    "ship_name": ship_name,
                    "event_date": event_date,
                    "title": title,
                    "max_seat": max_seat,
                    "rem_seat": rem_seat,
                    "price": price,
                    "ready": ready,
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
