from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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

# 500 Internal Server Error 발생 시 서버가 죽지 않고 JSON 에러 메시지를 내보내도록 설정
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=200,
        content={"status": "error", "message": f"서버 내부 오류: {str(exc)}"}
    )

@app.get("/api/v1/reservations")
def get_live_reservations(subdomain: str = "seojin", yyyymm: str = "202608"):
    target_url = f"https://{subdomain}.sunsang24.com/?yyyymm={yyyymm}"
    
    try:
        res = requests.get(target_url, headers=HEADERS, timeout=8)
        if res.status_code != 200:
            return {"status": "error", "message": f"선사 웹페이지 응답 에러 (코드: {res.status_code})"}
            
        html = res.text
        soup = BeautifulSoup(html, 'html.parser')
        
        cleaned_results = []
        year_str = yyyymm[:4]
        month_str = yyyymm[4:6]

        # 1. HTML 내 스크립트/글자 영역에서 날짜 및 출항 키워드 추출
        # 선상24 페이지 내 텍스트 덩어리 수집
        text_nodes = soup.find_all(['td', 'tr', 'div', 'li'])
        
        for node in text_nodes:
            text = node.get_text(separator=' ', strip=True)
            if not text or ("남은자리" not in text and "바로예약" not in text and "출조" not in text):
                continue
            
            # 날짜 추출 (8월 17일, 17일 등)
            m_md = re.search(r'(\d{1,2})월\s*(\d{1,2})일', text)
            m_d = re.search(r'\b([1-9]|[12][0-9]|3[01])일\b', text)
            
            event_date = ""
            if m_md:
                event_date = f"{year_str}-{int(m_md.group(1)):02d}-{int(m_md.group(2)):02d}"
            elif m_d:
                event_date = f"{year_str}-{month_str}-{int(m_d.group(1)):02d}"
                
            # 남은 자리 추출
            rem_seat = 0
            m_rem = re.search(r'남은자리\s*[:\s]*(\d+)명?', text) or re.search(r'(\d+)명\s*남음', text) or re.search(r'예약/(\d+)명', text)
            if m_rem:
                rem_seat = int(m_rem.group(1))

            # 어종 / 일정 제목 추출
            title = ""
            m_bracket = re.search(r'《\s*([^》]+)\s*》', text)
            m_fish = re.search(r'어종\s*:\s*([^\n/]+)', text)
            if m_bracket:
                title = m_bracket.group(1).strip()
            elif m_fish:
                title = m_fish.group(1).strip()
            else:
                # 키워드가 포함된 문구 정제
                lines = [line.strip() for line in text.split(' ') if len(line.strip()) > 1]
                title = " ".join(lines[:3])

            ship_name = "신출항호"
            m_ship = re.search(r'([가-힣A-Za-z0-9]+호)', text)
            if m_ship:
                ship_name = m_ship.group(1)

            if event_date and (rem_seat > 0 or title):
                cleaned_results.append({
                    "ship_name": ship_name,
                    "event_date": event_date,
                    "title": title[:40],
                    "rem_seat": rem_seat,
                    "ready": rem_seat > 0,
                    "booking_url": target_url
                })

        # 중복 항목 정제
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
