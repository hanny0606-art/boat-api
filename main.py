from fastapi import FastAPI, HTTPException
import requests
import re
import uvicorn

app = FastAPI()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
}

@app.get("/api/v1/reservations")
def get_live_reservations(subdomain: str = "seojin", yyyymm: str = "202608", debug: bool = False):
    target_url = f"https://{subdomain}.sunsang24.com/?yyyymm={yyyymm}"
    
    try:
        response = requests.get(target_url, headers=HEADERS, timeout=8)
        html_content = response.text
        
        # 선상24 자바스크립트 내 API 호출 URL 패턴 자동 추적
        api_urls = re.findall(r'["\'](/[^"\']*(?:event|schedule|list|ajax)[^"\']*)["\']', html_content, re.IGNORECASE)
        
        if debug:
            return {
                "status": "debug",
                "subdomain": subdomain,
                "found_api_endpoints": list(set(api_urls))[:15],
                "html_snippet": html_content[:500]
            }

        return {
            "status": "success",
            "message": "debug=true 링크를 입력해 JS API 주소를 스캔하세요.",
            "debug_url": f"https://boat-api-zu7i.onrender.com/api/v1/reservations?subdomain={subdomain}&yyyymm={yyyymm}&debug=true"
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
