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

def safe_extract(item: dict, keys: list, default=None):
    """최상위 딕셔너리뿐만 아니라 하위 중첩 객체/리스트까지 탐색하여 값을 추출합니다."""
    # 1. 최상위 단일 필드 검색
    for k in keys:
        if k in item and item[k] not in (None, ""):
            return item[k]
            
    # 2. 하위 중첩 객체(events, ship, schedule 등) 내부 검색
    nested_keys = ['events', 'event', 'ship', 'ships', 'schedule', 'schedules', 'detail', 'info']
    for nk in nested_keys:
        sub_obj = item.get(nk)
        if isinstance(sub_obj, dict):
            for k in keys:
                if k in sub_obj and sub_obj[k] not in (None, ""):
                    return sub_obj[k]
        elif isinstance(sub_obj, list) and len(sub_obj) > 0:
            for elem in sub_obj:
                if isinstance(elem, dict):
                    for k in keys:
                        if k in elem and elem[k] not in (None, ""):
                            return elem[k]
    return default

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
        
        # 디버그 모드: 원본 구조 확인용
        if debug:
            return {"status": "debug", "raw_data": raw_list}
        
        cleaned_results = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue

            # 날짜 추출
            event_date = safe_extract(item, ["sdate", "event_sdate", "date"], "")
            
            # 배 이름 및 제목(어종/일정) 추출
            ship_name = safe_extract(item, ["ship_name", "name"], "")
            title = safe_extract(item, ["title", "fish_type", "subject", "notice_title"], "")
            
            # 인원 및 가격 수치 추출
            max_seat = int(safe_extract(item, ["max_cnt", "total_seat", "person_limit", "max_person"], 0) or 0)
            rem_seat = int(safe_extract(item, ["rem_cnt", "left_seat", "person_rem", "rem_person"], 0) or 0)
            price = int(safe_extract(item, ["price", "fee", "person_price"], 0) or 0)
            
            # 예약 가능 여부
            ready_val = safe_extract(item, ["reservation_fishing_ready", "is_ready", "ready"], False)
            # 일정 제목이 있거나 남은 자리가 0보다 크면 오픈된 일정으로 판단
            ready = bool(ready_val or title or rem_seat > 0)

            cleaned_results.append({
                "schedule_no": item.get("ship_schedule_no") or item.get("no"),
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
