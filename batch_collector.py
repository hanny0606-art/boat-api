import os
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from supabase import create_client, Client

SUPABASE_URL = "https://izlyzbiriawqibxhgxnm.supabase.co"
SUPABASE_KEY = "sb_secret_SuMvCM8l5XF3NYSieKcmdw_wkenExmw"
SCRAPER_API_KEY = "31410731f1e2583c1a2bbbd532c282ea"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def scrape_sunsang24(subdomain: str, yyyymm: str, valid_ships: list):
    target_url = f"https://{subdomain}.sunsang24.com/ship/schedule_fleet/{yyyymm}"
    scraper_url = "https://api.scraperapi.com"
    params = {
        'api_key': SCRAPER_API_KEY,
        'url': target_url,
        'render': 'true',
        'country_code': 'kr'
    }

    try:
        res = requests.get(scraper_url, params=params, timeout=60)
        if res.status_code != 200:
            return []

        soup = BeautifulSoup(res.text, 'html.parser')
        raw_text = soup.get_text(separator=' ', strip=True)
        normalized_text = re.sub(r'\s+', ' ', raw_text)

        year_str = yyyymm[:4]
        cleaned_results = []

        date_matches = list(re.finditer(r'(\d{1,2})\s*월\s*(\d{1,2})\s*일', normalized_text))

        for i in range(len(date_matches)):
            d_match = date_matches[i]
            month = int(d_match.group(1))
            day = int(d_match.group(2))
            event_date = f"{year_str}-{month:02d}-{day:02d}"

            start_idx = d_match.end()
            end_idx = date_matches[i+1].start() if i + 1 < len(date_matches) else len(normalized_text)
            section_text = normalized_text[start_idx:end_idx]

            if valid_ships and len(valid_ships) > 0:
                ship_pattern = r'(' + '|'.join([re.escape(s) for s in valid_ships]) + r')'
            else:
                ship_pattern = r'([가-힣A-Za-z0-9]+호)'

            ship_matches = list(re.finditer(ship_pattern, section_text))

            for j in range(len(ship_matches)):
                s_match = ship_matches[j]
                ship_name = s_match.group(1)

                s_start = s_match.end()
                s_end = ship_matches[j+1].start() if j + 1 < len(ship_matches) else len(section_text)
                ship_block = section_text[s_start:s_end]

                title = "출항 일정"
                fish_match = re.search(r'어종\s*[:\s]*([^/|\n\r<]+)', ship_block)
                if fish_match:
                    raw_title = fish_match.group(1).strip()
                    title = raw_title.split('운항시간')[0].split('예약')[0].strip()

                rem_seat = 0
                rem_match = re.search(r'남은자리\s*[:\s]*(\d+)', ship_block) or re.search(r'(\d+)\s*명\s*남음', ship_block)
                if rem_match:
                    rem_seat = int(rem_match.group(1))

                max_seat = 0
                max_match = re.search(r'정원\s*[:\s]*(\d+)', ship_block) or re.search(r'(\d+)\s*명\s*정원', ship_block) or re.search(r'(\d+)\s*명\s*예약', ship_block)
                if max_match:
                    max_seat = int(max_match.group(1))

                is_closed = '예약마감' in ship_block or '마감' in ship_block

                cleaned_results.append({
                    "subdomain": subdomain,
                    "ship_name": ship_name,
                    "event_date": event_date,
                    "title": title or "출항 일정",
                    "max_seat": max_seat if max_seat > 0 else 20,
                    "rem_seat": 0 if is_closed else rem_seat,
                    "ready": not is_closed and rem_seat > 0,
                    "booking_url": target_url,
                    "updated_at": datetime.now().isoformat()
                })

        seen = set()
        unique_results = []
        for item in cleaned_results:
            key = (item["event_date"], item["ship_name"])
            if key not in seen:
                seen.add(key)
                unique_results.append(item)

        return unique_results
    except Exception as e:
        print(f"[{subdomain}] 에러 발생: {e}")
        return []

def run_batch():
    if not os.path.exists('list.json'):
        print("list.json 파일이 존재하지 않습니다.")
        return

    with open('list.json', 'r', encoding='utf-8') as f:
        targets = json.load(f)

    now = datetime.now()
    yyyymm = now.strftime("%Y%m")

    print(f"=== 총 {len(targets)}개 선사 데이터 수집 시작 ===")
    for target in targets:
        subdomain = target.get('subdomain')
        ships = target.get('ships', [])
        
        if not subdomain:
            continue

        print(f"[{subdomain}] 수집 진행 중...")
        results = scrape_sunsang24(subdomain, yyyymm, ships)
        
        if results:
            try:
                supabase.table("ship_reservations").upsert(results, on_conflict="subdomain,ship_name,event_date").execute()
                print(f" -> [{subdomain}] {len(results)}건 DB 저장 완료")
            except Exception as db_err:
                print(f" -> [{subdomain}] DB 저장 에러: {db_err}")

if __name__ == "__main__":
    run_batch()
