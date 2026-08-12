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
    subdomain: str = "daebak", 
    ship_id: str = "375",
    yyyymm: str = "202609",
    start_date: str = None,
    end_date: str = None
):
    # 날짜 범위 자동 계산
    if not start_date or not end_date:
        try:
            year = int(yyyymm[:4])
            month = int(yyyymm[4:6])
            last_day = calendar.monthrange(year, month)[1]
            start_date = f"{year}-{month:02d}-01"
            end_date = f"{year}-{month:02d}-{last_day:02d}"
        except Exception:
            start_date = "2026-09-01"
            end_date = "2026-09-30"

    # 1. 스크린샷 1의 진짜 일정/어종 API (service.sunsang24.com)
    info_url = f"https://service.sunsang24.com/v1/customer/event_list/{ship_id}?rows=100&yyyymm={yyyymm}"
    
    # 2. 스크린샷 2의 예약 현황 API
    res_url = f"https://{subdomain}.sunsang24.com/ship/schedule_fleet_reservation/{start_date}/{end_date}"

    req_headers = HEADERS.copy()
    req_headers['Referer'] = f"https://{subdomain}.sunsang24.com/"
    req_headers['Origin'] = f"https://{subdomain}.sunsang24.com"

    try:
        # A. 일정 기본 정보 수집 (어종, 선비, 정원 등)
        info_dict = {}
        res_info = requests.get(info_url, headers=HEADERS, timeout=5)
        if res_info.status_code == 200:
            raw_info = res_info.json()
            if isinstance(raw_info, list):
                for item in raw_info:
                    if item.get("is_notice") or item.get("is_popup"):
                        continue
                    sdate = item.get("event_sdate") or item.get("date") or ""
                    if sdate:
                        info_dict[sdate] = {
                            "title": item.get("title") or item.get("fish_type") or "",
                            "max_seat": int(item.get("max_cnt") or item.get("total_seat") or 0),
                            "rem_seat": int(item.get("rem_cnt") or item.get("left_seat") or 0),
                            "price": int(item.get("price") or item.get("fee") or 0),
                            "ship_name": item.get("ship_name") or "대박호"
                        }

        # B. 예약 현황 데이터 수집 및 결합
        cleaned_results = []
        res_fleet = requests.get(res_url, headers=req_headers, timeout=5)
        
        if res_fleet.status_code == 200:
            fleet_json = res_fleet.json()
            raw_list = fleet_json.get("data", [])
            
            for item in raw_list:
                sdate = item.get("sdate", "")
                schedule_no = item.get("ship_schedule_no") or item.get("no")
                
                # 정보 결합
                detail = info_dict.get(sdate, {})
                
                ready = bool(
                    item.get("reservation_fishing_ready") or 
                    item.get("reservation_ready") or 
                    detail.get("rem_seat", 0) > 0 or 
                    bool(detail.get("title"))
                )

                cleaned_results.append({
                    "schedule_no": schedule_no,
                    "subdomain": subdomain,
                    "ship_id": ship_id,
                    "ship_name": detail.get("ship_name", "선박"),
                    "event_date": sdate,
                    "title": detail.get("title", ""),
                    "max_seat": detail.get("max_seat", 0),
                    "rem_seat": detail.get("rem_seat", 0),
                    "price": detail.get("price", 0),
                    "ready": ready,
                    "booking_url": f"https://{subdomain}.sunsang24.com/"
                })

        return {
            "status": "success",
            "subdomain": subdomain,
            "ship_id": ship_id,
            "period": f"{start_date} ~ {end_date}",
            "count": len(cleaned_results),
            "data": cleaned_results
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
