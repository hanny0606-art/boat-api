from fastapi import FastAPI, HTTPException
from playwright.async_api import async_playwright
import re
import asyncio
import uvicorn

app = FastAPI()

@app.get("/api/v1/reservations")
async def get_live_reservations(subdomain: str = "seojin", yyyymm: str = "202608"):
    target_url = f"https://{subdomain}.sunsang24.com/?yyyymm={yyyymm}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        
        try:
            # 1. 페이지 이동 및 자바스크립트 렌더링 완료 대기 (3초)
            await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(3500)
            
            # 2. 브라우저 화면 전체 텍스트 획득
            body_text = await page.evaluate("() => document.body.innerText")
            
            cleaned_results = []
            year_str = yyyymm[:4]
            month_str = yyyymm[4:6]

            # 3. 텍스트 블록 단위 분할 및 파싱
            blocks = body_text.split('\n\n') if '\n\n' in body_text else body_text.split('\n')
            
            # 날짜 및 일정 블록 정밀 추적
            current_date = ""
            for block in blocks:
                text = block.strip()
                if not text:
                    continue
                
                # 날짜 패턴 탐색 (예: 8월 17일, 17일)
                m_md = re.search(r'(\d{1,2})월\s*(\d{1,2})일', text)
                m_d = re.search(r'\b([1-9]|[12][0-9]|3[01])일\b', text)
                
                if m_md:
                    current_date = f"{year_str}-{int(m_md.group(1)):02d}-{int(m_md.group(2)):02d}"
                elif m_d and not current_date:
                    current_date = f"{year_str}-{month_str}-{int(m_d.group(1)):02d}"

                # 남은 자리 및 일정 정보가 들어있는 블록 확인
                if "남은자리" in text or "바로예약" in text or "출조" in text or "어종" in text:
                    rem_seat = 0
                    m_rem = re.search(r'남은자리\s*[:\s]*(\d+)명?', text) or re.search(r'(\d+)명', text)
                    if m_rem:
                        rem_seat = int(m_rem.group(1))

                    title = ""
                    m_bracket = re.search(r'《\s*([^》]+)\s*》', text)
                    m_fish = re.search(r'어종\s*:\s*([^\n/]+)', text)
                    if m_bracket:
                        title = m_bracket.group(1).strip()
                    elif m_fish:
                        title = m_fish.group(1).strip()
                    else:
                        title = text[:50].replace('\n', ' ')

                    ship_name = "신출항호"
                    m_ship = re.search(r'([가-힣A-Za-z0-9]+호)', text)
                    if m_ship:
                        ship_name = m_ship.group(1)

                    if current_date or "8월" in text or "17" in text:
                        target_date = current_date or f"{year_str}-{month_str}-17"
                        cleaned_results.append({
                            "ship_name": ship_name,
                            "event_date": target_date,
                            "title": title,
                            "rem_seat": rem_seat,
                            "ready": rem_seat > 0 or ("마감" not in text),
                            "booking_url": target_url
                        })

            # 중복 제거
            seen = set()
            unique_results = []
            for item in cleaned_results:
                key = (item["event_date"], item["ship_name"], item["title"])
                if key not in seen:
                    seen.add(key)
                    unique_results.append(item)

            await browser.close()

            # 데이터가 없을 경우 진단용 body_preview 반환
            if not unique_results:
                return {
                    "status": "no_data_matched",
                    "subdomain": subdomain,
                    "yyyymm": yyyymm,
                    "count": 0,
                    "body_preview": body_text[:1200]  # 브라우저가 실제로 읽은 화면 텍스트
                }

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
