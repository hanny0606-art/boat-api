Python
from fastapi import FastAPI, HTTPException
import requests
from bs4 import BeautifulSoup
import re
import uvicorn

app = FastAPI()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

@app.get("/api/v1/reservations")
def get_live_reservations(subdomain: str = "seojin", yyyymm: str = "202608"):
    """
    선상24 웹 페이지 HTML을 직접 읽어와
    달력 내 출항 일정, 어종, 남은 자릿수, 예약을 파싱합니다.
    """
    year = yyyymm[:4]
    month = yyyymm[4:6].zfill(2)
    
    # 선상24 달력 페이지 URL
    target_url = f"https://{subdomain}.sunsang24.com/"
    params = {"yyyymm": f"{year}{month}"}
    
    try:
        response = requests.get(target_url, params=params, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="선사 페이지 접속 실패")
            
        soup = BeautifulSoup(response.text, 'html.parser')
        cleaned_results = []
        
        # 달력 내 날짜별 셀 탐색
        # 선상24 달력 구조 내 일별 컨테이너 추출
        day_cells = soup.find_all(['td', 'div'], class_=re.compile(r'day|date|schedule|cal', re.I))
        
        for cell in day_cells:
            cell_text = cell.get_text(separator=' ', strip=True)
            if not cell_text:
                continue

            # 날짜 추출 (1~31)
            date_match = re.search(r'\b([1-9]|[12][0-9]|3[01])일\b', cell_text)
            if not date_match:
                continue
                
            day_num = int(date_match.group(1))
            formatted_date = f"{year}-{month}-{day_num:02d}"
            
            # 남은 자리 추출 (예: "남은자리 15명" 또는 "15명")
            rem_seat = 0
            rem_match = re.search(r'남은자리\s*[:\s]*(\d+)명?', cell_text) or re.search(r'잔여\s*[:\s]*(\d+)명?', cell_text)
            if rem_match:
                rem_seat = int(rem_match.group(1))
                
            # 어종 / 제목 추출
            title = ""
            fish_match = re.search(r'어종\s*:\s*([^/|\n]+)', cell_text) or re.search(r'《\s*([^》]+)\s*》', cell_text)
            if fish_match:
                title = fish_match.group(1).strip()
            elif "남은자리" in cell_text:
                # 텍스트 내에서 주요 키워드 추출
                lines = [l.strip() for l in cell.stripped_strings if len(l.strip()) > 2]
                title = " / ".join(lines[:2])
                
            if rem_seat > 0 or title:
                cleaned_results.append({
                    "subdomain": subdomain,
                    "event_date": formatted_date,
                    "title": title or "출항 일정",
                    "rem_seat": rem_seat,
                    "ready": rem_seat > 0,
                    "booking_url": target_url,
                    "raw_text": cell_text[:100]  # 파싱 상태 확인용 샘플
                })
        
        # 날짜순 중복 제거 및 정렬
        seen_dates = set()
        unique_results = []
        for r in cleaned_results:
            if r["event_date"] not in seen_dates:
                seen_dates.add(r["event_date"])
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
