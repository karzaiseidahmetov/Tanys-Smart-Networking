"""Generate synthetic (fictional) participant profiles for the networking demo.

Usage:  python data/generate_profiles.py [count]
Writes data/profiles.json and data/profiles.csv. Deterministic (seed=42).
All names are randomly combined fictional names; no real profiles were used.
"""
import csv
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.catalog import ROLES, ROLE_SKILLS, INTERESTS, SLOTS, RELATED_ROLES  # noqa: E402

random.seed(42)
HERE = os.path.dirname(os.path.abspath(__file__))

M_FIRST = ["Айдар", "Ерлан", "Тимур", "Бекзат", "Санжар", "Ернар", "Дамир", "Арман", "Ильяс", "Нұрлан",
           "Мирас", "Ерасыл", "Даулет", "Алихан", "Азамат", "Руслан", "Әли", "Жандос", "Мади", "Ғалым",
           "Артём", "Максим", "Дмитрий", "Игорь", "Олжас", "Батыр", "Шыңғыс", "Темірлан", "Абылай", "Нурбол"]
F_FIRST = ["Аружан", "Дана", "Жанель", "Динара", "Мадина", "Асель", "Айгерім", "Әлия", "Томирис", "Камила",
           "Жансая", "Аяжан", "Сабина", "Інжу", "Меруерт", "Гүлназ", "Алина", "Елена", "Анна", "Ольга",
           "Дильназ", "Карина", "Айым", "Зарина", "Ақбота", "Нәзира", "Салтанат", "Виктория", "Диана", "Лаура"]
SURN_BASE = ["Ахмет", "Сейіт", "Жұмабек", "Нұрлан", "Серік", "Қасым", "Бекмұрат", "Тоқтар", "Әбдір", "Ермек",
             "Сапар", "Омар", "Байжан", "Мұрат", "Есен", "Қуаныш", "Талғат", "Жақсылық", "Иван", "Петр", "Смирн"]
NEUTRAL_SURN = ["Ким", "Цой", "Пак", "Ли", "Тен"]

COMPANIES = ["продуктовый стартап", "финтех-компания", "EdTech-стартап", "банк", "telecom-оператор",
             "аутсорс-студия", "e-commerce платформа", "госсектор", "университет", "фриланс", "GameDev-студия",
             "AgriTech-стартап", "логистическая компания", "HealthTech-стартап", "IT-интегратор"]

ROLE_INTERESTS = {
    "backend": ["cloud", "opensource", "fintech", "ecommerce", "ai"],
    "frontend": ["design", "opensource", "ecommerce", "edtech", "mobile"],
    "mobile": ["mobile", "design", "fintech", "ecommerce", "startups"],
    "data_ml": ["ai", "llm", "data", "healthtech", "agritech", "qazaq_lang"],
    "analyst": ["data", "fintech", "product", "ecommerce", "govtech"],
    "devops": ["cloud", "opensource", "cybersecurity"],
    "qa": ["opensource", "career", "fintech"],
    "security": ["cybersecurity", "cloud", "govtech", "hackathons"],
    "gamedev": ["gamedev", "design", "edtech", "robotics"],
    "design": ["design", "product", "edtech", "mobile", "startups"],
    "product": ["product", "startups", "fintech", "edtech", "data"],
    "hr": ["career", "startups", "edtech"],
    "founder": ["startups", "fintech", "agritech", "healthtech", "govtech", "ai"],
    "student": ["career", "hackathons", "ai", "gamedev", "robotics", "edtech"],
}

GOAL_DIST = [("job_seek", 0.24), ("hire", 0.15), ("find_mentor", 0.16), ("be_mentor", 0.14),
             ("find_cofounder", 0.13), ("exchange", 0.18)]

ABOUT = {
    "ru": {
        "intro": "{role} с опытом {exp}. Работаю с {skills}.",
        "intro_student": "Студент, изучаю {skills}. Участвую в хакатонах.",
        "interest": "Интересуюсь темами: {interests}.",
        "job_seek": "Ищу работу или стажировку, где можно расти в {focus}.",
        "hire": "Нанимаю в команду: {hiring}. Ищу мотивированных людей.",
        "find_mentor": "Хочу найти ментора, который поможет вырасти до следующего грейда.",
        "be_mentor": "Готов(а) менторить начинающих: код-ревью, карьера, подготовка к собеседованиям.",
        "find_cofounder": "Делаю стартап в сфере {domain}, ищу кофаундера-{need}.",
        "exchange": "Люблю обмениваться опытом, могу рассказать про {skills} и послушать про ваши кейсы.",
    },
    "kk": {
        "intro": "{role}, тәжірибем {exp}. {skills} құралдарымен жұмыс істеймін.",
        "intro_student": "Студентпін, {skills} үйреніп жүрмін. Хакатондарға қатысамын.",
        "interest": "Қызығатын тақырыптарым: {interests}.",
        "job_seek": "{focus} саласында өсуге болатын жұмыс немесе тағылымдама іздеймін.",
        "hire": "Командаға маман іздеймін: {hiring}.",
        "find_mentor": "Келесі деңгейге өсуге көмектесетін ментор іздеймін.",
        "be_mentor": "Жаңадан бастағандарға менторлық жасауға дайынмын: код-ревью, мансап, сұхбатқа дайындық.",
        "find_cofounder": "{domain} саласында стартап жасап жатырмын, {need} серіктес іздеймін.",
        "exchange": "Тәжірибе алмасқанды ұнатамын, {skills} туралы айтып бере аламын.",
    },
    "en": {
        "intro": "{role} with {exp} of experience. I work with {skills}.",
        "intro_student": "Student learning {skills}. I love hackathons.",
        "interest": "Interested in: {interests}.",
        "job_seek": "Looking for a job or internship where I can grow in {focus}.",
        "hire": "Hiring for my team: {hiring}.",
        "find_mentor": "Looking for a mentor to help me reach the next level.",
        "be_mentor": "Happy to mentor juniors: code review, career advice, interview prep.",
        "find_cofounder": "Building a startup in {domain}, looking for a {need} co-founder.",
        "exchange": "I enjoy sharing experience — can talk about {skills} and learn from your cases.",
    },
}
NEED = {"ru": {True: "бизнес/продакт", False: "технаря (CTO)"},
        "kk": {True: "бизнес/продакт", False: "техникалық (CTO)"},
        "en": {True: "business/product", False: "technical (CTO)"}}


def exp_text(years, lang):
    if lang == "ru":
        return f"{years} " + ("год" if years == 1 else "года" if 2 <= years <= 4 else "лет")
    if lang == "kk":
        return f"{years} жыл"
    return f"{years} year" + ("" if years == 1 else "s")


def pick_goal():
    r, acc = random.random(), 0.0
    for g, p in GOAL_DIST:
        acc += p
        if r <= acc:
            return g
    return "exchange"


def make_name(used):
    while True:
        female = random.random() < 0.45
        first = random.choice(F_FIRST if female else M_FIRST)
        if random.random() < 0.15:
            last = random.choice(NEUTRAL_SURN)
        else:
            base = random.choice(SURN_BASE)
            last = base + ("ова" if female else "ов")
        name = f"{first} {last}"
        if name not in used:
            used.add(name)
            return name


def pick_role(goal):
    if goal == "hire":
        return random.choice(["backend", "data_ml", "frontend", "devops", "hr", "hr", "product", "founder", "mobile", "analyst"])
    if goal == "be_mentor":
        return random.choice([r for r in ROLES if r not in ("student", "hr")])
    if goal == "find_cofounder":
        return random.choice(["founder", "founder", "product", "backend", "data_ml", "frontend", "mobile", "design"])
    if goal in ("job_seek", "find_mentor"):
        return random.choice([r for r in ROLES if r not in ("hr", "founder")] + ["student", "student"])
    return random.choice([r for r in ROLES if r != "student"])


def pick_exp(goal, role):
    if role == "student":
        return random.choice([0, 0, 1])
    if goal in ("be_mentor", "hire"):
        return random.randint(5, 14)
    if goal == "find_mentor":
        return random.randint(0, 3)
    if goal == "job_seek":
        return random.choice([0, 1, 1, 2, 2, 3, 4, 5, 6])
    return random.randint(1, 10)


def make_profile(i, used, goal=None, role=None, hiring=None):
    goal = goal or pick_goal()
    role = role or pick_role(goal)
    exp = pick_exp(goal, role)
    lang = random.choices(["ru", "kk", "en"], weights=[55, 25, 20])[0]
    skills_pool = ROLE_SKILLS[role]
    stack = random.sample(skills_pool, k=min(len(skills_pool), random.randint(3, 5)))
    interests = random.sample(ROLE_INTERESTS[role], k=min(len(ROLE_INTERESTS[role]), random.randint(2, 3)))
    if random.random() < 0.35:
        extra = random.choice(list(INTERESTS.keys()))
        if extra not in interests:
            interests.append(extra)

    hiring_roles = []
    if goal == "hire":
        if role in ("hr", "founder", "product"):
            hiring_roles = random.sample(["backend", "frontend", "mobile", "data_ml", "analyst", "devops", "qa", "design"], k=random.randint(2, 3))
        else:
            hiring_roles = [role] + random.sample(sorted(RELATED_ROLES[role]), k=min(1, len(RELATED_ROLES[role])))
        if hiring:
            hiring_roles = [hiring] + [r for r in hiring_roles if r != hiring][:1]
        if role in ("hr", "founder", "product"):
            # recruiters list the stack they hire for
            stack = stack[:2] + random.sample(sorted({s for r in hiring_roles for s in ROLE_SKILLS[r]}), k=3)

    languages = sorted({lang, "ru"} | ({"kk"} if random.random() < 0.5 else set()) | ({"en"} if random.random() < 0.6 else set()))
    slots = sorted(random.sample(SLOTS, k=random.randint(4, 8)), key=SLOTS.index)

    t = ABOUT[lang]
    skills_txt = ", ".join(stack[:3])
    interests_txt = ", ".join(INTERESTS[x][lang] for x in interests)
    parts = [t["intro_student"].format(skills=skills_txt) if role == "student"
             else t["intro"].format(role=ROLES[role][lang], exp=exp_text(exp, lang), skills=skills_txt)]
    parts.append(t["interest"].format(interests=interests_txt))
    parts.append(t[goal].format(
        focus=ROLES[role][lang] if role != "student" else stack[0],
        hiring=", ".join(ROLES[r][lang] for r in hiring_roles),
        domain=INTERESTS[interests[0]][lang],
        need=NEED[lang][ROLES[role]["tech"]],
        skills=skills_txt,
    ))

    return {
        "id": f"p{i:03d}",
        "name": make_name(used),
        "role": role,
        "stack": stack,
        "experience_years": exp,
        "interests": interests,
        "about": " ".join(parts),
        "goal": goal,
        "hiring_roles": hiring_roles,
        "company": "—" if role == "student" else random.choice(COMPANIES),
        "languages": languages,
        "slots": slots,
        "synthetic": True,
    }


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 160
    used = set()
    profiles = [make_profile(i + 1, used) for i in range(n)]

    # Coverage pass: every professional role gets enough reciprocal counterparts,
    # so any jury profile (even a rare role like QA or security) has relevant matches.
    tech_roles = [r for r in ROLES if r not in ("hr", "founder", "student")]
    need = {"hire": 3, "be_mentor": 2, "find_mentor": 2, "job_seek": 2, "exchange": 2}
    for r in tech_roles:
        for g, k in need.items():
            if g == "hire":
                have = sum(1 for p in profiles if p["goal"] == "hire" and r in p["hiring_roles"])
            else:
                have = sum(1 for p in profiles if p["goal"] == g and p["role"] == r)
            for _ in range(max(0, k - have)):
                if g == "hire":
                    owner = random.choice([r, "hr", "product", "founder"])
                    profiles.append(make_profile(len(profiles) + 1, used, goal="hire", role=owner, hiring=r))
                else:
                    profiles.append(make_profile(len(profiles) + 1, used, goal=g, role=r))
    for g in ("find_cofounder",):
        for r in ("backend", "data_ml", "frontend", "mobile", "founder", "product", "design"):
            if sum(1 for p in profiles if p["goal"] == g and p["role"] == r) < 2:
                profiles.append(make_profile(len(profiles) + 1, used, goal=g, role=r))
    n = len(profiles)
    with open(os.path.join(HERE, "profiles.json"), "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=1)
    with open(os.path.join(HERE, "profiles.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "role", "stack", "experience_years", "interests", "goal", "hiring_roles",
                    "company", "languages", "slots", "about"])
        for p in profiles:
            w.writerow([p["id"], p["name"], p["role"], "; ".join(p["stack"]), p["experience_years"],
                        "; ".join(p["interests"]), p["goal"], "; ".join(p["hiring_roles"]), p["company"],
                        "; ".join(p["languages"]), "; ".join(p["slots"]), p["about"]])
    from collections import Counter
    print(f"Generated {n} profiles. Goals:", dict(Counter(p["goal"] for p in profiles)))


if __name__ == "__main__":
    main()
