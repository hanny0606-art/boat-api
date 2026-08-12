from fastapi import FastAPI, HTTPException
from supabase import create_client, Client
import uvicorn
from typing import Optional

app = FastAPI()

SUPABASE_URL = "https://izlyzbiriawqibxhgxnm.supabase.co"
SUPABASE_KEY = "sb_secret_SuMvCM8l5XF3NYSieKcmdw_wkenExmw"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 슬래시 유무와 관계없이 모두 매칭되도록 2개 경로 지정
@app.get("/api/v1/reservations")
@app.get("/api/v1/reservations/")
def get_reservations_from_db(
    subdomain: Optional[str] = None, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None
):
    try:
        query = supabase.table("ship_reservations").select("*")
        
        # 특정 subdomain을 지정했을 때만 필터링 (없으면 전체 994개 선사 조회)
        if subdomain:
            query = query.eq("subdomain", subdomain)
            
        if start_date:
            query = query.gte("event_date", start_date)
        if end_date:
            query = query.lte("event_date", end_date)

        response = query.order("event_date", desc=False).limit(10000).execute()
        data = response.data

        return {
            "status": "success",
            "filter_subdomain": subdomain if subdomain else "ALL_SHIPS",
            "total_count": len(data),
            "data": data
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
