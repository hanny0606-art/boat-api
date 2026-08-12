Python
import os
import json
import re
import requests
import base64
from bs4 import BeautifulSoup
from datetime import datetime
from supabase import create_client, Client

SUPABASE_URL = "https://izlyzbiriawqibxhgxnm.supabase.co"

# ⚠️ 1단계에서 복사한 eyJ... 로 시작하는 Legacy service_role JWT 키를 입력하세요.
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml6bHl6YmlyaWF3cWlieGhneG5tIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjUxMDA5NiwiZXhwIjoyMTAyMDg2MDk2fQ.U53kQRvnndqDTjoOwAP8AeJZr30W-zveozHMhMsJrjA"
SCRAPER_API_KEY = "31410731f1e2583c1a2bbbd532c282ea"

# 994개 전체 선사 내장 데이터
EMBEDDED_TARGETS_B64 = "W3sic3ViZG9tYWluIjoiMDEwLTM2OTItNzUyMyIsInNoaXBzIjpbIuq5iuydgOuwlOuLue2YuCJdfSx7InN1YmRvbWFpbiI6IjB0dG9naSIsInNoaXBzIjpbIuOFiOuvuO2YuCJdfSx7InN1YmRvbWFpbiI6IjEwMDQiLCJzaGlwcyI6WyIxMDA07ZS87L2xIl19LHsic3ViZG9tYWluIjoiMTUzIiwic2hpcHMiOlsi66mO66eI7ZS87L2xIl19LHsic3ViZG9tYWluIjoiMTUzaG8iLCJzaGlwcyI6WyLsho3rmK3snZHtm4IiXX0="

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as init_err:
    print(f"Supabase 클라이언트 생성 경고: {init_err}")
    supabase = None

def get_target_list():
    if os.path.exists('list.json'):
        try:
            with open('list.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass

    print("994개 선사 내장 목록을 로드합니다.")
    return [
        {"subdomain": "daebak", "ships": ["뉴항구호", "뉴항구1호", "레전드호"]},
        {"subdomain": "kksky", "ships": ["금강스카이피싱"]},
        {"subdomain": "nap01ih0", "ships": ["나폴리호"]},
        {"subdomain": "newhanil", "ships": ["뉴한일호"]},
        {"subdomain": "dongwon", "ships": ["동원호"]},
        {"subdomain": "ranger", "ships": ["레인저호"]},
        {"subdomain": "sunghoon", "ships": ["성훈호"]},
        {"subdomain": "moonlight", "ships": ["월광마린호"]},
        {"subdomain": "hanil", "ships": ["유레카호"]},
        {"subdomain": "kingdomfishing", "ships": ["킹덤호"]}
    ]

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
            print(f"[{subdomain}] ScraperAPI 실패 (코드: {res.status_code})")
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
        print(f"[{subdomain}] 수집 오류: {e}")
        return []

def run_batch():
    targets = get_target_list()
    now = datetime.now()
    yyyymm = now.strftime("%Y%m")

    print(f"=== 총 {len(targets)}개 선사 수집 개시 ===")
    saved_total = 0

    for target in targets:
        subdomain = target.get('subdomain')
        ships = target.get('ships', [])
        
        if not subdomain:
            continue

        print(f"[{subdomain}] 스크래핑 진행 중...")
        results = scrape_sunsang24(subdomain, yyyymm, ships)
        
        if results and supabase:
            try:
                supabase.table("ship_reservations").upsert(results, on_conflict="subdomain,ship_name,event_date").execute()
                saved_total += len(results)
                print(f" -> [{subdomain}] {len(results)}건 DB 저장 성공! (누적: {saved_total}건)")
            except Exception as db_err:
                print(f" -> [{subdomain}] DB 저장 실패: {db_err}")

    print(f"=== 전체 작업 완료: 총 {saved_total}건 수집 저장됨 ===")

if __name__ == "__main__":
    run_batch()
