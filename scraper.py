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

# (메인역할, 서브롤)
HERO_ROLES = {
    # 탱커 - 개시자
    "D.Va": ("탱커", "개시자"),
    "레킹볼": ("탱커", "개시자"),
    "윈스턴": ("탱커", "개시자"),
    "둠피스트": ("탱커", "개시자"),
    # 탱커 - 투사
    "마우가": ("탱커", "투사"),
    "오리사": ("탱커", "투사"),
    "로드호그": ("탱커", "투사"),
    "자리야": ("탱커", "투사"),
    # 탱커 - 강건한 자
    "라마트라": ("탱커", "강건한 자"),
    "라인하르트": ("탱커", "강건한 자"),
    "도미나": ("탱커", "강건한 자"),
    "해저드": ("탱커", "강건한 자"),
    "정커퀸": ("탱커", "강건한 자"),
    "시그마": ("탱커", "강건한 자"),
    # 딜러 - 전문가
    "바스티온": ("딜러", "전문가"),
    "엠레": ("딜러", "전문가"),
    "정크랫": ("딜러", "전문가"),
    "메이": ("딜러", "전문가"),
    "솔저: 76": ("딜러", "전문가"),
    # 딜러 - 수색가
    "에코": ("딜러", "수색가"),
    "프레야": ("딜러", "수색가"),
    "파라": ("딜러", "수색가"),
    "솜브라": ("딜러", "수색가"),
    # 딜러 - 측면 공격가
    "겐지": ("딜러", "측면 공격가"),
    "안란": ("딜러", "측면 공격가"),
    "리퍼": ("딜러", "측면 공격가"),
    "트레이서": ("딜러", "측면 공격가"),
    "벤데타": ("딜러", "측면 공격가"),
    "벤처": ("딜러", "측면 공격가"),
    # 딜러 - 명사수
    "애쉬": ("딜러", "명사수"),
    "캐서디": ("딜러", "명사수"),
    "한조": ("딜러", "명사수"),
    "소전": ("딜러", "명사수"),
    "위도우메이커": ("딜러", "명사수"),
    # 힐러 - 전술가
    "아나": ("힐러", "전술가"),
    "바티스트": ("힐러", "전술가"),
    "제트팩 캣": ("힐러", "전술가"),
    "루시우": ("힐러", "전술가"),
    "젠야타": ("힐러", "전술가"),
    # 힐러 - 의무관
    "키리코": ("힐러", "의무관"),
    "라이프위버": ("힐러", "의무관"),
    "메르시": ("힐러", "의무관"),
    "모이라": ("힐러", "의무관"),
    # 힐러 - 생존왕
    "브리기테": ("힐러", "생존왕"),
    "일리아리": ("힐러", "생존왕"),
    "주노": ("힐러", "생존왕"),
    "미즈키": ("힐러", "생존왕"),
    "우양": ("힐러", "생존왕"),
}

def scrape_data(page, tier):
    all_data = []

    for role in ["Tank", "Damage", "Support"]:
        url = f"https://overwatch.blizzard.com/ko-kr/rates/?input=PC&map=all-maps&region=Asia&role={role}&rq=2&tier={tier}"
        page.goto(url)
        page.wait_for_timeout(5000)

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
                                if name in HERO_ROLES:
                                    main_role, subrole = HERO_ROLES[name]
                                else:
                                    main_role, subrole = "미분류", "미분류"
                                    print(f"  → 미분류 영웅 발견: {name}")

                                all_data.append({
                                    "영웅": name,
                                    "승률": winrate,
                                    "픽률": pickrate,
                                    "메인역할": main_role,
                                    "서브롤": subrole
                                })
                                i += 3
                                continue
                        except:
                            pass
                i += 1

        except Exception as e:
            print(f"  → 오류: {e}")

        time.sleep(2)

    # 중복 제거
    seen = {}
    for h in all_data:
        if h["영웅"] not in seen:
            seen[h["영웅"]] = h
    all_data = list(seen.values())

    print(f"  → 총 수집된 영웅 수: {len(all_data)}명")
    return all_data
    
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
            group_name, role = key.split("_", 1)
            for h in heroes:
                writer.writerow([
                    timestamp,
                    group_name,
                    role,
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
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    all_data = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for group_name, tier in TIER_GROUPS.items():
            print(f"\n수집 중: {group_name} ({tier})")
            data = scrape_data(page, tier)

            # 메인역할별로 분리
            role_data = {"탱커": [], "딜러": [], "힐러": []}
            for h in data:
                role = h["메인역할"]
                if role in role_data:
                    role_data[role].append(h)

            # 역할별 영웅 수 출력
            for role, heroes in role_data.items():
                print(f"  → {role}: {len(heroes)}명")

            # 역할별 점수 계산
            for role, heroes in role_data.items():
                scored = calculate_scores(heroes)
                all_data[f"{group_name}_{role}"] = scored

            time.sleep(2)
# 진단: 어떤 영웅이 빠졌는지 확인
all_collected = set()
for heroes in all_data.values():
    for h in heroes:
        all_collected.add(h["영웅"])

all_defined = set(HERO_ROLES.keys())
missing = all_defined - all_collected
extra = all_collected - all_defined

print(f"\n=== 진단 결과 ===")
print(f"정의된 영웅 수: {len(all_defined)}명")
print(f"수집된 영웅 수: {len(all_collected)}명")
if missing:
    print(f"누락된 영웅: {sorted(missing)}")
if extra:
    print(f"미분류 영웅: {sorted(extra)}")
        browser.close()

    save_csv(all_data, timestamp)
    git_push(timestamp)
    print("\n완료!")

if __name__ == "__main__":
    main()
