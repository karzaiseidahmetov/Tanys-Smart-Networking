"""Sanity / quality check: reciprocity rule, latency, sample output.

Run:  python tests/eval.py
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from app.recommender import Recommender  # noqa: E402
from app.catalog import GOAL_PRIMARY  # noqa: E402

with open(os.path.join(ROOT, "data", "profiles.json"), encoding="utf-8") as f:
    PROFILES = json.load(f)

TESTS = [
    {"id": "t1", "name": "Тест Джуниор", "role": "backend", "stack": ["python", "fastapi", "postgresql"],
     "experience_years": 1, "interests": ["fintech", "ai"], "goal": "job_seek", "languages": ["ru", "kk"],
     "about": "Junior Python-бэкендер, хочу в финтех, делал пет-проект на FastAPI и Docker.",
     "slots": ["12:00", "14:00", "15:30"]},
    {"id": "t2", "name": "Тест Рекрутер", "role": "hr", "stack": ["it recruiting"], "experience_years": 6,
     "interests": ["career"], "goal": "hire", "hiring_roles": ["frontend", "mobile"], "languages": ["ru", "en"],
     "about": "Ищу React и Flutter разработчиков в продуктовую команду.", "slots": ["11:00", "13:00"]},
    {"id": "t3", "name": "Тест Студентка", "role": "student", "stack": ["python"], "experience_years": 0,
     "interests": ["ai", "qazaq_lang"], "goal": "find_mentor", "languages": ["kk", "ru"],
     "about": "Машиналық оқытуды үйреніп жүрмін, NLP және қазақ тіліндегі LLM қызықтырады.", "slots": []},
    {"id": "t4", "name": "Test Founder", "role": "founder", "stack": ["sales", "fundraising"], "experience_years": 4,
     "interests": ["agritech", "startups"], "goal": "find_cofounder", "languages": ["en", "ru"],
     "about": "Building an AgriTech startup with drones and computer vision, need a technical CTO.", "slots": []},
    {"id": "t5", "name": "Тест Сеньор", "role": "devops", "stack": ["kubernetes", "terraform", "aws"],
     "experience_years": 9, "interests": ["cloud", "opensource"], "goal": "be_mentor", "languages": ["ru"],
     "about": "Senior DevOps, готов менторить по Kubernetes и CI/CD.", "slots": []},
    {"id": "t6", "name": "Тест Аналитик", "role": "analyst", "stack": ["sql", "power bi"], "experience_years": 3,
     "interests": ["data", "fintech"], "goal": "exchange", "languages": ["ru"],
     "about": "Аналитик в банке, хочу обменяться опытом по дашбордам и A/B тестам.", "slots": []},
]

rec = Recommender(PROFILES)
ok = True
for u in TESTS:
    t0 = time.perf_counter()
    res = rec.recommend(u, lang="ru")
    dt = (time.perf_counter() - t0) * 1000
    goals = [r["goal"] for r in res["recommendations"]]
    recip = all(g in GOAL_PRIMARY[u["goal"]] for g in goals)
    no_same_seek = not (u["goal"] == "job_seek" and "job_seek" in goals)
    ok &= recip and no_same_seek and len(goals) == 5 and dt < 3000
    print(f"\n=== {u['name']} [{u['goal']}]  {dt:.1f} ms  reciprocity={'OK' if recip else 'FAIL'}")
    for r in res["recommendations"]:
        print(f"  {r['score']:>3}  {r['name']:<22} {r['role_label']:<24} -> {r['explanation']}")
        print(f"       ice: {r['icebreaker']}   slot: {r['meeting_slot']}")
    print("  booths:", [b["name"] for b in res["booths"]])

print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
sys.exit(0 if ok else 1)
