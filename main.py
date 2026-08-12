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
    # 스캔으로 발견된 선박 전용 일정 API 엔드포인트 목록
    urls_to_try = [
        f"https://{subdomain}.sunsang24.com/ship/schedule/{ship_id}?yyyymm={yyyymm}",
        f"https://{subdomain}.sunsang24.com/ship/event_list?yyyymm={yyyymm}&ship_id={ship_id}",
        f"https://service.sunsang24.com/v1/customer/event_list/{ship_id}?rows=100&yyyymm={yyyymm}"
    ]
    
    req_headers = HEADERS.copy()
    req_headers['Referer'] = f"https://{subdomain}.sunsang24.com/"
    req_headers['Origin'] = f"https://{subdomain}.sunsang24.com"

    debug_logs = {}

    for target_url in urls_to_try:
        try:
            res = requests.get(target_url, headers=req_headers, timeout=6)
            if res.status_code == 200:
                try:
                    data = res.json()
                    debug_logs[target_url] = data
                    
                    # JSON 데이터 파싱
                    raw_list = data.get("data") if isinstance(data, dict) else data
                    if isinstance(raw_list, list) and len(raw_list) > 0:
                        cleaned = []
                        for item in raw_list:
                            if not isinstance(item, dict):
                                continue
                                
                            # 공지사항 제외 및 유효 일정 필터링
                            is_notice = item.get("is_notice") or item.get("is_popup")
                            event_date = item.get("event_sdate") or item.get("sdate") or item.get("date") or ""
                            title = item.get("title") or item.get("fish_type") or item.get("subject") or ""
                            
                            if is_notice and not event_date:
                                continue

                            rem_seat = int(item.get("rem_cnt") or item.get("person_rem") or item.get("left_seat") or 0)
                            max_seat = int(item.get("max_cnt") or item.get("person_limit") or item.get("total_seat") or 0)
                            price = int(item.get("price") or item.get("person_price") or item.get("fee") or 0)
                            ship_name = item.get("ship_name") or "신출항호"
                            
                            if event_date or title:
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
                        
                        # 정제된 결과가 존재하면 성공 반환 (debug 모드가 아닐 때)
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
                    debug_logs[target_url] = res.text[:200]
        except Exception as e:
            debug_logs[target_url] = str(e)

    if debug:
        return {"status": "debug_mode", "responses": debug_logs}

    return {
        "status": "error",
        "message": "데이터 수집 실패. ?debug=true로 각 엔드포인트 응답을 확인하세요.",
        "debug_logs": debug_logs
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
