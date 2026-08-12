from fastapi import FastAPI, HTTPException
from supabase import create_client, Client
import uvicorn

app = FastAPI()

# 전달해주신 Supabase 프로젝트 URL 및 Secret Key 적용
SUPABASE_URL = "https://izlyzbiriawqibxhgxnm.supabase.co"
SUPABASE_KEY = "sb_secret_SuMvCM8l5XF3NYSieKcmdw_wkenExmw"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.get("/api/v1/reservations")
def get_reservations_from_db(
    subdomain: str = "daebak", 
    start_date: str = None, 
    end_date: str = None
):
    try:
        query = supabase.table("ship_reservations").select("*").eq("subdomain", subdomain)
        
        if start_date:
            query = query.gte("event_date", start_date)
        if end_date:
            query = query.lte("event_date", end_date)

        response = query.order("event_date", desc=False).execute()
        data = response.data

        return {
            "status": "success",
            "subdomain": subdomain,
            "count": len(data),
            "data": data
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
