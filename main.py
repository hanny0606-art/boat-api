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

EXCLUDE_KEYWORDS = ["이벤트알림", "공지사항", "조황정보", "전체보기", "환불안내", "팝업", "규정"]

@app.get("/api/v1/reservations")
def get_live_reservations(
    subdomain: str = "daebak", 
    ship_id: str = None,
    yyyymm: str = "202609",
    start_date: str = None,
    end_date: str = None
):
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

    # 1. 선단 메인 페이지에서 등록된 모든 ship_id 정밀 자동 스캔
    fleet_html_url = f"https://{subdomain}.sunsang24.com/ship/schedule_fleet/{yyyymm}"
    discovered_ship_ids = set()
    
    if ship_id:
        discovered_ship_ids.add(str(ship_id))

    try:
        html_res = requests.get(fleet_html_url, headers=HEADERS, timeout=5)
        if html_res.status_code == 200:
            html_text = html_res.text
            # URL 및 스크립트 내부 ship_id 추출
            found_ids = re.findall(r'/(?:schedule|event_list|ship)/(\d{3,6})', html_text)
            for fid in found_ids:
                discovered_ship_ids.add(fid)
                
            found_ids_js = re.findall(r'ship[_\-]?id["\']?\s*[:=]\s*["\']?(\d{3,6})', html_text, re.I)
            for fid in found_ids_js:
                discovered_ship_ids.add(fid)
    except Exception:
        pass

    # 기본 백업 ship_id (대박호 계열)
    if not discovered_ship_ids:
        discovered_ship_ids = {"375", "376", "377"}

    # 2. 스캔된 선박별 상세 일정 정보 수집 (schedule_no 기준 1:1 매핑 테이블 생성)
    master_schedule_dict = {}

    for sid in discovered_ship_ids:
        info_url = f"https://service.sunsang24.com/v1/customer/event_list/{sid}?rows=100&yyyymm={yyyymm}"
        try:
            res = requests.get(info_url, headers=HEADERS, timeout=5)
            if res.status_code == 200:
                raw_data = res.json()
                raw_list = raw_data.get("data") if isinstance(raw_data, dict) else (raw_data if isinstance(raw_data, list) else [])
                
                for item in raw_list:
                    if not isinstance(item, dict):
                        continue
                    if item.get("is_notice") or item.get("is_popup"):
                        continue
                    
                    title = item.get("title") or item.get("fish_type") or item.get("subject") or ""
                    if any(kw in title for kw in EXCLUDE_KEYWORDS):
                        continue

                    sched_no = str(item.get("no") or item.get("ship_schedule_no") or "")
                    if sched_no:
                        master_schedule_dict[sched_no] = {
                            "ship_id": sid,
                            "ship_name": item.get("ship_name") or "선박",
                            "title": title,
                            "max_seat": int(item.get("max_cnt") or item.get("total_seat") or item.get("person_limit") or 0),
                            "rem_seat": int(item.get("rem_cnt") or item.get("left_seat") or item.get("person_rem") or 0),
                            "price": int(item.get("price") or item.get("fee") or item.get("person_price") or 0),
                        }
        except Exception:
            continue

    # 3. 실시간 예약 API 데이터 수집 및 고유 일정 번호(schedule_no) 1:1 결합
    fleet_res_url = f"https://{subdomain}.sunsang24.com/ship/schedule_fleet_reservation/{start_date}/{end_date}"
    req_headers = HEADERS.copy()
    req_headers['Referer'] = f"https://{subdomain}.sunsang24.com/"

    cleaned_results = []
    try:
        res = requests.get(fleet_res_url, headers=req_headers, timeout=6)
        if res.status_code == 200:
            json_data = res.json()
            raw_list = json_data.get("data", []) if isinstance(json_data, dict) else json_data
            
            for item in raw_list:
                if not isinstance(item, dict):
                    continue

                sdate = item.get("sdate", "")
                sched_no = str(item.get("ship_schedule_no") or item.get("no") or "")
                
                # 1:1 ID 매칭
                detail = master_schedule_dict.get(sched_no, {})

                rem_seat = detail.get("rem_seat", 0)
                title = detail.get("title", "")
                fishing_ready = bool(item.get("reservation_fishing_ready"))
                
                ready = fishing_ready or rem_seat > 0 or bool(title)

                cleaned_results.append({
                    "schedule_no": int(sched_no) if sched_no.isdigit() else sched_no,
                    "subdomain": subdomain,
                    "ship_id": detail.get("ship_id", ship_id or ""),
                    "ship_name": detail.get("ship_name", "선박"),
                    "event_date": sdate,
                    "title": title,
                    "max_seat": detail.get("max_seat", 0),
                    "rem_seat": rem_seat,
                    "price": detail.get("price", 0),
                    "ready": ready,
                    "booking_url": f"https://{subdomain}.sunsang24.com/ship/schedule_fleet/{yyyymm}"
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
