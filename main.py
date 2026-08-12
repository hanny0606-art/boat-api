from fastapi import FastAPI, HTTPException
import requests
from bs4 import BeautifulSoup
import re
import uvicorn

app = FastAPI()

SCRAPER_API_KEY = "31410731f1e2583c1a2bbbd532c282ea"

# 해당 선사(대박호 계열)의 실제 등록된 선박 이름 명단
VALID_SHIPS = ["뉴항구호", "뉴항구1호", "레전드호"]

@app.get("/api/v1/reservations")
def get_live_reservations(subdomain: str = "daebak", yyyymm: str = "202609"):
    target_url = f"https://{subdomain}.sunsang24.com/ship/schedule_fleet/{yyyymm}"
    
    scraper_url = "https://api.scraperapi.com"
    params = {
        'api_key': SCRAPER_API_KEY,
        'url': target_url,
        'render': 'true',
        'country_code': 'kr'
    }

    try:
        res = requests.get(scraper_url, params=params, timeout=60)
        if res.status_code != 200:
            return {"status": "error", "message": f"ScraperAPI 응답 실패 (코드: {res.status_code})"}

        html_text = res.text
        soup = BeautifulSoup(html_text, 'html.parser')
        
        raw_text = soup.get_text(separator=' ', strip=True)
        normalized_text = re.sub(r'\s+', ' ', raw_text)

        year_str = yyyymm[:4]
        cleaned_results = []

        # 1. 날짜별 위치 스캔
        date_matches = list(re.finditer(r'(\d{1,2})\s*월\s*(\d{1,2})\s*일', normalized_text))

        for i in range(len(date_matches)):
            d_match = date_matches[i]
            month = int(d_match.group(1))
            day = int(d_match.group(2))
            event_date = f"{year_str}-{month:02d}-{day:02d}"

            start_idx = d_match.end()
            end_idx = date_matches[i+1].start() if i + 1 < len(date_matches) else len(normalized_text)
            section_text = normalized_text[start_idx:end_idx]

            # 2. 지정된 진짜 배 이름(`VALID_SHIPS`) 위치만 스캔
            ship_pattern = r'(' + '|'.join(VALID_SHIPS) + r')'
            ship_matches = list(re.finditer(ship_pattern, section_text))

            for j in range(len(ship_matches)):
                s_match = ship_matches[j]
                ship_name = s_match.group(1)

                s_start = s_match.end()
                s_end = ship_matches[j+1].start() if j + 1 < len(ship_matches) else len(section_text)
                ship_block = section_text[s_start:s_end]

                # 어종 정밀 추출 ("어종 : 주꾸미,갑오징어 / 루어" -> "주꾸미,갑오징어")
                title = "출항 일정"
                fish_match = re.search(r'어종\s*[:\s]*([^/|\n\r<]+)', ship_block)
                if fish_match:
                    raw_title = fish_match.group(1).strip()
                    # 불필요한 부가 텍스트 제거
                    title = raw_title.split('운항시간')[0].split('예약')[0].strip()

                # 남은 자리 추출
                rem_seat = 0
                rem_match = re.search(r'남은자리\s*[:\s]*(\d+)', ship_block) or re.search(r'(\d+)\s*명\s*남음', ship_block)
                if rem_match:
                    rem_seat = int(rem_match.group(1))

                # 정원 추출
                max_seat = 0
                max_match = re.search(r'정원\s*[:\s]*(\d+)', ship_block) or re.search(r'(\d+)\s*명\s*정원', ship_block) or re.search(r'(\d+)\s*명\s*예약', ship_block)
                if max_match:
                    max_seat = int(max_match.group(1))

                is_closed = '예약마감' in ship_block or '마감' in ship_block

                cleaned_results.append({
                    "subdomain": subdomain,
                    "ship_name": ship_name,
                    "event_date": event_date,
                    "title": title or "출항 일정",
                    "max_seat": max_seat if max_seat > 0 else (20 if "뉴항구" in ship_name else 11),
                    "rem_seat": 0 if is_closed else rem_seat,
                    "ready": not is_closed and rem_seat > 0,
                    "booking_url": target_url
                })

        # 중복 정제
        seen = set()
        unique_results = []
        for item in cleaned_results:
            key = (item["event_date"], item["ship_name"])
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
