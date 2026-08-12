from fastapi import FastAPI, HTTPException
from supabase import create_client, Client
import uvicorn
from typing import Optional

app = FastAPI()

SUPABASE_URL = "https://izlyzbiriawqibxhgxnm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml6bHl6YmlyaWF3cWlieGhneG5tIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjUxMDA5NiwiZXhwIjoyMTAyMDg2MDk2fQ.U53kQRvnndqDTjoOwAP8AeJZr30W-zveozHMhMsJrjA"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 기본 메인 주소 접속 시 상태 안내
@app.get("/")
def read_root():
    return {"status": "online", "message": "Boat API Server is running!"}

# 전체 선사 또는 특정 선사 조회 API
@app.get("/api/v1/reservations")
@app.get("/api/v1/reservations/")
def get_reservations_from_db(
    subdomain: Optional[str] = None, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None
):
    try:
        query = supabase.table("ship_reservations").select("*")
        
        # 특정 subdomain 지정 시 필터링 (미지정 시 전체 선사 조회)
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
