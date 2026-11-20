"""Job board matching (works without any event): vacancies <-> candidates.

score = 0.40 * role fit + 0.35 * stack overlap + 0.25 * level fit (experience vs junior/middle/senior)
Explanations are built only from facts that actually match, in ru / kk / en.
"""
from .catalog import ROLES, RELATED_ROLES
from .recommender import set_sim, role_rel

LEVELS = {"junior": (0, 2), "middle": (2, 5), "senior": (5, 50)}
FORMATS = ("office", "remote", "hybrid")
LEVEL_LABELS = {"junior": "Junior", "middle": "Middle", "senior": "Senior"}

T = {
    "ru": {"role_same": "Вакансия по вашей роли «{role}».", "role_rel": "Смежная роль: {vrole} — близко к вашей «{role}».",
           "role_other": "Роль: {vrole}.", "student": "Подходит для старта карьеры.",
           "stack": "Общий стек: {s}.", "lvl_ok": "Уровень {lvl} соответствует вашему опыту ({exp}).",
           "lvl_up": "Уровень {lvl} — на шаг выше вашего опыта ({exp}).", "lvl_down": "Уровень {lvl} — ниже вашего опыта.",
           "c_role_same": "{name} — {role}, ищет работу.", "c_role_rel": "{name} — {role}, смежная роль для «{vrole}».",
           "c_role_other": "{name} — {role}.", "c_lvl": "Опыт {exp} — подходит под {lvl}.", "c_lvl_no": "Опыт {exp}.",
           "y0": "без опыта", "y": "{n} лет", "apply": "Здравствуйте! Откликаюсь на вакансию «{title}». Я {role}, опыт — {exp}{sk}. С удовольствием обсужу детали!",
           "sk": ", работаю с {s}"},
    "kk": {"role_same": "Вакансия сіздің «{role}» рөліңізге арналған.", "role_rel": "Жақын рөл: {vrole} — сіздің «{role}» рөліңізге жақын.",
           "role_other": "Рөлі: {vrole}.", "student": "Мансапты бастауға лайық.",
           "stack": "Ортақ стек: {s}.", "lvl_ok": "{lvl} деңгейі тәжірибеңізге сай ({exp}).",
           "lvl_up": "{lvl} деңгейі тәжірибеңізден бір саты жоғары ({exp}).", "lvl_down": "{lvl} деңгейі тәжірибеңізден төмен.",
           "c_role_same": "{name} — {role}, жұмыс іздейді.", "c_role_rel": "{name} — {role}, «{vrole}» рөліне жақын.",
           "c_role_other": "{name} — {role}.", "c_lvl": "Тәжірибесі {exp} — {lvl} деңгейіне сай.", "c_lvl_no": "Тәжірибесі {exp}.",
           "y0": "тәжірибесіз", "y": "{n} жыл", "apply": "Сәлеметсіз бе! «{title}» вакансиясына өтініш беремін. Мен — {role}, тәжірибем — {exp}{sk}. Талқылауға қуаныштымын!",
           "sk": ", {s} қолданамын"},
    "en": {"role_same": "The vacancy matches your role “{role}”.", "role_rel": "Related role: {vrole} — close to your “{role}”.",
           "role_other": "Role: {vrole}.", "student": "Good for starting a career.",
           "stack": "Shared stack: {s}.", "lvl_ok": "{lvl} level fits your experience ({exp}).",
           "lvl_up": "{lvl} level is one step above your experience ({exp}).", "lvl_down": "{lvl} level is below your experience.",
           "c_role_same": "{name} is a {role} looking for a job.", "c_role_rel": "{name} is a {role}, related to “{vrole}”.",
           "c_role_other": "{name} is a {role}.", "c_lvl": "{exp} of experience — fits {lvl}.", "c_lvl_no": "{exp} of experience.",
           "y0": "no experience", "y": "{n} yrs", "apply": "Hello! I'm applying for “{title}”. I'm a {role} with {exp} of experience{sk}. Happy to talk!",
           "sk": ", working with {s}"},
}


def _exp(n, lang):
    return T[lang]["y0"] if not n else T[lang]["y"].format(n=n)


def level_fit(exp, level):
    lo, hi = LEVELS.get(level, (0, 50))
    if lo <= exp <= hi:
        return 1.0
    dist = lo - exp if exp < lo else exp - hi
    return max(0.0, 1 - 0.3 * dist)


def title_of(v, lang):
    return v.get("title") or f"{LEVEL_LABELS.get(v['level'], '')} {ROLES[v['role']][lang]}".strip()


def _role_fit(prole, vrole):
    if prole == "student":      # any tech role is open to a student: the stack and level decide
        return 0.7 if ROLES[vrole]["tech"] else 0.3
    return role_rel(prole, vrole)


def match_jobs(profile, skills, vacancies, lang, exclude_owner=None, limit=30):
    out = []
    exp = profile.get("experience_years", 0)
    for v in vacancies:
        if v.get("owner") == exclude_owner:
            continue
        vs = {s.lower() for s in v.get("stack", [])}
        comp = {"role": _role_fit(profile["role"], v["role"]), "stack": set_sim(skills, vs), "level": level_fit(exp, v["level"])}
        score = .40 * comp["role"] + .35 * comp["stack"] + .25 * comp["level"]
        shared = sorted(skills & vs)
        out.append((score, v, comp, shared))
    out.sort(key=lambda x: -x[0])
    res = []
    for score, v, comp, shared in out[:limit]:
        t = T[lang]
        r, vr = ROLES[profile["role"]][lang], ROLES[v["role"]][lang]
        if profile["role"] == "student":
            s1 = t["student"]
        elif profile["role"] == v["role"]:
            s1 = t["role_same"].format(role=r)
        elif v["role"] in RELATED_ROLES.get(profile["role"], ()) or profile["role"] in RELATED_ROLES.get(v["role"], ()):
            s1 = t["role_rel"].format(vrole=vr, role=r)
        else:
            s1 = t["role_other"].format(vrole=vr)
        parts = [s1]
        if shared:
            parts.append(t["stack"].format(s=", ".join(shared[:4])))
        lo, hi = LEVELS[v["level"]]
        lk = "lvl_ok" if comp["level"] == 1 else ("lvl_up" if exp < lo else "lvl_down")
        parts.append(t[lk].format(lvl=LEVEL_LABELS[v["level"]], exp=_exp(exp, lang)))
        res.append({"id": v["id"], "score": round(min(score, 1) * 100), "shared_skills": shared,
                    "explanation": " ".join(parts)})
    return res


def match_candidates(v, people, feats, lang, limit=10):
    vs = {s.lower() for s in v.get("stack", [])}
    out = []
    for c in people:
        if c["id"] == v.get("owner") or c.get("goal") != "job_seek":
            continue
        cs = feats[c["id"]]["skills"] if c["id"] in feats else {s.lower() for s in c.get("stack", [])}
        comp = {"role": _role_fit(c["role"], v["role"]), "stack": set_sim(vs, cs), "level": level_fit(c.get("experience_years", 0), v["level"])}
        score = .40 * comp["role"] + .35 * comp["stack"] + .25 * comp["level"]
        out.append((score, c, comp, sorted(vs & cs)))
    out.sort(key=lambda x: -x[0])
    res = []
    for score, c, comp, shared in out[:limit]:
        t = T[lang]
        r, vr = ROLES[c["role"]][lang], ROLES[v["role"]][lang]
        if c["role"] == v["role"]:
            s1 = t["c_role_same"].format(name=c["name"], role=r)
        elif related_or_student(c["role"], v["role"]):
            s1 = t["c_role_rel"].format(name=c["name"], role=r, vrole=vr)
        else:
            s1 = t["c_role_other"].format(name=c["name"], role=r)
        parts = [s1]
        if shared:
            parts.append(t["stack"].format(s=", ".join(shared[:4])))
        ek = "c_lvl" if comp["level"] == 1 else "c_lvl_no"
        parts.append(t[ek].format(exp=_exp(c.get("experience_years", 0), lang), lvl=LEVEL_LABELS[v["level"]]))
        res.append({"id": c["id"], "name": c["name"], "role_label": r, "experience_years": c.get("experience_years", 0),
                    "stack": c.get("stack", []), "shared_skills": shared, "score": round(min(score, 1) * 100),
                    "explanation": " ".join(parts), "synthetic": bool(c.get("synthetic"))})
    return res


def related_or_student(a, b):
    return a == "student" or b in RELATED_ROLES.get(a, ()) or a in RELATED_ROLES.get(b, ())


def apply_text(v, profile, skills, lang):
    t = T[lang]
    shared = sorted(skills & {s.lower() for s in v.get("stack", [])})
    sk = t["sk"].format(s=", ".join(shared[:3])) if shared else ""
    role = ROLES[profile["role"]][lang]
    role = role.lower() if lang != "en" else role
    return t["apply"].format(title=title_of(v, lang), role=role, exp=_exp(profile.get("experience_years", 0), lang), sk=sk)
