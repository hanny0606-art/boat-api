from fastapi import FastAPI, HTTPException
import requests
import uvicorn
import calendar
import re

app = FastAPI()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

EXCLUDE_KEYWORDS = ["이벤트알림", "공지사항", "조황정보", "전체보기", "환불안내", "팝업"]

def clean_date(date_str: str) -> str:
    if not date_str:
        return ""
    match = re.search(r'(\d{4})[.-](\d{1,2})[.-](\d{1,2})', str(date_str))
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    return str(date_str).strip()

@app.get("/api/v1/reservations")
def get_live_reservations(
    subdomain: str = "daebak", 
    ship_id: str = "375",
    yyyymm: str = None,
    start_date: str = None,
    end_date: str = None
):
    # start_date 기반 yyyymm 자동 추출
    if start_date and not yyyymm:
        yyyymm = start_date.replace("-", "")[:6]
    elif not yyyymm:
        yyyymm = "202609"

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

    # 1. 상세 일정/어종 API
    info_url = f"https://service.sunsang24.com/v1/customer/event_list/{ship_id}?rows=100&yyyymm={yyyymm}"
    # 2. 예약 달력 API
    res_url = f"https://{subdomain}.sunsang24.com/ship/schedule_fleet_reservation/{start_date}/{end_date}"

    req_headers = HEADERS.copy()
    req_headers['Referer'] = f"https://{subdomain}.sunsang24.com/"
    req_headers['Origin'] = f"https://{subdomain}.sunsang24.com"

    try:
        # A. 어종 및 일정 세부 정보 추출 (이중 매핑 구조)
        info_by_no = {}
        info_by_date = {}

        res_info = requests.get(info_url, headers=HEADERS, timeout=6)
        if res_info.status_code == 200:
            raw_data = res_info.json()
            
            # JSON 응답 객체/배열 자동 분해
            if isinstance(raw_data, dict):
                raw_list = raw_data.get("data") or raw_data.get("list") or []
            elif isinstance(raw_data, list):
                raw_list = raw_data
            else:
                raw_list = []

            for item in raw_list:
                if not isinstance(item, dict):
                    continue

                if item.get("is_notice") is True or item.get("is_popup") is True:
                    continue

                title = item.get("title") or item.get("fish_type") or item.get("subject") or ""
                if any(kw in title for kw in EXCLUDE_KEYWORDS):
                    continue

                sdate = clean_date(item.get("event_sdate") or item.get("date") or "")
                sched_no = str(item.get("no") or item.get("ship_schedule_no") or "")

                item_detail = {
                    "title": title,
                    "max_seat": int(item.get("max_cnt") or item.get("total_seat") or item.get("person_limit") or 0),
                    "rem_seat": int(item.get("rem_cnt") or item.get("left_seat") or item.get("person_rem") or 0),
                    "price": int(item.get("price") or item.get("fee") or item.get("person_price") or 0),
                    "ship_name": item.get("ship_name") or "대박호"
                }

                if sched_no:
                    info_by_no[sched_no] = item_detail
                if sdate:
                    info_by_date[sdate] = item_detail

        # B. 예약 달력 데이터 수집 및 결합
        cleaned_results = []
        res_fleet = requests.get(res_url, headers=req_headers, timeout=6)
        
        if res_fleet.status_code == 200:
            fleet_json = res_fleet.json()
            raw_list = fleet_json.get("data", []) if isinstance(fleet_json, dict) else fleet_json
            
            for item in raw_list:
                if not isinstance(item, dict):
                    continue

                sdate = clean_date(item.get("sdate", ""))
                sched_no = str(item.get("ship_schedule_no") or item.get("no") or "")

                # 고유번호 우선 매칭 ➔ 날짜 기준 2차 매칭
                detail = info_by_no.get(sched_no) or info_by_date.get(sdate) or {}

                ready = bool(
                    item.get("reservation_fishing_ready") or 
                    detail.get("rem_seat", 0) > 0 or 
                    bool(detail.get("title"))
                )

                cleaned_results.append({
                    "schedule_no": int(sched_no) if sched_no.isdigit() else sched_no,
                    "subdomain": subdomain,
                    "ship_id": ship_id,
                    "ship_name": detail.get("ship_name", "대박호"),
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
