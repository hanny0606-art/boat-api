from fastapi import FastAPI, HTTPException
import requests
from bs4 import BeautifulSoup
import re
import uvicorn

app = FastAPI()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

@app.get("/api/v1/reservations")
def get_live_reservations(subdomain: str = "daebak", yyyymm: str = "202609"):
    # 선단 전체 달력 HTML 주소 단 1개만 요청
    target_url = f"https://{subdomain}.sunsang24.com/ship/schedule_fleet/{yyyymm}"
    
    try:
        res = requests.get(target_url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail="선사 페이지 로딩 실패")
            
        html_text = res.text
        soup = BeautifulSoup(html_text, 'html.parser')
        
        cleaned_results = []
        year_str = yyyymm[:4]
        month_str = yyyymm[4:6]

        # 달력 내 날짜/선박별 일정 컨테이너 추출
        # 선상24는 일정 요소를 <tr>, <td>, <div class="schedule..."> 등에 배치함
        containers = soup.find_all(['td', 'tr', 'div'], class_=re.compile(r'schedule|event|day|fleet|item', re.I))
        if not containers:
            containers = soup.find_all(['td', 'div'])

        for container in containers:
            text = container.get_text(separator=' ', strip=True)
            if not text or ('어종' not in text and '남은자리' not in text and '예약' not in text):
                continue

            # 1. 일정 고유 번호(schedule_no) 추출 (data-no, href, onclick 등에서 추출)
            schedule_no = ""
            no_match = re.search(r'(?:schedule_no|no|event_no|id)[=/\'\"]+(\d{6,8})', str(container))
            if no_match:
                schedule_no = no_match.group(1)

            # 2. 날짜 추출 (M월 D일)
            date_match = re.search(r'(\d{1,2})월\s*(\d{1,2})일', text) or re.search(r'\b([1-9]|[12][0-9]|3[01])일\b', text)
            event_date = ""
            if date_match:
                if len(date_match.groups()) == 2:
                    event_date = f"{year_str}-{int(date_match.group(1)):02d}-{int(date_match.group(2)):02d}"
                else:
                    event_date = f"{year_str}-{month_str}-{int(date_match.group(1)):02d}"

            # 3. 배 이름 추출 (레전드호, 뉴항구호 등)
            ship_name = "선박"
            ship_match = re.search(r'([가-힣A-Za-z0-9]+호)', text)
            if ship_match:
                ship_name = ship_match.group(1)

            # 4. 어종 추출 ("어종 : 주꾸미,갑오징어" -> "주꾸미,갑오징어")
            title = ""
            fish_match = re.search(r'어종\s*[:\s]*([^/\n\r<]+)', text)
            if fish_match:
                title = fish_match.group(1).strip()

            # 5. 남은자리 추출
            rem_seat = 0
            rem_match = re.search(r'남은자리\s*[:\s]*(\d+)', text) or re.search(r'(\d+)명\s*남음', text)
            if rem_match:
                rem_seat = int(rem_match.group(1))

            is_closed = '예약마감' in text or '완료' in text

            if event_date and (ship_name != "선박" or title):
                cleaned_results.append({
                    "schedule_no": int(schedule_no) if schedule_no.isdigit() else schedule_no,
                    "subdomain": subdomain,
                    "ship_name": ship_name,
                    "event_date": event_date,
                    "title": title or "출항 일정",
                    "rem_seat": rem_seat,
                    "ready": not is_closed and (rem_seat > 0 or bool(title)),
                    "booking_url": target_url
                })

        # 중복 항목 제거
        seen = set()
        unique_results = []
        for r in cleaned_results:
            key = (r["event_date"], r["ship_name"], r["title"])
            if key not in seen:
                seen.add(key)
                unique_results.append(r)

        return {
            "status": "success",
            "subdomain": subdomain,
            "yyyymm": yyyymm,
            "count": len(unique_results),
            "data": unique_results
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
