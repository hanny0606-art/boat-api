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
def get_live_reservations(
    subdomain: str = "seojin", 
    yyyymm: str = "202608",
    debug: bool = False
):
    target_url = f"https://{subdomain}.sunsang24.com/?yyyymm={yyyymm}"
    
    try:
        response = requests.get(target_url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="선사 메인 페이지 접속 실패")
            
        html_text = response.text
        soup = BeautifulSoup(html_text, 'html.parser')
        
        # '남은자리' 또는 '바로예약' 키워드가 포함된 HTML 요소 탐색
        target_elements = soup.find_all(lambda tag: tag.name in ['td', 'div', 'li', 'article'] and ('남은자리' in tag.get_text() or '바로예약' in tag.get_text()))
        
        cleaned_results = []
        raw_snippets = []

        year_str = yyyymm[:4]
        month_str = yyyymm[4:6]

        for el in target_elements:
            # 부모 컨테이너로 올라가서 해당 날짜/선박 전체 정보 영역 확보
            container = el
            for _ in range(3):
                if container.parent and container.parent.name in ['td', 'tr', 'div', 'li']:
                    container = container.parent
            
            text = container.get_text(separator=' ', strip=True)
            raw_snippets.append(text[:150])

            # 1. 날짜 추출 (YYYY-MM-DD 또는 M월 D일 또는 D일)
            date_str = ""
            m_full = re.search(r'(\d{4})[.-](\d{1,2})[.-](\d{1,2})', text)
            m_md = re.search(r'(\d{1,2})월\s*(\d{1,2})일', text)
            m_d = re.search(r'\b([1-9]|[12][0-9]|3[01])일\b', text)

            if m_full:
                date_str = f"{m_full.group(1)}-{int(m_full.group(2)):02d}-{int(m_full.group(3)):02d}"
            elif m_md:
                date_str = f"{year_str}-{int(m_md.group(1)):02d}-{int(m_md.group(2)):02d}"
            elif m_d:
                date_str = f"{year_str}-{month_str}-{int(m_d.group(1)):02d}"

            # 2. 남은 자릿수 추출
            rem_seat = 0
            m_rem = re.search(r'남은자리\s*[:\s]*(\d+)명?', text)
            if m_rem:
                rem_seat = int(m_rem.group(1))

            # 3. 어종 / 제목 추출
            title = ""
            m_bracket = re.search(r'《\s*([^》]+)\s*》', text)
            m_fish = re.search(r'어종\s*:\s*([^/|\n\r]+)', text)
            m_notice = re.search(r'공지사항\s*:\s*([^/|\n\r]+)', text)

            if m_bracket:
                title = m_bracket.group(1).strip()
            elif m_fish:
                title = m_fish.group(1).strip()
            elif m_notice:
                title = m_notice.group(1).strip()

            # 4. 선박명 추출
            ship_name = "신출항호"
            m_ship = re.search(r'([가-힣A-Za-z0-9]+호)', text)
            if m_ship:
                ship_name = m_ship.group(1)

            if date_str and (rem_seat > 0 or title):
                cleaned_results.append({
                    "ship_name": ship_name,
                    "event_date": date_str,
                    "title": title or "출항 일정",
                    "rem_seat": rem_seat,
                    "ready": rem_seat > 0,
                    "booking_url": target_url
                })

        # 날짜 및 선박 기준 중복 제거
        seen = set()
        unique_results = []
        for item in cleaned_results:
            key = (item["event_date"], item["ship_name"])
            if key not in seen:
                seen.add(key)
                unique_results.append(item)

        if debug:
            return {
                "status": "debug",
                "found_elements_count": len(target_elements),
                "snippets": raw_snippets[:10],
                "parsed_data": unique_results
            }

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
