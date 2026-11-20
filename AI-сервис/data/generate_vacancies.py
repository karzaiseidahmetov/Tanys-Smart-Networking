"""Generate demo vacancies from synthetic hiring profiles.

Usage:  python data/generate_vacancies.py     (run after generate_profiles.py)
Writes data/vacancies.json. Companies and salaries are fictional.
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.catalog import ROLES, ROLE_SKILLS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
rnd = random.Random(77)
profiles = json.load(open(os.path.join(HERE, "profiles.json"), encoding="utf-8"))

SALARY = {"junior": (300, 550), "middle": (600, 1200), "senior": (1200, 2500)}
CITIES = ["Алматы", "Астана", "Шымкент", "Алматы", "Алматы"]
DESC = {
    "ru": "Ищем {role} в команду ({company}). Стек: {stack}. Задачи: развитие продукта, код-ревью, работа в команде.",
    "kk": "Командаға {role} іздейміз ({company}). Стек: {stack}. Міндеттер: өнімді дамыту, код-ревью, командада жұмыс.",
    "en": "We're looking for a {role} ({company}). Stack: {stack}. You'll grow the product, do code reviews and work in a team.",
}

out = []
for p in profiles:
    if p["goal"] != "hire":
        continue
    for role in (p.get("hiring_roles") or [p["role"]])[:2]:
        level = rnd.choice(["junior", "junior", "middle", "middle", "senior"])
        pool = ROLE_SKILLS[role]
        stack = rnd.sample(pool, k=min(len(pool), rnd.randint(3, 5)))
        lo, hi = SALARY[level]
        sal_from = rnd.randrange(lo, hi, 50) * 1000
        fmt = rnd.choice(["office", "hybrid", "remote", "hybrid"])
        desc = {lg: DESC[lg].format(role=ROLES[role][lg].lower() if lg != "en" else ROLES[role][lg],
                                    company=p["company"], stack=", ".join(stack)) for lg in DESC}
        out.append({"id": f"v{len(out) + 1:03d}", "owner": p["id"], "role": role, "level": level, "stack": stack,
                    "format": fmt, "city": rnd.choice(CITIES), "salary_from": sal_from,
                    "company": p["company"], "description": desc, "created": 1795100000 + len(out) * 3600,
                    "synthetic": True})

# Coverage pass: every core student skill has at least 3 junior vacancies / internships,
# and every tech role has at least 2 junior vacancies — so beginners always get relevant matches.
hirers = [p for p in profiles if p["goal"] == "hire"]


def add_vacancy(role, level, must_skill=None):
    p = rnd.choice(hirers)
    pool = [s for s in ROLE_SKILLS[role] if s != must_skill]
    stack = ([must_skill] if must_skill else []) + rnd.sample(pool, k=min(len(pool), rnd.randint(2, 4)))
    lo, hi = SALARY[level]
    desc = {lg: DESC[lg].format(role=ROLES[role][lg].lower() if lg != "en" else ROLES[role][lg],
                                company=p["company"], stack=", ".join(stack)) for lg in DESC}
    out.append({"id": f"v{len(out) + 1:03d}", "owner": p["id"], "role": role, "level": level, "stack": stack,
                "format": rnd.choice(["office", "hybrid", "remote"]), "city": rnd.choice(CITIES),
                "salary_from": rnd.randrange(lo, hi, 50) * 1000, "company": p["company"], "description": desc,
                "created": 1795100000 + len(out) * 3600, "synthetic": True})


for skill in ROLE_SKILLS["student"]:
    roles = [r for r, sk in ROLE_SKILLS.items() if skill in sk and r not in ("student", "hr", "founder")] or ["backend"]
    while sum(1 for v in out if v["level"] == "junior" and skill in v["stack"]) < 3:
        add_vacancy(rnd.choice(roles), "junior", must_skill=skill)
for role in [r for r in ROLES if ROLES[r]["tech"] and r != "student"]:
    while sum(1 for v in out if v["level"] == "junior" and v["role"] == role) < 2:
        add_vacancy(role, "junior")

with open(os.path.join(HERE, "vacancies.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f"Generated {len(out)} vacancies")
