"""Generate demo events (meetups / conferences) and assign synthetic participants.

Usage:  python data/generate_events.py      (run after generate_profiles.py)
Writes data/events.json. Event names are fictional demo events.
The hackathon event includes every synthetic profile; the others get a themed subset.
"""
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
rnd = random.Random(2026)
profiles = json.load(open(os.path.join(HERE, "profiles.json"), encoding="utf-8"))

EVENTS = [
    {"id": "e-hack26", "type": "hackathon", "name": "AI in Engineering Hackathon 2026",
     "date": "2026-11-20", "date_end": "2026-11-21", "city": "Алматы", "place": "МИТУ, Аль-Фараби 93г/5",
     "description": {"ru": "24-часовой хакатон: AI-решения для инженерных задач. Нетворкинг 19:00–21:00.",
                     "kk": "24 сағаттық хакатон: инженерлік міндеттерге арналған AI-шешімдер. Нетворкинг 19:00–21:00.",
                     "en": "24-hour hackathon: AI solutions for engineering tasks. Networking 19:00–21:00."},
     "tags": None},
    {"id": "e-llm14", "type": "meetup", "name": "Qazaq IT Meetup #14: LLM в продакшене",
     "date": "2026-11-28", "city": "Алматы", "place": "IT-хаб, 3 этаж",
     "description": {"ru": "Как запускать LLM и RAG в реальных продуктах: доклады, кейсы и нетворкинг.",
                     "kk": "LLM мен RAG-ты нақты өнімдерде қалай іске қосу керек: баяндамалар, кейстер және нетворкинг.",
                     "en": "Running LLMs and RAG in real products: talks, case studies and networking."},
     "tags": {"ai", "llm", "data", "qazaq_lang"}, "roles": {"data_ml", "analyst", "backend"}},
    {"id": "e-front", "type": "meetup", "name": "Frontend & Mobile Night",
     "date": "2026-12-05", "city": "Астана", "place": "Astana Hub",
     "description": {"ru": "Вечер для фронтенд- и мобайл-разработчиков и дизайнеров: React, Flutter, UX.",
                     "kk": "Фронтенд, мобайл әзірлеушілер мен дизайнерлерге арналған кеш: React, Flutter, UX.",
                     "en": "An evening for frontend and mobile developers and designers: React, Flutter, UX."},
     "tags": {"design", "mobile", "ecommerce"}, "roles": {"frontend", "mobile", "design", "qa"}},
    {"id": "e-career", "type": "conference", "name": "Startup & Career Day 2026",
     "date": "2026-12-12", "city": "Алматы", "place": "Конгресс-холл",
     "description": {"ru": "Конференция о карьере и стартапах: найм, менторство, поиск кофаундеров.",
                     "kk": "Мансап пен стартаптар туралы конференция: жалдау, менторлық, серіктес іздеу.",
                     "en": "A conference on careers and startups: hiring, mentoring, finding co-founders."},
     "tags": {"startups", "career", "fintech", "product"}, "goals": {"hire", "job_seek", "find_cofounder", "be_mentor", "find_mentor"}},
]

out = []
for e in EVENTS:
    if e["tags"] is None:
        ids = [p["id"] for p in profiles]
    else:
        ids = []
        for p in profiles:
            fit = bool(set(p["interests"]) & e["tags"]) or p["role"] in e.get("roles", set()) or p["goal"] in e.get("goals", set())
            if (fit and rnd.random() < 0.8) or rnd.random() < 0.12:
                ids.append(p["id"])
        # Coverage pass: in every event each professional role has reciprocal counterparts,
        # so a participant with any role finds relevant people at any event.
        chosen = set(ids)
        by_id = {p["id"]: p for p in profiles}
        tech_roles = sorted({p["role"] for p in profiles} - {"hr", "founder", "student"})
        need = {"hire": 3, "be_mentor": 2, "find_mentor": 2, "job_seek": 2, "exchange": 2}
        for r in tech_roles:
            for g, k in need.items():
                def ok(p):
                    return p["goal"] == g and (r in p["hiring_roles"] if g == "hire" else p["role"] == r)
                have = sum(1 for i in chosen if ok(by_id[i]))
                extra = [p["id"] for p in profiles if ok(p) and p["id"] not in chosen]
                rnd.shuffle(extra)
                chosen.update(extra[:max(0, k - have)])
        for r in ("backend", "data_ml", "frontend", "mobile", "founder", "product", "design"):
            have = sum(1 for i in chosen if by_id[i]["goal"] == "find_cofounder" and by_id[i]["role"] == r)
            extra = [p["id"] for p in profiles if p["goal"] == "find_cofounder" and p["role"] == r and p["id"] not in chosen]
            chosen.update(extra[:max(0, 2 - have)])
        ids = [p["id"] for p in profiles if p["id"] in chosen]
    item = {k: v for k, v in e.items() if k not in ("tags", "roles", "goals")}
    item["participants"] = ids
    out.append(item)

with open(os.path.join(HERE, "events.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("Events:", {e["name"]: len(e["participants"]) for e in out})
