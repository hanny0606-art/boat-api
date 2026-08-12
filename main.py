from fastapi import FastAPI, HTTPException
import requests
import json
import re
import uvicorn

app = FastAPI()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

EXCLUDE_KEYWORDS = ["이벤트알림", "공지사항", "조황정보", "전체보기", "환불안내", "팝업"]

@app.get("/api/v1/reservations")
def get_live_reservations(subdomain: str = "daebak", yyyymm: str = "202609"):
    target_url = f"https://{subdomain}.sunsang24.com/ship/schedule_fleet/{yyyymm}"
    
    try:
        res = requests.get(target_url, headers=HEADERS, timeout=8)
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail="선사 페이지 로딩 실패")
            
        html_text = res.text
        
        # 1. <script> 태그 내부의 JSON 배열/객체 패턴 스캔
        json_matches = re.findall(r'(\[\s*\{.*?\}\s*\]|\{\s*["\'](?:schedules|events|data)["\']\s*:.*?\})', html_text, re.DOTALL)
        
        extracted_items = []
        
        for raw_json in json_matches:
            try:
                # 싱글 쿼테이션 처리 및 JSON 변환
                valid_json_str = re.sub(r"'", '"', raw_json)
                parsed = json.loads(valid_json_str)
                
                if isinstance(parsed, dict):
                    parsed = parsed.get("data") or parsed.get("schedules") or parsed.get("events") or []
                
                if isinstance(parsed, list):
                    for obj in parsed:
                        if isinstance(obj, dict) and ("sdate" in obj or "event_sdate" in obj or "ship_name" in obj):
                            extracted_items.append(obj)
            except Exception:
                continue

        # 2. JSON 파싱 실패 시 HTML 내 텍스트 구문 정밀 추적 (백업)
        cleaned_results = []
        year_str = yyyymm[:4]
        month_str = yyyymm[4:6]

        if extracted_items:
            for item in extracted_items:
                title = item.get("title") or item.get("fish_type") or item.get("subject") or ""
                if any(kw in title for kw in EXCLUDE_KEYWORDS):
                    continue

                sdate = item.get("sdate") or item.get("event_sdate") or ""
                rem_seat = int(item.get("rem_cnt") or item.get("left_seat") or item.get("person_rem") or 0)
                max_seat = int(item.get("max_cnt") or item.get("person_limit") or item.get("total_seat") or 0)
                price = int(item.get("price") or item.get("fee") or 0)

                cleaned_results.append({
                    "schedule_no": item.get("ship_schedule_no") or item.get("no") or item.get("id"),
                    "subdomain": subdomain,
                    "ship_name": item.get("ship_name") or item.get("ship", {}).get("name") or "선박",
                    "event_date": sdate,
                    "title": title,
                    "max_seat": max_seat,
                    "rem_seat": rem_seat,
                    "price": price,
                    "ready": rem_seat > 0 or bool(title),
                    "booking_url": target_url
                })
        else:
            # 원본 HTML에서 스케줄 패턴 추출
            pattern = re.compile(
                r'([가-힣A-Za-z0-9]+호).*?(\d{1,2}월\s*\d{1,2}일).*?어종\s*[:\s]*([^/\n\r<]+)', 
                re.DOTALL
            )
            for match in pattern.finditer(html_text):
                ship_name = match.group(1)
                date_raw = match.group(2)
                title = match.group(3).strip()

                m_md = re.search(r'(\d{1,2})월\s*(\d{1,2})일', date_raw)
                event_date = f"{year_str}-{int(m_md.group(1)):02d}-{int(m_md.group(2)):02d}" if m_md else f"{year_str}-{month_str}-01"

                cleaned_results.append({
                    "schedule_no": "",
                    "subdomain": subdomain,
                    "ship_name": ship_name,
                    "event_date": event_date,
                    "title": title,
                    "max_seat": 0,
                    "rem_seat": 0,
                    "ready": True,
                    "booking_url": target_url
                })

        # 중복 제거
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
            "data": unique_results,
            "debug_sample": html_text[html_text.find("schedule"):html_text.find("schedule")+300] if not unique_results else ""
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
