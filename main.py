from fastapi import FastAPI, HTTPException
import requests
from bs4 import BeautifulSoup
import re
import uvicorn

app = FastAPI()

SCRAPER_API_KEY = "31410731f1e2583c1a2bbbd532c282ea"

@app.get("/api/v1/reservations")
def get_live_reservations(subdomain: str = "daebak", yyyymm: str = "202609"):
    target_url = f"https://{subdomain}.sunsang24.com/ship/schedule_fleet/{yyyymm}"
    
    scraper_url = "https://api.scraperapi.com"
    params = {
        'api_key': SCRAPER_API_KEY,
        'url': target_url,
        'render': 'true',         # 크롬 JS 실행
        'country_code': 'kr'      # 한국 프록시 IP
    }

    try:
        res = requests.get(scraper_url, params=params, timeout=60)
        if res.status_code != 200:
            return {
                "status": "error", 
                "message": f"ScraperAPI 응답 실패 (상태코드: {res.status_code})"
            }

        html_text = res.text
        soup = BeautifulSoup(html_text, 'html.parser')
        
        # 전체 텍스트 수집 및 공백 정규화 (줄바꿈/탭 제거)
        raw_text = soup.get_text(separator=' ', strip=True)
        normalized_text = re.sub(r'\s+', ' ', raw_text)

        year_str = yyyymm[:4]
        cleaned_results = []

        # 1. 날짜 위치 탐색 ("9 월 1 일", "9월 1일" 등)
        date_matches = list(re.finditer(r'(\d{1,2})\s*월\s*(\d{1,2})\s*일', normalized_text))

        for i in range(len(date_matches)):
            d_match = date_matches[i]
            month = int(d_match.group(1))
            day = int(d_match.group(2))
            event_date = f"{year_str}-{month:02d}-{day:02d}"

            # 현재 날짜부터 다음 날짜 전까지의 텍스트 블록 자르기
            start_idx = d_match.end()
            end_idx = date_matches[i+1].start() if i + 1 < len(date_matches) else len(normalized_text)
            section_text = normalized_text[start_idx:end_idx]

            # 2. 날짜 구간 내 선박(호) 위치 탐색 (예: 뉴항구호, 레전드호)
            ship_matches = list(re.finditer(r'([가-힣A-Za-z0-9]+호)', section_text))

            for j in range(len(ship_matches)):
                s_match = ship_matches[j]
                ship_name = s_match.group(1)

                s_start = s_match.end()
                s_end = ship_matches[j+1].start() if j + 1 < len(ship_matches) else len(section_text)
                ship_block = section_text[s_start:s_end]

                # 어종 정밀 추출 ("어종 : 주꾸미,갑오징어 / 선상" -> "주꾸미,갑오징어")
                fish_match = re.search(r'어종\s*[:\s]*([^/|\n\r<]+)', ship_block)
                title = fish_match.group(1).strip() if fish_match else ""

                # 남은 자리 및 정원 추출
                rem_seat = 0
                rem_match = re.search(r'남은자리\s*[:\s]*(\d+)', ship_block) or re.search(r'(\d+)\s*명\s*남음', ship_block)
                if rem_match:
                    rem_seat = int(rem_match.group(1))

                max_seat = 0
                max_match = re.search(r'예약/\s*(\d+)\s*명', ship_block) or re.search(r'정원\s*[:\s]*(\d+)', ship_block)
                if max_match:
                    max_seat = int(max_match.group(1))

                is_closed = '예약마감' in ship_block or '마감' in ship_block

                cleaned_results.append({
                    "subdomain": subdomain,
                    "ship_name": ship_name,
                    "event_date": event_date,
                    "title": title or "출항 일정",
                    "max_seat": max_seat,
                    "rem_seat": rem_seat if not is_closed else 0,
                    "ready": not is_closed and (rem_seat > 0 or bool(title)),
                    "booking_url": target_url
                })

        # 중복 항목 제거
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
