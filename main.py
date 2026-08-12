from fastapi import FastAPI, HTTPException
import requests
from bs4 import BeautifulSoup
import re
import uvicorn

app = FastAPI()

# Step 1에서 발급받은 본인의 ScraperAPI 키를 여기에 입력하세요
SCRAPER_API_KEY = "31410731f1e2583c1a2bbbd532c282ea"

@app.get("/api/v1/reservations")
def get_live_reservations(subdomain: str = "daebak", yyyymm: str = "202609"):
    target_url = f"https://{subdomain}.sunsang24.com/ship/schedule_fleet/{yyyymm}"
    
    # ScraperAPI 엔드포인트 설정 (render=true 옵션으로 자바스크립트 완전 실행)
    scraper_url = "http://api.scraperapi.com"
    params = {
        'api_key': SCRAPER_API_KEY,
        'url': target_url,
        'render': 'true'  # 클라우드 크롬 브라우저에서 JS를 실행하도록 지시
    }

    try:
        # ScraperAPI가 JS 렌더링을 끝내고 완성형 HTML을 반환할 때까지 대기
        res = requests.get(scraper_url, params=params, timeout=35)
        if res.status_code != 200:
            return {
                "status": "error", 
                "message": f"ScraperAPI 요청 실패 (상태코드: {res.status_code}). API Key를 확인하세요."
            }

        html_text = res.text
        soup = BeautifulSoup(html_text, 'html.parser')
        
        cleaned_results = []
        year_str = yyyymm[:4]
        month_str = yyyymm[4:6]

        # JS 실행 후 그려진 일정 영역 요소 검색
        elements = soup.find_all(['td', 'tr', 'div', 'li'])

        for el in elements:
            text = el.get_text(separator=' ', strip=True)
            if '어종' not in text and '남은자리' not in text and '예약' not in text:
                continue

            # 1. 배 이름 추출 (예: 레전드호, 뉴항구호)
            ship_match = re.search(r'([가-힣A-Za-z0-9]+호)', text)
            ship_name = ship_match.group(1) if ship_match else ""

            # 2. 어종 정밀 추출 ("어종 : 주꾸미,갑오징어" -> "주꾸미,갑오징어")
            fish_match = re.search(r'어종\s*[:\s]*([^/\n\r<]+)', text)
            title = fish_match.group(1).strip() if fish_match else ""

            # 3. 날짜 추출 (M월 D일)
            date_match = re.search(r'(\d{1,2})월\s*(\d{1,2})일', text) or re.search(r'\b([1-9]|[12][0-9]|3[01])일\b', text)
            event_date = ""
            if date_match:
                if len(date_match.groups()) == 2:
                    event_date = f"{year_str}-{int(date_match.group(1)):02d}-{int(date_match.group(2)):02d}"
                else:
                    event_date = f"{year_str}-{month_str}-{int(date_match.group(1)):02d}"

            # 4. 남은 자리 수 추출
            rem_seat = 0
            rem_match = re.search(r'남은자리\s*[:\s]*(\d+)', text) or re.search(r'(\d+)명\s*남음', text)
            if rem_match:
                rem_seat = int(rem_match.group(1))

            is_closed = '예약마감' in text or '완료' in text

            if event_date and (ship_name or title):
                cleaned_results.append({
                    "subdomain": subdomain,
                    "ship_name": ship_name or "선박",
                    "event_date": event_date,
                    "title": title or "출항 일정",
                    "rem_seat": rem_seat,
                    "ready": not is_closed and (rem_seat > 0 or bool(title)),
                    "booking_url": target_url
                })

        # 날짜 / 선박 / 어종 기준 중복 정제
        seen = set()
        unique_results = []
        for item in cleaned_results:
            key = (item["event_date"], item["ship_name"], item["title"])
            if key not in seen:
                seen.add(key)
                unique_results.append(item)

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
