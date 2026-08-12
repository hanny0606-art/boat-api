import pandas as pd
import urllib.parse
import json

df = pd.read_excel('list.xlsx')
sunsang24_df = df[df['platform'].str.contains('sunsang24', case=False, na=False)].copy()

def extract_subdomain(url):
    if not isinstance(url, str):
        return None
    url = url.strip()
    parsed = urllib.parse.urlparse(url)
    netloc = parsed.netloc if parsed.netloc else parsed.path.split('/')[0]
    parts = netloc.split('.')
    if len(parts) >= 3 and 'sunsang24' in netloc:
        return parts[0].lower()
    return None

sunsang24_df['subdomain'] = sunsang24_df['base_url'].apply(extract_subdomain)
sunsang24_df = sunsang24_df.dropna(subset=['subdomain'])

grouped = sunsang24_df.groupby('subdomain')['site_name'].apply(lambda x: list(set(x.dropna()))).reset_index()

targets = []
for idx, row in grouped.iterrows():
    targets.append({
        "subdomain": row['subdomain'],
        "ships": row['site_name']
    })

with open('list.json', 'w', encoding='utf-8') as f:
    json.dump(targets, f, ensure_ascii=False, indent=2)

print(f"총 {len(targets)}개 선사 추출 완료 ➔ list.json 저장 완료!")
