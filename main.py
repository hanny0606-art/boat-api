from fastapi import FastAPI, HTTPException
import requests
import uvicorn

app = FastAPI()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'X-Requested-With': 'XMLHttpRequest'
}

@app.get("/api/v1/reservations")
def get_live_reservations(
    subdomain: str = "seojin", 
    ship_id: str = "1359", 
    yyyymm: str = "202608",
    debug: bool = False
):
    urls_to_try = [
        f"https://{subdomain}.sunsang24.com/ship/schedule/{ship_id}?yyyymm={yyyymm}",
        f"https://{subdomain}.sunsang24.com/ship/event_list?yyyymm={yyyymm}&ship_id={ship_id}",
        f"https://service.sunsang24.com/v1/customer/event_list/{ship_id}?rows=100&yyyymm={yyyymm}"
    ]
    
    req_headers = HEADERS.copy()
    req_headers['Referer'] = f"https://{subdomain}.sunsang24.com/"
    req_headers['Origin'] = f"https://{subdomain}.sunsang24.com"

    debug_logs = {}
    formatted_yyyymm = f"{yyyymm[:4]}-{yyyymm[4:6]}"  # 예: "2026-08"

    for target_url in urls_to_try:
        try:
            res = requests.get(target_url, headers=req_headers, timeout=6)
            if res.status_code == 200:
                try:
                    data = res.json()
                    debug_logs[target_url] = data
                    
                    raw_list = data.get("data") if isinstance(data, dict) else data
                    if isinstance(raw_list, list) and len(raw_list) > 0:
                        cleaned = []
                        for item in raw_list:
                            if not isinstance(item, dict):
                                continue
                                
                            # 1. 공지사항 / 팝업 무조건 제외
                            if item.get("is_notice") is True or item.get("is_popup") is True:
                                continue
                                
                            title = item.get("title") or item.get("fish_type") or item.get("subject") or ""
                            if "환불" in title or "공지" in title or "안내" in title:
                                continue

                            event_date = item.get("event_sdate") or item.get("sdate") or item.get("date") or ""
                            # 2. 요청 연월(예: 2026-08)과 일치하지 않는 과거 날짜 제외
                            if formatted_yyyymm not in event_date:
                                continue

                            rem_seat = int(item.get("rem_cnt") or item.get("person_rem") or item.get("left_seat") or 0)
                            max_seat = int(item.get("max_cnt") or item.get("person_limit") or item.get("total_seat") or 0)
                            price = int(item.get("price") or item.get("person_price") or item.get("fee") or 0)
                            ship_name = item.get("ship_name") or "신출항호"
                            
                            cleaned.append({
                                "schedule_no": item.get("no") or item.get("ship_schedule_no") or item.get("id"),
                                "ship_id": ship_id,
                                "ship_name": ship_name,
                                "event_date": event_date,
                                "title": title,
                                "max_seat": max_seat,
                                "rem_seat": rem_seat,
                                "price": price,
                                "ready": rem_seat > 0 or bool(title),
                                "booking_url": f"https://{subdomain}.sunsang24.com/"
                            })
                        
                        if cleaned and not debug:
                            return {
                                "status": "success",
                                "subdomain": subdomain,
                                "ship_id": ship_id,
                                "yyyymm": yyyymm,
                                "count": len(cleaned),
                                "data": cleaned
                            }
                except Exception:
                    debug_logs[target_url] = res.text[:300]
        except Exception as e:
            debug_logs[target_url] = str(e)

    return {
        "status": "debug_mode" if debug else "no_data_filtered",
        "message": "필터링 후 유효 데이터가 없거나 debug 모드입니다. 아래 각 URL 원본 데이터를 확인하세요.",
        "debug_logs": debug_logs
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
