import os
import time
import json
import gspread
from datetime import datetime
from playwright.sync_api import sync_playwright
from google.oauth2.service_account import Credentials

SHEET_ID = os.environ.get("GOOGLE_SHEETS_ID")
CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS")

TIER_GROUPS = {
    "저티어": ["Bronze", "Silver", "Gold"],
    "중티어": ["Platinum", "Diamond"],
    "고티어": ["Master", "GrandmasterAndChampion"]
}

ROLES = ["Tank", "Damage", "Support"]
ROLE_KR = {"Tank": "탱커", "Damage": "딜러", "Support": "서포터"}

def get_credentials():
    creds_dict = json.loads(CREDENTIALS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def scrape_tier_data(page, tier, role):
    url = f"https://overwatch.blizzard.com/ko-kr/rates/?input=PC&map=all-maps&region=Asia&role={role}&rq=1&tier={tier}"
    page.goto(url)
    
    # 데이터 로딩 대기
    page.wait_for_timeout(5000)
    
    data = []
    
    try:
        # 페이지 전체 텍스트 추출 후 파싱
        content = page.content()
        
        # 테이블 행 찾기
        rows = page.query_selector_all("table tbody tr")
        
        if not rows:
            # 다른 셀렉터 시도
            rows = page.query_selector_all(".stats-table tr")
        
        if not rows:
            # 카드 형태 시도
            rows = page.query_selector_all("[class*='hero-row'], [class*='HeroRow'], [class*='stats-row']")
        
        print(f"  → 찾은 행 수: {len(rows)}")
        
        for row in rows:
            try:
                cells = row.query_selector_all("td")
                if len(cells) < 2:
                    continue
                
                texts = [cell.inner_text().strip() for cell in cells]
                print(f"  → 셀 내용: {texts}")
                
                name = texts[0]
                
                # % 기호 포함된 셀 찾기
                rates = [t.replace("%", "").strip() for t in texts if "%" in t and t != "--"]
                
                if len(rates) < 2:
                    continue
                
                pickrate = float(rates[0])
                winrate = float(rates[1])
                
                if name and pickrate and winrate:
                    data.append({"영웅": name, "승률": winrate, "픽률": pickrate})
                    
            except Exception as e:
                print(f"  → 행 파싱 오류: {e}")
                continue
                
    except Exception as e:
        print(f"  → 수집 오류: {e}")
    
    return data

def calculate_scores(heroes):
    if not heroes:
        return []
    
    avg_pickrate = sum(h["픽률"] for h in heroes) / len(heroes)
    
    for hero in heroes:
        winrate_score = (hero["승률"] - 50) * 0.6
        pickrate_score = (hero["픽률"] / avg_pickrate) * 0.4
        hero["점수"] = round(winrate_score + pickrate_score, 3)
    
    heroes.sort(key=lambda x: x["점수"], reverse=True)
    
    total = len(heroes)
    for i, hero in enumerate(heroes):
        rank_pct = (i / total) * 100
        if rank_pct < 10:
            hero["티어"] = "S"
        elif rank_pct < 30:
            hero["티어"] = "A"
        elif rank_pct < 60:
            hero["티어"] = "B"
        elif rank_pct < 80:
            hero["티어"] = "C"
        else:
            hero["티어"] = "D"
    
    return heroes

def update_sheets(gc, all_data, today):
    sh = gc.open_by_key(SHEET_ID)
    
    for group_name in TIER_GROUPS:
        for role in ROLES:
            sheet_name = f"{group_name}_{ROLE_KR[role]}"
            
            try:
                worksheet = sh.worksheet(sheet_name)
            except:
                worksheet = sh.add_worksheet(title=sheet_name, rows=200, cols=10)
                worksheet.append_row(["날짜", "영웅", "승률(%)", "픽률(%)", "점수", "티어"])
            
            heroes = all_data.get(f"{group_name}_{role}", [])
            if not heroes:
                print(f"  → {sheet_name} 데이터 없음, 건너뜀")
                continue
            
            for h in heroes:
                worksheet.append_row([today, h["영웅"], h["승률"], h["픽률"], h["점수"], h["티어"]])
            
            print(f"  → {sheet_name} {len(heroes)}개 저장 완료")
            time.sleep(1)

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    gc = get_credentials()
    all_data = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        for group_name, tiers in TIER_GROUPS.items():
            for role in ROLES:
                combined = []
                
                for tier in tiers:
                    print(f"수집 중: {group_name} - {ROLE_KR[role]} - {tier}")
                    data = scrape_tier_data(page, tier, role)
                    print(f"  → 수집된 영웅 수: {len(data)}")
                    combined.extend(data)
                    time.sleep(2)
                
                hero_dict = {}
                for h in combined:
                    if h["영웅"] not in hero_dict:
                        hero_dict[h["영웅"]] = []
                    hero_dict[h["영웅"]].append(h)
                
                averaged = []
                for name, entries in hero_dict.items():
                    avg_win = sum(e["승률"] for e in entries) / len(entries)
                    avg_pick = sum(e["픽률"] for e in entries) / len(entries)
                    averaged.append({"영웅": name, "승률": round(avg_win, 2), "픽률": round(avg_pick, 2)})
                
                scored = calculate_scores(averaged)
                all_data[f"{group_name}_{role}"] = scored
        
        browser.close()
    
    update_sheets(gc, all_data, today)
    print("완료!")

if __name__ == "__main__":
    main()
