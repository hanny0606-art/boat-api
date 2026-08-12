from fastapi import FastAPI, HTTPException
import requests
from bs4 import BeautifulSoup
import re
import uvicorn
import calendar

app = FastAPI()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

@app.get("/api/v1/reservations")
def get_live_reservations(
    subdomain: str = "daebak", 
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
            start_date = f"{yyyymm[:4]}-{yyyymm[4:6]}-01"
            end_date = f"{yyyymm[:4]}-{yyyymm[4:6]}-30"

    # 1. 선단 fleet 달력 HTML URL
    fleet_html_url = f"https://{subdomain}.sunsang24.com/ship/schedule_fleet/{yyyymm}"
    # 2. 예약 현황 API URL
    fleet_res_url = f"https://{subdomain}.sunsang24.com/ship/schedule_fleet_reservation/{start_date}/{end_date}"

    req_headers = HEADERS.copy()
    req_headers['Referer'] = f"https://{subdomain}.sunsang24.com/"

    # --- [Step 1] Fleet HTML 파싱: 배이름, 어종(title), 정원, 마감상태 정밀 추출 ---
    html_schedules = []
    try:
        html_res = requests.get(fleet_html_url, headers=req_headers, timeout=8)
        if html_res.status_code == 200:
            soup = BeautifulSoup(html_res.text, 'html.parser')
            
            # 일별/선박별 일정 블록 수집
            blocks = soup.find_all(['td', 'tr', 'div', 'li'])
            
            for block in blocks:
                text = block.get_text(separator=' ', strip=True)
                if '어종' not in text and '운항시간' not in text and '예약' not in text:
                    continue

                # 배 이름 추출 (예: 레전드호, 뉴항구호)
                ship_match = re.search(r'([가-힣A-Za-z0-9]+호)', text)
                ship_name = ship_match.group(1) if ship_match else ""

                # 어종 정보만 정밀 추출 ("어종 : 주꾸미,갑오징어 / 선상" -> "주꾸미,갑오징어")
                fish_match = re.search(r'어종\s*[:\s]*([^/\n\r<]+)', text)
                title = fish_match.group(1).strip() if fish_match else ""

                # 날짜 추출 (예: 9월 6일 -> 2026-09-06)
                m_md = re.search(r'(\d{1,2})월\s*(\d{1,2})일', text)
                m_d = re.search(r'\b([1-9]|[12][0-9]|3[01])일\b', text)
                
                event_date = ""
                year_str = yyyymm[:4]
                month_str = yyyymm[4:6]

                if m_md:
                    event_date = f"{year_str}-{int(m_md.group(1)):02d}-{int(m_md.group(2)):02d}"
                elif m_d:
                    event_date = f"{year_str}-{month_str}-{int(m_d.group(1)):02d}"

                # 정원 / 잔여석 추출
                max_seat = 0
                rem_seat = 0
                seat_match = re.search(r'(\d+)명', text)
                if seat_match:
                    max_seat = int(seat_match.group(1))

                is_closed = '예약마감' in text
                if not is_closed:
                    rem_match = re.search(r'남은자리\s*[:\s]*(\d+)', text)
                    if rem_match:
                        rem_seat = int(rem_match.group(1))

                if event_date and (ship_name or title):
                    html_schedules.append({
                        "event_date": event_date,
                        "ship_name": ship_name,
                        "title": title,
                        "max_seat": max_seat,
                        "rem_seat": rem_seat,
                        "is_closed": is_closed
                    })
    except Exception as e:
        print(f"HTML 파싱 에러: {e}")

    # --- [Step 2] 실시간 예약 API 응답과 HTML 데이터 매칭 ---
    cleaned_results = []
    try:
        res = requests.get(fleet_res_url, headers=req_headers, timeout=8)
        if res.status_code == 200:
            json_data = res.json()
            raw_list = json_data.get("data", []) if isinstance(json_data, dict) else json_data
            
            for idx, item in enumerate(raw_list):
                if not isinstance(item, dict):
                    continue

                sdate = item.get("sdate", "")
                sched_no = item.get("ship_schedule_no") or item.get("no")

                # 동일 날짜의 HTML 파싱 데이터 매칭
                matched_list = [h for h in html_schedules if h["event_date"] == sdate]
                
                # 순서나 배 이름 매칭
                matched_info = None
                if matched_list:
                    if idx < len(matched_list):
                        matched_info = matched_list[idx]
                    else:
                        matched_info = matched_list[0]

                ship_name = matched_info["ship_name"] if matched_info and matched_info["ship_name"] else "선박"
                title = matched_info["title"] if matched_info else ""
                max_seat = matched_info["max_seat"] if matched_info else 0
                rem_seat = matched_info["rem_seat"] if matched_info else 0
                is_closed = matched_info["is_closed"] if matched_info else False

                fishing_ready = bool(item.get("reservation_fishing_ready"))
                ready = fishing_ready and not is_closed

                cleaned_results.append({
                    "schedule_no": sched_no,
                    "subdomain": subdomain,
                    "ship_name": ship_name,
                    "event_date": sdate,
                    "title": title,
                    "max_seat": max_seat,
                    "rem_seat": rem_seat,
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
