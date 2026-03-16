def scrape_data(page, tier):
    url = f"https://overwatch.blizzard.com/ko-kr/rates/?input=PC&map=all-maps&region=Asia&role=All&rq=2&tier={tier}"
    page.goto(url)
    page.wait_for_timeout(6000)

    # 페이지 끝까지 스크롤해서 모든 영웅 로드
    for _ in range(10):
        page.keyboard.press("End")
        page.wait_for_timeout(500)

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
                            if name in HERO_ROLES:
                                main_role, subrole = HERO_ROLES[name]
                            else:
                                main_role, subrole = "미분류", "미분류"
                                print(f"  → 미분류 영웅 발견: {name}")

                            data.append({
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

    # 중복 제거
    seen = {}
    for h in data:
        if h["영웅"] not in seen:
            seen[h["영웅"]] = h
    data = list(seen.values())

    print(f"  → 총 수집된 영웅 수: {len(data)}명")

    # 진단
    all_defined = set(HERO_ROLES.keys())
    collected = set(h["영웅"] for h in data)
    missing = all_defined - collected
    if missing:
        print(f"  → 누락된 영웅: {sorted(missing)}")

    return data
