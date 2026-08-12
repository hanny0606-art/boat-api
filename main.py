from fastapi import FastAPI, HTTPException
from playwright.async_api import async_playwright
import re
import asyncio
import uvicorn

app = FastAPI()

@app.get("/api/v1/reservations")
async def get_live_reservations(subdomain: str = "seojin", yyyymm: str = "202608"):
    """
    Headless Chrome 브라우저를 백그라운드에서 직접 실행하여 
    자바스크립트가 완성한 화면의 어종, 남은자리, 예약 상태를 100% 실시간 렌더링 후 수집합니다.
    """
    target_url = f"https://{subdomain}.sunsang24.com/?yyyymm={yyyymm}"
    
    async with async_playwright() as p:
        # headless 브라우저 실행 (서버 자원 최소화 설정)
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # 페이지 이동 및 자바스크립트 AJAX 데이터 로딩 대기
            await page.goto(target_url, wait_until="networkidle", timeout=15000)
            await asyncio.sleep(1.5)  # 추가 안정 대기
            
            # 화면의 모든 달력 셀 / 일정 컨테이너 탐색
            schedule_elements = await page.query_selector_all("td, div.day, div.schedule, article")
            
            cleaned_results = []
            
            for el in schedule_elements:
                text = await el.inner_text()
                if not text or ("남은자리" not in text and "바로예약" not in text and "어종" not in text):
                    continue
                
                # 1. 날짜 추출 (M월 D일 또는 D일)
                year_str = yyyymm[:4]
                month_str = yyyymm[4:6]
                date_str = ""
                
                m_md = re.search(r'(\d{1,2})월\s*(\d{1,2})일', text)
                m_d = re.search(r'\b([1-9]|[12][0-9]|3[01])일\b', text)
                
                if m_md:
                    date_str = f"{year_str}-{int(m_md.group(1)):02d}-{int(m_md.group(2)):02d}"
                elif m_d:
                    date_str = f"{year_str}-{month_str}-{int(m_d.group(1)):02d}"
                
                # 2. 남은 자릿수 추출
                rem_seat = 0
                m_rem = re.search(r'남은자리\s*[:\s]*(\d+)명?', text) or re.search(r'(\d+)명\s*남음', text)
                if m_rem:
                    rem_seat = int(m_rem.group(1))
                
                # 3. 어종 / 일정 제목 추출
                title = ""
                m_bracket = re.search(r'《\s*([^》]+)\s*》', text)
                m_fish = re.search(r'어종\s*:\s*([^\n\r]+)', text)
                m_notice = re.search(r'공지사항\s*:\s*([^\n\r]+)', text)
                
                if m_bracket:
                    title = m_bracket.group(1).strip()
                elif m_fish:
                    title = m_fish.group(1).strip()
                elif m_notice:
                    title = m_notice.group(1).strip()
                else:
                    lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 1]
                    title = " / ".join(lines[:2])
                
                # 4. 배 이름 추출
                ship_name = "신출항호"
                m_ship = re.search(r'([가-힣A-Za-z0-9]+호)', text)
                if m_ship:
                    ship_name = m_ship.group(1)

                if date_str and (rem_seat > 0 or title):
                    cleaned_results.append({
                        "ship_name": ship_name,
                        "event_date": date_str,
                        "title": title,
                        "rem_seat": rem_seat,
                        "ready": rem_seat > 0 or ("마감" not in text),
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

            await browser.close()

            return {
                "status": "success",
                "subdomain": subdomain,
                "yyyymm": yyyymm,
                "count": len(unique_results),
                "data": unique_results
            }

        except Exception as e:
            await browser.close()
            return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
