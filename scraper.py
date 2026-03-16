import os
import time
import csv
import subprocess
from datetime import datetime
from playwright.sync_api import sync_playwright

TIER_GROUPS = {
    "저티어": "Bronze",
    "중티어": "Platinum",
    "고티어": "Master"
}

ROLES = {
    "Tank": "탱커",
    "Damage": "딜러",
    "Support": "힐러"
}

HERO_SUBROLES = {
    # 개시자
    "D.Va": "개시자", "레킹볼": "개시자", "윈스턴": "개시자", "둠피스트": "개시자",
    # 투사
    "마우가": "투사", "오리사": "투사", "로드호그": "투사", "자리야": "투사",
    # 강건한 자
    "라마트라": "강건한 자", "라인하르트": "강건한 자", "도미나": "강건한 자",
    "해저드": "강건한 자", "정커퀸": "강건한 자", "시그마": "강건한 자",
    # 전문가
    "바스티온": "전문가", "엠레": "전문가", "정크랫": "전문가",
    "메이": "전문가", "솔저: 76": "전문가",
    # 수색가
    "에코": "수색가", "프레야": "수색가", "파라": "수색가", "솜브라": "수색가",
    # 측면 공격가
    "겐지": "측면 공격가", "안란": "측면 공격가", "리퍼": "측면 공격가",
    "트레이서": "측면 공격가", "벤데타": "측면 공격가", "벤처": "측면 공격가",
    # 명사수
    "애쉬": "명사수", "캐서디": "명사수", "한조": "명사수",
    "소전": "명사수", "위도우메이커": "명사수",
    # 전술가
    "아나": "전술가", "바티스트": "전술가", "제트팩 캣": "전술가",
    "루시우": "전술가", "젠야타": "전술가",
    # 의무관
    "키리코": "의무관", "라이프위버": "의무관", "메르시": "의무관", "모이라": "의무관",
    # 생존왕
    "브리기테": "생존왕", "일리아리": "생존왕", "주노": "생존왕",
    "미즈키": "생존왕", "우양": "생존왕",
}

def scrape_data(page, tier, role):
    url = f"https://overwatch.blizzard.com/ko-kr/rates/?input=PC&map=all-maps&region=Asia&role={role}&rq=2&tier={tier}"
    page.goto(url)
    page.wait_for_timeout(5000)

    data = []

    try:
        body_text = page.inner_text("body")
        lines = body_text.split("\n")
        lines = [l.strip() for l in lines if l.strip()]

        i = 0
        while i < len(lines):
            if i + 2 < len(lines):
                next1 = lines[i + 1]
                next2 = lines[i + 2]

                if "%" in next1 and "%" in next2:
                    try:
                        name = lines[i]
                        winrate = float(next1.replace("%", "").strip())
                        pickrate = float(next2.replace("%", "").strip())

                        if name and 0 < pickrate < 100 and 0 < winrate < 100:
                            data.append({
                                "영웅": name,
                                "승률": winrate,
                                "픽률": pickrate,
                                "서브롤": HERO_SUBROLES.get(name, "미분류")
                            })
                            i += 3
                            continue
                    except:
                        pass
            i += 1

    except Exception as e:
        print(f"  → 오류: {e}")

    return data

def calculate_scores(heroes):
    if not heroes:
        return []

    avg_pickrate = sum(h["픽률"] for h in heroes) / len(heroes)

    for hero in heroes:
        winrate_score = (hero["승률"] - 50) * 0.4
        pickrate_score = (hero["픽률"] / avg_pickrate) * 0.6
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

def save_csv(all_data, timestamp):
    os.makedirs("data", exist_ok=True)
    filepath = f"data/{timestamp}.csv"

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["날짜", "랭크그룹", "메인역할", "서브롤", "영웅", "승률(%)", "픽률(%)", "점수", "티어"])

        for key, heroes in all_data.items():
            group_name, role_kr = key.split("_")
            for h in heroes:
                writer.writerow([
                    timestamp,
                    group_name,
                    role_kr,
                    h["서브롤"],
                    h["영웅"],
                    h["승률"],
                    h["픽률"],
                    h["점수"],
                    h["티어"]
                ])

    print(f"  → CSV 저장 완료: {filepath}")
    return filepath

def git_push(timestamp):
    subprocess.run(["git", "config", "user.email", "action@github.com"])
    subprocess.run(["git", "config", "user.name", "GitHub Action"])
    subprocess.run(["git", "add", "data/"])
    subprocess.run(["git", "commit", "-m", f"데이터 업데이트: {timestamp}"])
    subprocess.run(["git", "push"])
    print("  → GitHub 업로드 완료!")

def main():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H")
    all_data = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for group_name, tier in TIER_GROUPS.items():
            for role_en, role_kr in ROLES.items():
                print(f"수집 중: {group_name} - {role_kr}")
                data = scrape_data(page, tier, role_en)
                print(f"  → 수집된 영웅 수: {len(data)}")

                scored = calculate_scores(data)
                all_data[f"{group_name}_{role_kr}"] = scored
                time.sleep(2)

        browser.close()

    save_csv(all_data, timestamp)
    git_push(timestamp)
    print("완료!")

if __name__ == "__main__":
    main()
