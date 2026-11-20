"""HARD acceptance test — checks every criterion of the Qazaq IT Community case.

Run:  python tests/hard_test.py
No dependencies. Starts the real HTTP server on a free port with a temporary state dir.

Quality is judged by an INDEPENDENT judge (`suitable()` below), not by the recommender's own score:
a recommendation counts as suitable only if the goal is reciprocal AND there is a concrete,
checkable reason to meet (role fit for the goal pair + shared skills/interests/role family).
"""
import csv
import json
import os
import random
import re
import statistics
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["STATE_DIR"] = tempfile.mkdtemp(prefix="tanys_test_")

from app import catalog as C                      # noqa: E402
from app.recommender import Recommender, extract  # noqa: E402

PROFILES = json.load(open(os.path.join(ROOT, "data", "profiles.json"), encoding="utf-8"))
RESULTS = []          # (section, name, ok, detail)
KZ = set("әғқңөұүһі")


def check(section, name, ok, detail=""):
    RESULTS.append((section, name, bool(ok), detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  — {detail}" if detail else ""))
    return ok


# ---------------------------------------------------------------- independent judge
def canon(p):
    skills = {s.lower() for s in p.get("stack", [])} | extract(p.get("about", ""), C.SKILL_ALIASES)
    inter = set(p.get("interests", [])) | extract(p.get("about", ""), C.INTEREST_ALIASES)
    return skills, inter


def related(a, b):
    return a == b or b in C.RELATED_ROLES.get(a, ()) or a in C.RELATED_ROLES.get(b, ())


def suitable(u, c):
    """Would a human juror accept this recommendation? Returns (bool, reason)."""
    if c["goal"] not in C.GOAL_PRIMARY[u["goal"]]:
        return False, "goal not reciprocal"
    us, ui = canon(u)
    cs, ci = canon(c)
    shared = bool(us & cs) or bool(ui & ci)
    g = u["goal"]
    if g == "job_seek":
        hr = c.get("hiring_roles") or [c["role"]]
        fit = u["role"] == "student" or any(related(u["role"], h) for h in hr)
        return (fit and (shared or u["role"] in hr)), "hirer fit"
    if g == "hire":
        hr = u.get("hiring_roles") or [u["role"]]
        fit = any(related(c["role"], h) for h in hr) or c["role"] == "student"
        return (fit and (shared or c["role"] in hr)), "candidate fit"
    if g == "find_mentor":
        gap = c.get("experience_years", 0) - u.get("experience_years", 0)
        return (gap >= 2 and (shared or related(u["role"], c["role"]))), "mentor fit"
    if g == "be_mentor":
        gap = u.get("experience_years", 0) - c.get("experience_years", 0)
        return (gap >= 2 and (shared or related(u["role"], c["role"]))), "mentee fit"
    if g == "find_cofounder":
        comp = C.ROLES[u["role"]]["tech"] != C.ROLES[c["role"]]["tech"]
        return (bool(ui & ci) or (comp and shared)), "cofounder fit"
    return (related(u["role"], c["role"]) or len(us & cs) >= 1 or len(ui & ci) >= 2), "exchange fit"


# ---------------------------------------------------------------- jury-style profiles (adversarial)
def P(name, role, goal, exp, stack=(), interests=(), about="", hiring=(), langs=("ru",), slots=()):
    return {"name": name, "role": role, "goal": goal, "experience_years": exp, "stack": list(stack),
            "interests": list(interests), "about": about, "hiring_roles": list(hiring),
            "languages": list(langs), "slots": list(slots)}


JURY = [
    P("J01 junior backend", "backend", "job_seek", 1, ["python", "django"], ["fintech"], "Ищу первую работу бэкендером"),
    P("J02 only free text", "backend", "job_seek", 2, [], [], "пишу на питоне, знаю джанго и постгрес, хочу в финтех"),
    P("J03 kazakh text only", "data_ml", "job_seek", 1, [], [], "Машиналық оқыту және деректер талдау бойынша жұмыс іздеймін, python білемін"),
    P("J04 english slang", "frontend", "job_seek", 3, [], [], "React/TS dev, k8s curious, want an ecommerce startup", langs=("en",)),
    P("J05 QA rare role", "qa", "job_seek", 2, ["selenium", "postman"], ["career"], "QA automation"),
    P("J06 security", "security", "job_seek", 4, ["pentest", "linux"], ["cybersecurity"], "CTF player, pentester"),
    P("J07 student no exp", "student", "job_seek", 0, ["c++"], ["hackathons"], "студент 3 курса, ищу стажировку"),
    P("J08 recruiter mobile", "hr", "hire", 5, ["it recruiting"], ["career"], "нанимаем Kotlin и Swift разработчиков", hiring=("mobile",)),
    P("J09 CTO hires no list", "backend", "hire", 10, ["go", "kafka", "postgresql"], ["fintech"], "Нанимаю Go бэкендеров"),
    P("J10 ML lead hires", "data_ml", "hire", 8, ["pytorch", "nlp"], ["ai", "llm"], "Ищем NLP инженеров для LLM на казахском", hiring=("data_ml",)),
    P("J11 designer hire", "product", "hire", 6, ["jira"], ["design"], "нужен UI/UX дизайнер в команду", hiring=("design",)),
    P("J12 mentee devops", "devops", "find_mentor", 1, ["docker"], ["cloud"], "хочу вырасти в DevOps, разобраться в кубере"),
    P("J13 mentee kazakh", "student", "find_mentor", 0, ["python"], ["ai", "qazaq_lang"], "ЖИ үйреніп жүрмін, ментор іздеймін", langs=("kk",)),
    P("J14 mentee gamedev", "gamedev", "find_mentor", 1, ["unity"], ["gamedev"], "Unity джун"),
    P("J15 mentor frontend", "frontend", "be_mentor", 9, ["react", "typescript"], ["opensource"], "Senior frontend, готов менторить"),
    P("J16 mentor analyst", "analyst", "be_mentor", 7, ["sql", "power bi"], ["data"], "Lead analyst"),
    P("J17 founder needs CTO", "founder", "find_cofounder", 5, ["sales"], ["healthtech", "startups"], "HealthTech стартап, ищу CTO"),
    P("J18 dev needs biz", "mobile", "find_cofounder", 4, ["flutter"], ["fintech"], "делаю финтех-приложение, ищу бизнес-партнёра"),
    P("J19 exchange devops", "devops", "exchange", 5, ["kubernetes", "terraform"], ["cloud"], "обмен опытом по IaC"),
    P("J20 exchange designer", "design", "exchange", 3, ["figma"], ["design"], "дизайн-системы"),
    P("J21 empty interests", "backend", "exchange", 4, ["java", "spring"], [], ""),
    P("J22 typos caps", "frontend", "job_seek", 2, ["REACT", " Vue "], ["ecommerce"], "ФРОНТЕНД, РЕАКТ!!!"),
    P("J23 huge text", "data_ml", "exchange", 3, ["python"], ["ai"], "LLM RAG агенты " * 120),
    P("J24 en mentor sec", "security", "be_mentor", 12, ["siem", "owasp"], ["cybersecurity"], "Security lead, happy to mentor", langs=("en",)),
]


def sentences(text):
    text = re.sub(r"\([^)]*\)", "", text)          # parentheses don't count as sentences
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


# ================================================================ tests
def main():
    rec = Recommender(PROFILES)

    print("\n=== MUST 5 · База 100+ синтетических анкет")
    check("MUST", "в базе >= 100 анкет", len(PROFILES) >= 100, f"{len(PROFILES)}")
    names = [p["name"] for p in PROFILES]
    check("MUST", "имена уникальны", len(set(names)) == len(names))
    req = ["id", "name", "role", "stack", "experience_years", "interests", "about", "goal"]
    check("MUST", "у каждой анкеты все поля формы", all(all(k in p and p[k] not in (None, "") for k in req) for p in PROFILES))
    check("MUST", "все цели из списка кейса", all(p["goal"] in C.GOALS for p in PROFILES))
    check("MUST", "все 6 целей представлены", {p["goal"] for p in PROFILES} == set(C.GOALS))
    check("MUST", "все анкеты помечены synthetic", all(p.get("synthetic") for p in PROFILES))
    with open(os.path.join(ROOT, "data", "profiles.csv"), encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    check("MUST", "CSV совпадает с JSON", len(rows) == len(PROFILES))
    bad = [p["name"] for p in PROFILES if re.search(r"linkedin|t\.me/|@\w{3,}", p["about"], re.I)]
    check("MUST", "нет ссылок на реальные профили (LinkedIn/Telegram)", not bad, ", ".join(bad[:3]))

    print("\n=== MUST 1 · Анкета (роль, стек, опыт, интересы, «о себе», цель из 6)")
    html = open(os.path.join(ROOT, "static", "index.html"), encoding="utf-8").read()
    for fid in ["role", "stackInput", "exp", "interests", "about", "goals"]:
        check("MUST", f"поле #{fid} есть в форме", f'id="{fid}"' in html)
    check("MUST", "6 целей ровно как в кейсе", C.GOALS == ["job_seek", "hire", "find_mentor", "be_mentor", "find_cofounder", "exchange"])

    print("\n=== MUST 2 · Топ-5, у каждой объяснение 1–2 предложения")
    all_ok, bad_expl, truth_bad = True, [], []
    for u in JURY:
        r = rec.recommend(u)["recommendations"]
        all_ok &= len(r) == 5
        for x in r:
            n = len(sentences(x["explanation"]))
            if not (1 <= n <= 2) or len(x["explanation"]) < 20:
                bad_expl.append(f"{u['name']}: {n} предл.")
            # truthfulness: every skill claimed as shared really is in both profiles
            c = rec.profiles[x["id"]]
            us, _ = canon(u)
            cs, _ = canon(c)
            for s in x["shared_skills"]:
                if s not in us or s not in cs:
                    truth_bad.append(f"{u['name']}→{c['name']}: {s}")
            if x["name"] not in x["explanation"]:
                truth_bad.append(f"{u['name']}: имя не в объяснении")
    check("MUST", "ровно 5 рекомендаций для каждой из 24 анкет жюри", all_ok)
    check("MUST", "каждое объяснение 1–2 предложения", not bad_expl, "; ".join(bad_expl[:3]))
    check("MUST", "объяснения правдивы (совпадения реально есть у обоих)", not truth_bad, "; ".join(truth_bad[:3]))

    print("\n=== MUST 3 · Взаимность целей (жёстко + fuzz 500 случайных анкет)")
    viol = []
    for u in JURY:
        for x in rec.recommend(u)["recommendations"]:
            if x["goal"] not in C.GOAL_PRIMARY[u["goal"]]:
                viol.append(f"{u['name']}→{x['goal']}")
    check("MUST", "анкеты жюри: только взаимные цели", not viol, ", ".join(viol[:3]))
    rnd = random.Random(7)
    fuzz_viol, js_js, fuzz_n5 = 0, 0, 0
    for i in range(500):
        role = rnd.choice(list(C.ROLES))
        u = P(f"F{i}", role, rnd.choice(C.GOALS), rnd.randint(0, 15),
              rnd.sample(C.ALL_SKILLS, rnd.randint(0, 4)), rnd.sample(list(C.INTERESTS), rnd.randint(0, 3)),
              rnd.choice(["", "люблю python и стартапы", "Kazakh NLP", "дизайн", "ищу работу"]),
              hiring=rnd.sample([r for r in C.ROLES if r not in ("hr", "founder", "student")], rnd.randint(0, 2)))
        res = rec.recommend(u)["recommendations"]
        fuzz_n5 += len(res) == 5
        for x in res:
            if u["goal"] == "job_seek" and x["goal"] == "job_seek":
                js_js += 1
            if x["goal"] not in C.GOAL_PRIMARY[u["goal"]] + C.GOAL_SECONDARY[u["goal"]]:
                fuzz_viol += 1
            if x["goal"] not in C.GOAL_PRIMARY[u["goal"]] and not x["fallback"]:
                fuzz_viol += 1
    check("MUST", "fuzz: соискателю НИКОГДА не показаны соискатели", js_js == 0, f"{js_js} нарушений")
    check("MUST", "fuzz: нет невзаимных целей без пометки «близкий вариант»", fuzz_viol == 0, f"{fuzz_viol}")
    check("MUST", "fuzz: всегда 5 рекомендаций", fuzz_n5 == 500, f"{fuzz_n5}/500")

    print("\n=== ЦЕЛЬ · Качество: >= 3 из 5 подходящих (независимый судья)")
    per = []
    for u in JURY:
        r = rec.recommend(u)["recommendations"]
        good = sum(suitable(u, rec.profiles[x["id"]])[0] for x in r)
        per.append(good)
        check("QUALITY", f"{u['name']:<24} {good}/5", good >= 3)
    check("QUALITY", "средняя точность@5 по жюри >= 80%", statistics.mean(per) / 5 >= 0.8,
          f"{statistics.mean(per) / 5:.0%}")
    check("QUALITY", "у первой рекомендации всегда подходящий человек",
          all(suitable(u, rec.profiles[rec.recommend(u)["recommendations"][0]["id"]])[0] for u in JURY))

    print("\n=== КАЧЕСТВО ВНУТРИ КАЖДОГО МЕРОПРИЯТИЯ")
    for ev in json.load(open(os.path.join(ROOT, "data", "events.json"), encoding="utf-8")):
        pool = set(ev["participants"])
        scores = [sum(suitable(u, rec.profiles[x["id"]])[0] for x in rec.recommend(u, pool=pool)["recommendations"]) for u in JURY]
        check("QUALITY", f"{ev['name'][:34]:<34} все 24 анкеты >= 3/5",
              min(scores) >= 3, f"точность {statistics.mean(scores) / 5:.0%}, мин {min(scores)}/5")

    print("\n=== СКОРОСТЬ · < 3 секунд (база 190 и 1000 участников)")
    times = []
    for u in JURY * 4:
        t0 = time.perf_counter(); rec.recommend(u); times.append(time.perf_counter() - t0)
    p99 = sorted(times)[int(len(times) * .99) - 1]
    check("SPEED", "p99 на текущей базе < 3 с", p99 < 3, f"p99={p99 * 1000:.1f} мс")
    big = []
    for k in range(6):
        for p in PROFILES:
            q = dict(p); q["id"] = f"{p['id']}_{k}"; q["name"] = p["name"] + f" {k}"; big.append(q)
    big = big[:1000]
    t0 = time.perf_counter(); rb = Recommender(big); t_index = time.perf_counter() - t0
    times = []
    for u in JURY:
        t0 = time.perf_counter(); rb.recommend(u); times.append(time.perf_counter() - t0)
    check("SPEED", "1000 участников: max < 3 с", max(times) < 3, f"max={max(times) * 1000:.1f} мс, индекс {t_index:.2f} с")

    print("\n=== SHOULD · 3 языка")
    u = JURY[0]
    out = {lg: rec.recommend(u, lang=lg)["recommendations"][0] for lg in ("ru", "kk", "en")}
    check("SHOULD", "kk-объяснение на казахском", any(ch in KZ for ch in out["kk"]["explanation"].lower()) or "іздейді" in out["kk"]["explanation"])
    check("SHOULD", "en-объяснение без кириллицы (кроме имени)",
          not re.search(r"[а-яё]", out["en"]["explanation"].replace(out["en"]["name"], "").lower()))
    check("SHOULD", "три языка дают разные тексты", len({o["explanation"] for o in out.values()}) == 3)
    check("SHOULD", "интерфейс переведён на kk/ru/en", all(f"\n {lg}:{{" in html or f" {lg}:{{" in html for lg in ("ru", "kk", "en")))
    kz_only = JURY[2]
    sk, it = canon(kz_only)
    check("SHOULD", "навыки/темы распознаются из казахского текста", "python" in sk and "ai" in it, f"{sorted(sk)} {sorted(it)}")
    sk, _ = canon(JURY[1])
    check("SHOULD", "сленг «питон/джанго/постгрес» распознан", {"python", "django", "postgresql"} <= sk, f"{sorted(sk)}")

    print("\n=== SHOULD · Первая фраза для каждой пары")
    ice_ok = all(len(x["icebreaker"]) > 15 for u in JURY for x in rec.recommend(u)["recommendations"])
    check("SHOULD", "icebreaker есть у каждой из 120 пар", ice_ok)
    kk_ice = rec.recommend(JURY[12], lang="kk")["recommendations"][0]["icebreaker"]
    check("SHOULD", "icebreaker на выбранном языке (kk)", any(ch in KZ for ch in kk_ice.lower()), kk_ice[:60])

    print("\n=== SHOULD · Обратная связь и пересчёт")
    uid = "test-user"
    u = JURY[0]
    first = [x["id"] for x in rec.recommend(u, user_id=uid)["recommendations"]]
    rec.add_feedback(uid, first[0], "no")
    after = [x["id"] for x in rec.recommend(u, user_id=uid)["recommendations"]]
    check("SHOULD", "«не подошло» убирает человека", first[0] not in after)
    check("SHOULD", "после отзыва по-прежнему 5", len(after) == 5)
    check("SHOULD", "пересчёт меняет выдачу (новый человек)", len(set(after) - set(first)) >= 1)
    rec.add_feedback(uid, after[0], "met")
    after2 = [x["id"] for x in rec.recommend(u, user_id=uid)["recommendations"]]
    check("SHOULD", "«познакомились» убирает из выдачи", after[0] not in after2)
    hist = rec.history(uid)
    check("SHOULD", "история содержит обе отметки", {h["type"] for h in hist} == {"met", "no"} and len(hist) == 2)
    rec.add_feedback(uid, first[0], "undo")
    check("SHOULD", "отмена отметки возвращает человека", first[0] in [x["id"] for x in rec.recommend(u, user_id=uid)["recommendations"]] or len(rec.history(uid)) == 1)
    for _ in range(40):   # stress: reject everyone repeatedly — must never crash or break reciprocity
        r = rec.recommend(u, user_id=uid)["recommendations"]
        if not r:
            break
        rec.add_feedback(uid, r[0]["id"], "no")
    r = rec.recommend(u, user_id=uid)["recommendations"]
    check("SHOULD", "40 отказов подряд: без падений, соискателей не показываем",
          all(x["goal"] != "job_seek" for x in r))

    print("\n=== COULD · Встречи 1:1, дашборд, стенды")
    u = JURY[0] | {"slots": ["11:00", "12:00", "13:00", "14:00", "15:00", "16:00"]}
    r = rec.recommend(u)["recommendations"]
    slots = [x["meeting_slot"] for x in r if x["meeting_slot"]]
    check("COULD", "слоты 1:1 назначены", len(slots) >= 1, f"{slots}")
    check("COULD", "слоты не пересекаются", len(slots) == len(set(slots)))
    check("COULD", "слот свободен у обоих", all(x["meeting_slot"] in u["slots"] and x["meeting_slot"] in rec.profiles[x["id"]]["slots"] for x in r if x["meeting_slot"]))
    st = rec.stats()
    check("COULD", "дашборд: интересы, цели, спрос/предложение", all(st[k] for k in ("interests", "goals", "hiring_demand", "job_supply")))
    check("COULD", "стенды рекомендуются с причиной", all(b["why"] for b in rec.recommend(JURY[0])["booths"]) and rec.recommend(JURY[0])["booths"])

    print("\n=== MUST 4 · Рабочий веб-интерфейс (реальный HTTP)")
    from http.server import ThreadingHTTPServer
    from app import server as S
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), S.Handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    def req(path, body=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        rq = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(rq, timeout=10) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    code, body = req("/")
    check("MUST", "GET / отдаёт страницу", code == 200 and b"<form" in body)
    for pth in ("/api/meta", "/api/profiles", "/api/stats", "/health"):
        check("MUST", f"GET {pth} = 200", req(pth)[0] == 200)
    t0 = time.perf_counter()
    code, body = req("/api/recommend", {"profile": JURY[1], "lang": "kk"})
    dt = time.perf_counter() - t0
    res = json.loads(body)
    check("MUST", "POST /api/recommend → 5 рекомендаций", code == 200 and len(res["recommendations"]) == 5)
    check("SPEED", "полный HTTP-запрос < 3 с", dt < 3, f"{dt * 1000:.0f} мс")
    code, body = req("/api/feedback", {"user_id": res["user_id"], "target_id": res["recommendations"][0]["id"], "type": "no", "lang": "ru"})
    check("SHOULD", "POST /api/feedback пересчитывает", code == 200 and res["recommendations"][0]["id"] not in [x["id"] for x in json.loads(body)["recommendations"]])
    code, body = req("/api/history", {"user_id": res["user_id"], "lang": "ru"})
    check("SHOULD", "POST /api/history возвращает отметку", code == 200 and len(json.loads(body)["history"]) == 1)

    def areq(path, body=None, token=None, method=None):
        data = json.dumps(body).encode() if body is not None else None
        h = {"Content-Type": "application/json"}
        if token:
            h["Authorization"] = "Bearer " + token
        rq = urllib.request.Request(base + path, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(rq, timeout=10) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except ValueError:
                return e.code, {}

    print("\n=== АККАУНТЫ · Регистрация, вход, защита")
    code, a = areq("/api/register", {"username": "aruzhan", "password": "secret123", "name": "Аружан Тест"})
    check("ACCOUNT", "регистрация → токен", code == 200 and a.get("token"))
    TA = a.get("token")
    check("ACCOUNT", "повторный логин → 409", areq("/api/register", {"username": "aruzhan", "password": "secret123", "name": "X"})[0] == 409)
    check("ACCOUNT", "плохой логин → 400", areq("/api/register", {"username": "a b<", "password": "secret123", "name": "X"})[0] == 400)
    check("ACCOUNT", "короткий пароль → 400", areq("/api/register", {"username": "bob_1", "password": "123", "name": "X"})[0] == 400)
    check("ACCOUNT", "неверный пароль → 401", areq("/api/login", {"username": "aruzhan", "password": "wrong!!"})[0] == 401)
    code, l = areq("/api/login", {"username": "ARUZHAN", "password": "secret123"})
    check("ACCOUNT", "вход (без учёта регистра логина)", code == 200 and l.get("token"))
    check("ACCOUNT", "/api/me без токена → 401", areq("/api/me")[0] == 401)
    code, me = areq("/api/me", token=TA)
    check("ACCOUNT", "/api/me с токеном → свой аккаунт", code == 200 and me["username"] == "aruzhan")
    users_raw = open(os.path.join(os.environ["STATE_DIR"], "users.json"), encoding="utf-8").read()
    check("ACCOUNT", "пароль не хранится открытым текстом", "secret123" not in users_raw and '"hash"' in users_raw)
    print("\n=== МЕРОПРИЯТИЯ · Митапы, конференции, регистрация")
    seed = json.load(open(os.path.join(ROOT, "data", "events.json"), encoding="utf-8"))
    code, evs = areq("/api/events?lang=kk", token=TA)
    check("EVENTS", "список мероприятий", code == 200 and len(evs["events"]) >= 4)
    check("EVENTS", "у каждого: название, тип, дата, число участников",
          all(e["name"] and e["type"] in ("meetup", "conference", "hackathon") and e["date"] and e["participants"] > 0 for e in evs["events"]))
    check("EVENTS", "описание на выбранном языке (kk)", any(ch in KZ for ch in evs["events"][0]["description"].lower()))
    check("EVENTS", "подбор без мероприятия → 400", areq("/api/recommend", {"profile": JURY[0]}, token=TA)[1].get("error") == "no_event")
    check("EVENTS", "подбор без регистрации → 403", areq("/api/recommend", {"profile": JURY[0], "event_id": "e-llm14"}, token=TA)[0] == 403)
    check("EVENTS", "регистрация на мероприятие", areq("/api/events/join", {"event_id": "e-llm14"}, token=TA)[0] == 200)
    me_ev = areq("/api/me", token=TA)[1]
    check("EVENTS", "мероприятие стало текущим (с названием)", me_ev["active_event"] and me_ev["active_event"]["name"].startswith("Qazaq IT Meetup"))
    llm_pool = set(next(e for e in seed if e["id"] == "e-llm14")["participants"])
    code, rl = areq("/api/recommend", {"profile": JURY[9], "lang": "ru"}, token=TA)
    check("EVENTS", "ответ содержит название мероприятия", code == 200 and rl["event"]["id"] == "e-llm14")
    check("EVENTS", "рекомендации — только участники этого мероприятия", all(x["id"] in llm_pool for x in rl["recommendations"]))
    check("EVENTS", "дашборд по мероприятию", req("/api/stats?event=e-llm14")[0] == 200 and json.loads(req("/api/stats?event=e-llm14")[1])["total"] == len(llm_pool) + 1)
    check("EVENTS", "участники по мероприятию", len(json.loads(req("/api/profiles?event=e-llm14")[1])) == len(llm_pool) + 1)
    check("EVENTS", "создание: короткое название → 400", areq("/api/events/create", {"name": "A", "date": "2026-12-01"}, token=TA)[0] == 400)
    check("EVENTS", "создание: без даты → 400", areq("/api/events/create", {"name": "Мой митап"}, token=TA)[0] == 400)
    code, ce = areq("/api/events/create", {"name": "Python Almaty Meetup", "type": "meetup", "date": "2026-12-20", "city": "Алматы"}, token=TA)
    check("EVENTS", "создание мероприятия → автор зарегистрирован, оно текущее", code == 200 and ce["event"]["registered"] and ce["event"]["active"])
    check("EVENTS", "создание без токена → 401", areq("/api/events/create", {"name": "X meetup", "date": "2026-12-01"})[0] == 401)
    check("EVENTS", "переключить на незарегистрированное → 403", areq("/api/events/active", {"event_id": "e-front"}, token=TA)[0] == 403)
    areq("/api/events/leave", {"event_id": ce["event"]["id"]}, token=TA)
    check("EVENTS", "отмена регистрации → текущим становится другое", areq("/api/me", token=TA)[1]["active_event"]["id"] == "e-llm14")
    check("EVENTS", "UI: вкладка мероприятий и название в шапке", 'id="tab-events"' in html and 'id="evChip"' in html)
    areq("/api/events/join", {"event_id": "e-hack26"}, token=TA)
    code, ra = areq("/api/recommend", {"profile": JURY[0], "lang": "ru"}, token=TA)
    check("ACCOUNT", "анкета сохраняется в аккаунт", code == 200 and areq("/api/me", token=TA)[1]["profile"]["goal"] == "job_seek")
    check("ACCOUNT", "имя в анкете = имя аккаунта", areq("/api/me", token=TA)[1]["profile"]["name"] == "Аружан Тест")
    uidA = me["id"]
    check("ACCOUNT", "нельзя выдать себя за аккаунт по user_id", areq("/api/recommend", {"profile": JURY[1], "user_id": uidA})[0] == 401)
    check("ACCOUNT", "нельзя читать чужую историю", areq("/api/history", {"user_id": uidA})[1]["history"] == [])

    print("\n=== ЧАТ · Первое сообщение и переписка")
    demo_peer = ra["recommendations"][0]
    check("CHAT", "чат без токена → 401", areq("/api/chat/send", {"to": demo_peer["id"], "text": "hi"})[0] == 401)
    check("CHAT", "чат с несуществующим → 404", areq("/api/chat/send", {"to": "zzz", "text": "hi"}, token=TA)[0] == 404)
    check("CHAT", "пустое сообщение → 400", areq("/api/chat/send", {"to": demo_peer["id"], "text": "   "}, token=TA)[0] == 400)
    code, s1 = areq("/api/chat/send", {"to": demo_peer["id"], "text": demo_peer["icebreaker"], "lang": "ru"}, token=TA)
    check("CHAT", "первое сообщение (icebreaker) отправлено", code == 200)
    check("CHAT", "второе до ответа → 409 (правило первого сообщения)",
          areq("/api/chat/send", {"to": demo_peer["id"], "text": "ещё"}, token=TA)[0] == 409)
    code, c = areq(f"/api/chat?with={demo_peer['id']}", token=TA)
    check("CHAT", "собеседник «печатает» до ответа", code == 200 and c["typing"] and not c["can_send"])
    time.sleep(2.3)
    code, c = areq(f"/api/chat?with={demo_peer['id']}&lang=ru", token=TA)
    check("CHAT", "демо-анкета ответила", len(c["messages"]) == 2 and c["messages"][1].get("demo"))
    check("CHAT", "после ответа можно писать дальше", c["can_send"] and areq("/api/chat/send", {"to": demo_peer["id"], "text": "Отлично!"}, token=TA)[0] == 200)
    time.sleep(2.3)
    msgs = areq(f"/api/chat?with={demo_peer['id']}", token=TA)[1]["messages"]
    check("CHAT", "демо отвечает и на следующие сообщения", len(msgs) == 4 and msgs[-1]["from"] == demo_peer["id"])
    areq("/api/chat/send", {"to": demo_peer["id"], "text": "Давай встретимся в 14:30?", "lang": "ru"}, token=TA)
    time.sleep(2.3)
    last = areq(f"/api/chat?with={demo_peer['id']}", token=TA)[1]["messages"][-1]
    check("CHAT", "демо понимает время встречи", last["from"] == demo_peer["id"] and "14:30" in last["text"], last["text"][:50])
    areq("/api/chat/send", {"to": demo_peer["id"], "text": "Рахмет!", "lang": "kk"}, token=TA)
    time.sleep(2.3)
    last = areq(f"/api/chat?with={demo_peer['id']}", token=TA)[1]["messages"][-1]
    check("CHAT", "демо отвечает на языке интерфейса (kk)", any(ch in KZ for ch in last["text"].lower()), last["text"][:50])
    check("CHAT", "удаление чата с демо", areq("/api/chat/delete", {"with": demo_peer["id"]}, token=TA)[0] == 200)
    check("CHAT", "удалённый чат исчез из списка", all(c["peer"]["id"] != demo_peer["id"] for c in areq("/api/chats", token=TA)[1]["chats"]))
    check("CHAT", "после удаления можно начать заново", areq("/api/chat/send", {"to": demo_peer["id"], "text": "Привет снова"}, token=TA)[0] == 200)
    check("CHAT", "удаление без токена → 401", areq("/api/chat/delete", {"with": demo_peer["id"]})[0] == 401)
    check("CHAT", "удаление несуществующего → 404", areq("/api/chat/delete", {"with": "zzz"}, token=TA)[0] == 404)
    _, rb = areq("/api/register", {"username": "bekzat", "password": "secret456", "name": "Бекзат Тест"})
    TB = rb["token"]; uidB = rb["me"]["id"]
    areq("/api/events/join", {"event_id": "e-hack26"}, token=TB)
    areq("/api/recommend", {"profile": JURY[7], "lang": "ru"}, token=TB)
    hack_ids = {p["id"] for p in json.loads(req("/api/profiles?event=e-hack26")[1])}
    check("EVENTS", "зарегистрированный участник виден в базе мероприятия", uidA in hack_ids and uidB in hack_ids)
    check("CHAT", "живой участник → живой участник: отправка", areq("/api/chat/send", {"to": uidB, "text": "Сәлем!"}, token=TA)[0] == 200)
    _, lb = areq("/api/chats", token=TB)
    check("CHAT", "получатель видит диалог и непрочитанное", lb["unread"] == 1 and lb["chats"][0]["peer"]["id"] == uidA)
    check("CHAT", "А ждёт ответа", areq("/api/chat/send", {"to": uidB, "text": "?"}, token=TA)[0] == 409)
    check("CHAT", "Б отвечает", areq("/api/chat/send", {"to": uidA, "text": "Сәлем! Кездесейік"}, token=TB)[0] == 200)
    check("CHAT", "А снова может писать", areq("/api/chat/send", {"to": uidB, "text": "14:00?"}, token=TA)[0] == 200)
    areq(f"/api/chat?with={uidA}", token=TB)
    check("CHAT", "после открытия диалога непрочитанных 0", areq("/api/chats", token=TB)[1]["unread"] == 0)
    long_txt = "x" * 5000
    areq("/api/chat/send", {"to": uidA, "text": long_txt}, token=TB)
    msgs = areq(f"/api/chat?with={uidB}", token=TA)[1]["messages"]
    check("CHAT", "длинное сообщение обрезается до 1000", len(msgs[-1]["text"]) == 1000)
    check("CHAT", "нельзя писать самому себе", areq("/api/chat/send", {"to": uidA, "text": "me"}, token=TA)[0] == 404)
    check("CHAT", "текст сообщений экранируется в UI", "esc(m.text)" in html)
    print("\n=== ЧАТ · Галочки (как WhatsApp) и «печатает»")
    areq("/api/chat/send", {"to": uidA, "text": "Ты тут?"}, token=TB)
    m_b = areq(f"/api/chat?with={uidA}&read=0", token=TB)[1]["messages"][-1]
    check("TICKS", "у отправителя есть статус", m_b.get("status") in ("sent", "delivered", "read"))
    check("TICKS", "у входящих сообщений статуса нет", "status" not in [m for m in areq(f"/api/chat?with={uidB}&read=0", token=TA)[1]["messages"] if m["from"] == uidB][-1])
    st_cmp = areq(f"/api/chat?with={uidA}&read=0", token=TB)[1]["messages"][-1]["status"]
    check("TICKS", "А получил (открыл список) → «доставлено» ✓✓", st_cmp == "delivered", st_cmp)
    areq(f"/api/chat?with={uidB}", token=TA)            # A opens the chat
    st = areq(f"/api/chat?with={uidA}&read=0", token=TB)[1]["messages"][-1]["status"]
    check("TICKS", "А открыл чат → «прочитано» (синие ✓✓)", st == "read", st)
    _, rc = areq("/api/register", {"username": "cyrus_t", "password": "secret789", "name": "Цой Тест"})
    TC, uidC = rc["token"], rc["me"]["id"]
    areq("/api/chat/send", {"to": uidC, "text": "Сәлем"}, token=TA)
    st = areq(f"/api/chat?with={uidC}&read=0", token=TA)[1]["messages"][-1]["status"]
    check("TICKS", "получатель офлайн → «отправлено» ✓", st == "sent", st)
    check("TICKS", "демо-анкета: «прочитано»", areq(f"/api/chat?with={demo_peer['id']}", token=TA)[1]["messages"][0].get("status") in ("read", "delivered"))
    check("TICKS", "галочки в UI (✓ / ✓✓ / синие)", "TICK1" in html and "TICK2" in html and ".tick.read" in html)
    check("TYPING", "«печатает» без токена → 401", areq("/api/chat/typing", {"to": uidA})[0] == 401)
    areq("/api/chat/typing", {"to": uidA}, token=TB)
    check("TYPING", "А видит «печатает» в чате", areq(f"/api/chat?with={uidB}", token=TA)[1]["typing"] is True)
    check("TYPING", "А видит «печатает» в списке чатов", any(c["typing"] for c in areq("/api/chats", token=TA)[1]["chats"] if c["peer"]["id"] == uidB))
    check("TYPING", "Б сам себе «печатает» не видит", areq(f"/api/chat?with={uidA}", token=TB)[1]["typing"] is False)
    areq("/api/chat/send", {"to": uidA, "text": "вот"}, token=TB)
    check("TYPING", "после отправки «печатает» пропадает", areq(f"/api/chat?with={uidB}", token=TA)[1]["typing"] is False)
    check("TYPING", "UI шлёт сигнал при вводе (throttle)", "pingTyping" in html and "/api/chat/typing" in html)

    print("\n=== ЧАТ · Удаление «у меня» и «у всех»")
    areq("/api/chat/delete", {"with": uidB}, token=TA)
    check("CHAT", "«у меня»: у А чата нет", all(c["peer"]["id"] != uidB for c in areq("/api/chats", token=TA)[1]["chats"]))
    check("CHAT", "«у меня»: у Б переписка сохранилась", any(c["peer"]["id"] == uidA for c in areq("/api/chats", token=TB)[1]["chats"]))
    check("CHAT", "«у всех» → 200", areq("/api/chat/delete", {"with": uidA, "scope": "all"}, token=TB)[0] == 200)
    check("CHAT", "«у всех»: у Б чата нет", all(c["peer"]["id"] != uidA for c in areq("/api/chats", token=TB)[1]["chats"]))
    check("CHAT", "«у всех»: у А тоже нет", all(c["peer"]["id"] != uidB for c in areq("/api/chats", token=TA)[1]["chats"]))
    check("CHAT", "«у всех»: сообщения удалены с сервера", areq(f"/api/chat?with={uidB}", token=TA)[1]["messages"] == [])
    check("CHAT", "кнопки «у всех» / «у меня» в UI", 'id="delAll"' in html and 'id="delOk"' in html and 'id="delModal"' in html)
    areq("/api/logout", {}, token=TA)
    check("ACCOUNT", "после выхода токен недействителен", areq("/api/me", token=TA)[0] == 401)

    print("\n=== ЗАЛ · Места участников")
    code, rs = areq("/api/recommend", {"profile": JURY[7], "lang": "kk"}, token=TB)
    zones = {"A", "B", "C", "D", "E", "F"}
    check("SEATS", "у каждой рекомендации есть место в зале",
          code == 200 and all(x.get("seat") and x["seat"]["zone"] in zones and 1 <= x["seat"]["table"] <= 30 for x in rs["recommendations"]))
    check("SEATS", "есть моё место (для карты зала)", rs.get("my_seat") and rs["my_seat"]["zone"] in zones)
    rs2 = areq("/api/recommend", {"profile": JURY[7], "lang": "kk"}, token=TB)[1]
    check("SEATS", "места стабильны между запросами", [x["seat"] for x in rs["recommendations"]] == [x["seat"] for x in rs2["recommendations"]])
    check("SEATS", "сменить своё место", areq("/api/events/seat", {"event_id": "e-hack26", "zone": "D", "table": 7}, token=TB)[0] == 200)
    check("SEATS", "новое место видно в подборе", areq("/api/recommend", {"profile": JURY[7]}, token=TB)[1]["my_seat"] == {"zone": "D", "table": 7})
    check("SEATS", "неверная зона/стол → 400", areq("/api/events/seat", {"event_id": "e-hack26", "zone": "Z", "table": 99}, token=TB)[0] == 400)
    check("SEATS", "место на чужом мероприятии → 403", areq("/api/events/seat", {"event_id": "e-front", "zone": "A", "table": 1}, token=TB)[0] == 403)
    check("SEATS", "места в списке участников мероприятия", all("seat" in p for p in json.loads(req("/api/profiles?event=e-hack26")[1])))
    check("SEATS", "мероприятие показывает моё место", next(e for e in areq("/api/events", token=TB)[1]["events"] if e["id"] == "e-hack26")["my_seat"] == {"zone": "D", "table": 7})
    check("SEATS", "UI: карта зала и место в карточке", 'id="hallMap"' in html and "seatPill(r.seat" in html)

    print("\n=== РАБОТА · Вакансии и кандидаты без мероприятия")
    from app import jobs as J

    def suitable_job(u, v):
        us, _ = canon(u)
        fit = u["role"] == "student" or related(u["role"], v["role"])
        return fit and (bool(us & {s.lower() for s in v["stack"]}) or u["role"] == v["role"]) and \
            J.level_fit(u.get("experience_years", 0), v["level"]) >= 0.4

    vac_all = json.load(open(os.path.join(ROOT, "data", "vacancies.json"), encoding="utf-8"))
    code, jl = areq("/api/jobs?lang=kk")
    check("JOBS", "список вакансий без входа и без мероприятия", code == 200 and len(jl["vacancies"]) >= 50)
    check("JOBS", "у вакансии: название, роль, уровень, формат, стек, автор",
          all(v["title"] and v["role_label"] and v["level"] and v["format"] and v["stack"] and v["owner"]["name"] for v in jl["vacancies"]))
    for u in [x for x in JURY if x["goal"] == "job_seek"]:
        top = J.match_jobs(u, canon(u)[0], vac_all, "ru")[:5]
        good = sum(suitable_job(u, next(v for v in vac_all if v["id"] == m["id"])) for m in top)
        check("JOBS", f"вакансии для {u['name']:<22} {good}/5", good >= 3)
    for u in [x for x in JURY if x["goal"] == "hire"]:
        v = {"id": "tmp", "owner": "x", "role": (u["hiring_roles"] or [u["role"]])[0], "level": "middle",
             "stack": list(canon(u)[0])}
        top = J.match_candidates(v, list(rec.profiles.values()), rec.feats, "ru")[:5]
        good = sum(1 for c in top if related(rec.profiles[c["id"]]["role"], v["role"]) or rec.profiles[c["id"]]["role"] == "student")
        check("JOBS", f"кандидаты для {u['name']:<21} {good}/5", good >= 3 and all(rec.profiles[c["id"]]["goal"] == "job_seek" for c in top))
    check("JOBS", "подбор вакансий без анкеты → no_profile", areq("/api/jobs/match", token=TC)[1].get("error") == "no_profile")
    check("JOBS", "анкета сохраняется без мероприятия", areq("/api/profile", {"profile": JURY[0]}, token=TC)[0] == 200)
    code, jm = areq("/api/jobs/match?lang=kk", token=TC)
    check("JOBS", "подбор вакансий с объяснением (kk)", code == 200 and jm["matches"] and all(m["explanation"] and 0 <= m["score"] <= 100 for m in jm["matches"]))
    check("JOBS", "объяснение на казахском", any(ch in KZ for ch in jm["matches"][0]["explanation"].lower()))
    check("JOBS", "создание: роль обязательна → 400", areq("/api/jobs/create", {"level": "junior"}, token=TB)[0] == 400)
    code, cv = areq("/api/jobs/create", {"title": "Middle Flutter-разработчик", "role": "mobile", "level": "middle", "format": "hybrid",
                                         "city": "Алматы", "salary_from": 900000, "stack": "flutter, dart, firebase"}, token=TB)
    check("JOBS", "вакансия опубликована", code == 200 and cv["vacancy"]["own"])
    VID = cv["vacancy"]["id"]
    code, cc = areq(f"/api/jobs/candidates?id={VID}&lang=ru", token=TB)
    check("JOBS", "AI-подбор кандидатов: только ищущие работу", code == 200 and cc["candidates"] and
          all(rec.profiles.get(c["id"], {}).get("goal") == "job_seek" or c["id"] == uidC for c in cc["candidates"]))
    check("JOBS", "кандидаты чужой вакансии → 403", areq(f"/api/jobs/candidates?id={VID}", token=TC)[0] == 403)
    code, ap = areq("/api/jobs/apply", {"id": VID, "lang": "ru"}, token=TC)
    check("JOBS", "отклик → сообщение автору в чат", code == 200 and ap["messaged"])
    mine = areq("/api/jobs/mine", token=TB)[1]["vacancies"]
    check("JOBS", "автор видит отклик в «Мои вакансии»", any(v["id"] == VID and any(a["id"] == uidC for a in v["applicants"]) for v in mine))
    check("JOBS", "автор получил сообщение-отклик", any(c["peer"]["id"] == uidC for c in areq("/api/chats", token=TB)[1]["chats"]))
    check("JOBS", "повторный отклик не дублируется", areq("/api/jobs/apply", {"id": VID}, token=TC)[1]["already"] is True and
          next(v for v in areq("/api/jobs/mine", token=TB)[1]["vacancies"] if v["id"] == VID)["applications"] == 1)
    check("JOBS", "отклик на свою вакансию → 400", areq("/api/jobs/apply", {"id": VID}, token=TB)[0] == 400)
    code, ap2 = areq("/api/jobs/apply", {"id": vac_all[0]["id"], "lang": "kk"}, token=TC)
    time.sleep(2.3)
    peer_msgs = areq(f"/api/chat?with={vac_all[0]['owner']}", token=TC)[1]["messages"]
    check("JOBS", "отклик на демо-вакансию → демо-ответ", code == 200 and len(peer_msgs) == 2 and peer_msgs[1].get("demo"))
    check("JOBS", "удаление чужой вакансии → 403", areq("/api/jobs/delete", {"id": VID}, token=TC)[0] == 403)
    check("JOBS", "удаление своей → 200", areq("/api/jobs/delete", {"id": VID}, token=TB)[0] == 200)
    check("JOBS", "без токена: подбор → 401", areq("/api/jobs/match")[0] == 401 and areq("/api/jobs/apply", {"id": vac_all[0]["id"]})[0] == 401)
    check("JOBS", "UI: вкладка «Работа»", 'id="tab-jobs"' in html and 'data-tab="jobs"' in html)

    print("\n=== MOBILE · Телефонная версия и PWA")
    check("MOBILE", "viewport для телефона", 'name="viewport"' in html and "viewport-fit=cover" in html)
    check("MOBILE", "нижняя навигация для телефона", 'nav class="bottom"' in html and "@media (max-width:760px)" in html)
    check("MOBILE", "чат на весь экран на телефоне", ".conv{position:fixed;inset:0" in html)
    check("MOBILE", "инпуты 16px (без зума на iOS)", "font-size:16px!important" in html)
    check("MOBILE", "safe-area (вырез экрана)", "safe-area-inset-bottom" in html)
    code, raw = req("/manifest.webmanifest")
    man = json.loads(raw) if code == 200 else {}
    check("MOBILE", "PWA manifest: standalone + иконки", man.get("display") == "standalone" and len(man.get("icons", [])) >= 2)
    check("MOBILE", "service worker отдаётся", req("/sw.js")[0] == 200)
    check("MOBILE", "иконки отдаются", req("/icon.svg")[0] == 200 and req("/icon-maskable.svg")[0] == 200)

    print("\n=== НАДЁЖНОСТЬ · Плохие входные данные")
    check("ROBUST", "битый JSON не роняет сервер", req("/api/recommend", raw=b"{not json")[0] in (200, 400))
    code, body = req("/api/recommend", {"profile": {"goal": "hack", "role": "<script>", "experience_years": "abc"}})
    check("ROBUST", "мусорные поля → валидный ответ", code == 200 and len(json.loads(body)["recommendations"]) == 5)
    check("ROBUST", "пустая анкета → валидный ответ", req("/api/recommend", {})[0] == 200)
    check("ROBUST", "feedback с чужим user_id → 400", req("/api/feedback", {"user_id": "nope", "target_id": "p001", "type": "no"})[0] == 400)
    check("ROBUST", "неизвестный путь → 404", req("/api/xxx")[0] == 404)
    unescaped = re.findall(r"\$\{(?:r|p|h|b)\.(name|about|explanation|icebreaker|company|role_label|goal_label|why)\}", html)
    check("ROBUST", "фронтенд экранирует все пользовательские тексты (XSS)", "const esc" in html and not unescaped, ", ".join(unescaped))
    check("ROBUST", "сервер жив после всех атак", req("/health")[0] == 200)
    httpd.shutdown()

    print("\n=== ЗАПУСК И СДАЧА")
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    check("REPO", "README с инструкцией docker compose up", "docker compose up" in readme)
    check("REPO", "docker-compose.yml и Dockerfile есть", os.path.exists(os.path.join(ROOT, "docker-compose.yml")) and os.path.exists(os.path.join(ROOT, "Dockerfile")))
    leaks = []
    for dp, _, fs in os.walk(ROOT):
        if any(x in dp for x in (".git", "__pycache__")):
            continue
        for fn in fs:
            if fn == "hard_test.py":      # contains the detection regex itself
                continue
            if fn.endswith((".py", ".html", ".md", ".yml", ".json", ".txt", ".env")):
                txt = open(os.path.join(dp, fn), encoding="utf-8", errors="ignore").read()
                if re.search(r"sk-[A-Za-z0-9]{20,}|sk-ant-|AIza[0-9A-Za-z_-]{30}|ghp_[A-Za-z0-9]{30}", txt):
                    leaks.append(fn)
    check("REPO", "в репозитории нет API-ключей", not leaks, ", ".join(leaks))
    check("REPO", "файл анкет JSON и CSV", all(os.path.exists(os.path.join(ROOT, "data", f)) for f in ("profiles.json", "profiles.csv")))
    check("REPO", "быстрые демо-анкеты для пути «анкета → результат»", html.count("label:{ru:") >= 3)

    # ------------------------------------------------------------ scorecard
    print("\n" + "=" * 64)
    sections = {}
    for s, _, ok, _ in RESULTS:
        a, b = sections.get(s, (0, 0))
        sections[s] = (a + ok, b + 1)
    for s, (a, b) in sections.items():
        print(f"  {s:<8} {a:>3}/{b:<3} {'OK' if a == b else 'FAIL'}")
    total_ok = sum(ok for _, _, ok, _ in RESULTS)
    print(f"  ИТОГО    {total_ok}/{len(RESULTS)} проверок")
    fails = [(s, n, d) for s, n, ok, d in RESULTS if not ok]
    if fails:
        print("\nПровалено:")
        for s, n, d in fails:
            print(f"  - [{s}] {n} {d}")
    print("=" * 64)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
