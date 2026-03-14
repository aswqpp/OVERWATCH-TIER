import os
import time
import csv
import subprocess
from datetime import datetime
from playwright.sync_api import sync_playwright

TIER_GROUPS = {
    "저티어": ["Bronze", "Silver", "Gold"],
    "중티어": ["Platinum", "Diamond"],
    "고티어": ["Master", "GrandmasterAndChampion"]
}

ROLES = ["Tank", "Damage", "Support"]
ROLE_KR = {"Tank": "탱커", "Damage": "딜러", "Support": "서포터"}

def scrape_tier_data(page, tier, role):
    url = f"https://overwatch.blizzard.com/ko-kr/rates/?input=PC&map=all-maps&region=Asia&role={role}&rq=1&tier={tier}"
    page.goto(url)
    page.wait_for_timeout(6000)

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
                        pickrate = float(next1.replace("%", "").strip())
                        winrate = float(next2.replace("%", "").strip())

                        if name and 0 < pickrate < 100 and 0 < winrate < 100:
                            data.append({
                                "영웅": name,
                                "승률": winrate,
                                "픽률": pickrate
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

def save_csv(all_data, today):
    os.makedirs("data", exist_ok=True)
    filepath = f"data/{today}.csv"

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["날짜", "그룹", "역할", "영웅", "승률(%)", "픽률(%)", "점수", "티어"])

        for key, heroes in all_data.items():
            group_name, role = key.rsplit("_", 1)
            for h in heroes:
                writer.writerow([
                    today,
                    group_name,
                    role,
                    h["영웅"],
                    h["승률"],
                    h["픽률"],
                    h["점수"],
                    h["티어"]
                ])

    print(f"  → CSV 저장 완료: {filepath}")
    return filepath

def git_push(today):
    subprocess.run(["git", "config", "user.email", "action@github.com"])
    subprocess.run(["git", "config", "user.name", "GitHub Action"])
    subprocess.run(["git", "add", "data/"])
    subprocess.run(["git", "commit", "-m", f"데이터 업데이트: {today}"])
    subprocess.run(["git", "push"])
    print("  → GitHub 업로드 완료!")

def main():
    today = datetime.now().strftime("%Y-%m-%d")
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
                    averaged.append({
                        "영웅": name,
                        "승률": round(avg_win, 2),
                        "픽률": round(avg_pick, 2)
                    })

                scored = calculate_scores(averaged)
                all_data[f"{group_name}_{ROLE_KR[role]}"] = scored

        browser.close()

    save_csv(all_data, today)
    git_push(today)
    print("완료!")

if __name__ == "__main__":
    main()
