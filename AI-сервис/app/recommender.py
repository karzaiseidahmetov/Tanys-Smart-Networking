"""Hybrid recommender: goal-reciprocity filter -> feature scoring -> explanations.

No external dependencies, no LLM. Scoring components (0..1 each):
  role   - role compatibility for the goal pair (hire<->seek: does the hirer hire my role, etc.)
  stack  - overlap of canonical skills (form + skills extracted from free text)
  inter  - overlap of interests (form + extracted from free text)
  text   - TF-IDF cosine similarity of "about" texts (crude multilingual stemming)
  exp    - experience fit (mentor seniority gap, hire level)
  lang   - shared spoken language bonus
Weights depend on the user's goal. Feedback ("met" / "not a fit") excludes the person and
shifts weights for similar profiles (role family), so the list is recalculated.
"""
import math
import re
import time
from collections import Counter

from .catalog import (GOAL_PRIMARY, GOAL_SECONDARY, ROLES, RELATED_ROLES, SKILL_ALIASES,
                      INTEREST_ALIASES, INTERESTS, GOAL_LABELS, BOOTHS)
from . import texts

WEIGHTS = {
    "job_seek":       {"role": .35, "stack": .30, "inter": .10, "text": .15, "exp": .05, "lang": .05},
    "hire":           {"role": .35, "stack": .30, "inter": .10, "text": .15, "exp": .05, "lang": .05},
    "find_mentor":    {"role": .25, "stack": .25, "inter": .15, "text": .15, "exp": .15, "lang": .05},
    "be_mentor":      {"role": .25, "stack": .25, "inter": .15, "text": .15, "exp": .15, "lang": .05},
    "find_cofounder": {"role": .30, "stack": .05, "inter": .35, "text": .25, "exp": .00, "lang": .05},
    "exchange":       {"role": .20, "stack": .30, "inter": .25, "text": .20, "exp": .00, "lang": .05},
}

WORD_RE = re.compile(r"[a-zа-яёәғқңөұүһі0-9#+.]+", re.IGNORECASE)
STOP = set("и в на с по для что как я я) это мы вы а но или к у о об из от до за же ли не бы то "
           "мен және бен пен да де үшін бұл осы мен the a an and or of to in for with on at is are i my "
           "am we you your our".split())


def tokenize(text):
    out = []
    for w in WORD_RE.findall(text.lower()):
        w = w.strip(".")
        if len(w) < 2 or w in STOP:
            continue
        out.append(w[:6] if len(w) > 6 else w)  # crude stemming that works for ru/kk/en
    return out


def extract(text, aliases):
    t = " " + text.lower().replace(",", " ").replace(".", " ") + " "
    found = set()
    for k, v in aliases.items():
        if k.startswith(" ") or k.endswith(" "):
            if k in t:
                found.add(v)
        elif len(k) <= 3:
            if re.search(r"(?<![a-zа-яёәғқңөұүһі])" + re.escape(k) + r"(?![a-zа-яёәғқңөұүһі])", t):
                found.add(v)
        elif re.search(r"(?<![a-zа-яёәғқңөұүһі])" + re.escape(k), t):   # word-start match: "ойын" ≠ "бойынша"
            found.add(v)
    return found


def _kind(v):
    return v.get("type") if isinstance(v, dict) else v


def set_sim(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / math.sqrt(len(a) * len(b))


def role_rel(a, b):
    if a == b:
        return 1.0
    if b in RELATED_ROLES.get(a, ()) or a in RELATED_ROLES.get(b, ()):
        return 0.6
    return 0.2


class Recommender:
    def __init__(self, profiles):
        self.profiles = {}
        self.feats = {}
        self.df = Counter()
        self.n_docs = 0
        for p in profiles:
            self.add(p, rebuild=False)
        self._rebuild_idf()
        self.feedback = {}   # user_id -> {target_id: "met"|"no"}

    # ---------- indexing ----------
    def _features(self, p):
        about = p.get("about", "")
        skills = {s.lower() for s in p.get("stack", [])} | extract(about, SKILL_ALIASES)
        inter = set(p.get("interests", [])) | extract(about, INTEREST_ALIASES)
        tokens = tokenize(about + " " + " ".join(p.get("stack", [])) + " " +
                          " ".join(INTERESTS[i]["en"] for i in inter if i in INTERESTS))
        return {"skills": skills, "inter": inter, "tf": Counter(tokens)}

    def add(self, p, rebuild=True):
        old = self.feats.get(p["id"])
        if old:
            for t in old["tf"]:
                self.df[t] -= 1
            self.n_docs -= 1
        f = self._features(p)
        self.profiles[p["id"]] = p
        self.feats[p["id"]] = f
        for t in f["tf"]:
            self.df[t] += 1
        self.n_docs += 1
        if rebuild:
            self._rebuild_idf()

    def remove(self, pid):
        f = self.feats.pop(pid, None)
        if f:
            for t in f["tf"]:
                self.df[t] -= 1
            self.n_docs -= 1
            self.profiles.pop(pid, None)
            self._rebuild_idf()

    def _rebuild_idf(self):
        self.idf = {t: math.log((1 + self.n_docs) / (1 + c)) + 1 for t, c in self.df.items()}
        self.vecs = {pid: self._vec(f["tf"]) for pid, f in self.feats.items()}

    def _vec(self, tf):
        v = {t: c * self.idf.get(t, 1.0) for t, c in tf.items()}
        n = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / n for t, x in v.items()}

    # ---------- scoring ----------
    def _role_score(self, u, c, goal):
        ur, cr = u["role"], c["role"]
        if goal == "job_seek":      # c hires
            hr = c.get("hiring_roles") or [cr]
            return max(role_rel(ur, h) for h in hr) if ur != "student" else (0.8 if any(h in ("backend", "frontend", "qa", "analyst") for h in hr) else 0.5)
        if goal == "hire":          # c seeks a job
            hr = u.get("hiring_roles") or [ur]
            return max(role_rel(cr, h) for h in hr)
        if goal in ("find_mentor", "be_mentor"):
            if "student" in (ur, cr):
                return 0.7
            return role_rel(ur, cr)
        if goal == "find_cofounder":
            ut, ct = ROLES[ur]["tech"], ROLES[cr]["tech"]
            if ut != ct:
                return 1.0          # tech + business = complementary team
            return 0.6 if ur != cr else 0.35
        return role_rel(ur, cr)     # exchange

    def _exp_score(self, u, c, goal):
        ue, ce = u.get("experience_years", 0), c.get("experience_years", 0)
        if goal == "find_mentor":
            gap = ce - ue
        elif goal == "be_mentor":
            gap = ue - ce
        else:
            return 1.0 if goal in ("job_seek", "hire") else 0.5
        return 1.0 if gap >= 3 else 0.6 if gap >= 1 else 0.0

    def score_pair(self, u, uf, uvec, c, goal):
        cf = self.feats[c["id"]]
        cvec = self.vecs[c["id"]]
        comp = {
            "role": self._role_score(u, c, goal),
            "stack": set_sim(uf["skills"], cf["skills"]),
            "inter": set_sim(uf["inter"], cf["inter"]),
            "text": sum(w * cvec.get(t, 0.0) for t, w in uvec.items()),
            "exp": self._exp_score(u, c, goal),
            "lang": 1.0 if set(u.get("languages", [])) & set(c.get("languages", [])) else 0.0,
        }
        w = WEIGHTS[goal]
        total = sum(w[k] * comp[k] for k in w)
        return total, comp, cf

    def recommend(self, user, k=5, lang="ru", user_id=None, pool=None):
        """pool: optional set of profile ids (participants of the selected event)."""
        t0 = time.perf_counter()
        goal = user["goal"]
        uf = self._features(user)
        uvec = self._vec(uf["tf"])
        fb = self.feedback.get(user_id, {}) if user_id else {}
        liked_roles = Counter(self.profiles[t]["role"] for t, v in fb.items() if _kind(v) == "met" and t in self.profiles)
        disliked_roles = Counter(self.profiles[t]["role"] for t, v in fb.items() if _kind(v) == "no" and t in self.profiles)

        tiers = [(GOAL_PRIMARY[goal], 0), (GOAL_SECONDARY[goal], 1)]
        scored = []
        for allowed, tier in tiers:
            cands = [c for c in self.profiles.values()
                     if c["goal"] in allowed and c["id"] != user_id and c["id"] not in fb
                     and (pool is None or c["id"] in pool)]
            for c in cands:
                s, comp, cf = self.score_pair(user, uf, uvec, c, goal)
                s += 0.04 * min(liked_roles[c["role"]], 2) - 0.08 * min(disliked_roles[c["role"]], 3)
                scored.append((tier, -s, c["id"], comp, cf, s))
            if len([x for x in scored if x[0] == 0]) >= k:
                break
        scored.sort(key=lambda x: (x[0], x[1]))
        top = scored[:k]

        recs = []
        used_slots = set()
        for tier, _, cid, comp, cf, s in top:
            c = self.profiles[cid]
            shared_skills = sorted(uf["skills"] & cf["skills"])
            shared_inter = sorted(uf["inter"] & cf["inter"])
            slot = next((sl for sl in c.get("slots", []) if sl in set(user.get("slots", [])) and sl not in used_slots), None)
            if slot:
                used_slots.add(slot)
            recs.append({
                "id": cid,
                "name": c["name"],
                "role": c["role"],
                "role_label": ROLES[c["role"]][lang],
                "goal": c["goal"],
                "goal_label": GOAL_LABELS[c["goal"]][lang],
                "experience_years": c.get("experience_years", 0),
                "company": c.get("company", ""),
                "stack": c.get("stack", []),
                "about": c.get("about", ""),
                "languages": c.get("languages", []),
                "score": round(min(s, 1.0) * 100),
                "components": {k2: round(v, 2) for k2, v in comp.items()},
                "fallback": tier == 1,
                "shared_skills": shared_skills,
                "shared_interests": [INTERESTS[i][lang] for i in shared_inter if i in INTERESTS],
                "explanation": texts.explain(user, c, goal, comp, shared_skills, shared_inter, lang),
                "icebreaker": texts.icebreaker(user, c, goal, shared_skills, shared_inter, lang),
                "meeting_slot": slot,
            })
        booths = self.booths(user, uf, lang)
        return {"recommendations": recs, "booths": booths,
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
                "extracted": {"skills": sorted(uf["skills"]), "interests": sorted(uf["inter"])}}

    def booths(self, user, uf, lang):
        res = []
        for b in BOOTHS:
            s = len(set(b["tags"]) & uf["inter"]) + (2 if user["goal"] in b["goals"] else 0)
            if s:
                res.append((s, b))
        res.sort(key=lambda x: -x[0])
        return [{"name": b["name"], "why": texts.booth_why(b, uf["inter"], user["goal"], lang)} for _, b in res[:2]]

    # ---------- feedback ----------
    def add_feedback(self, user_id, target_id, kind):
        if kind == "undo":
            self.feedback.get(user_id, {}).pop(target_id, None)
        else:
            self.feedback.setdefault(user_id, {})[target_id] = {"type": kind, "ts": int(time.time())}

    def history(self, user_id, lang="ru"):
        items = []
        for tid, v in self.feedback.get(user_id, {}).items():
            c = self.profiles.get(tid)
            if not c:
                continue
            items.append({
                "id": tid, "type": _kind(v), "ts": v.get("ts", 0) if isinstance(v, dict) else 0,
                "name": c["name"], "role_label": ROLES[c["role"]][lang],
                "goal_label": GOAL_LABELS[c["goal"]][lang],
                "experience_years": c.get("experience_years", 0), "stack": c.get("stack", []),
            })
        items.sort(key=lambda x: -x["ts"])
        return items

    # ---------- organizer dashboard ----------
    def stats(self, pool=None):
        ps = [p for p in self.profiles.values() if pool is None or p["id"] in pool]
        goals = Counter(p["goal"] for p in ps)
        inter = Counter(i for p in ps for i in self.feats[p["id"]]["inter"])
        skills = Counter(s for p in ps for s in p.get("stack", []))
        roles = Counter(p["role"] for p in ps)
        demand = Counter(r for p in ps if p["goal"] == "hire" for r in (p.get("hiring_roles") or [p["role"]]))
        supply = Counter(p["role"] for p in ps if p["goal"] == "job_seek")
        fb = Counter(_kind(v) for d in self.feedback.values() for t, v in d.items() if pool is None or t in pool)
        return {
            "total": len(ps),
            "goals": goals.most_common(),
            "interests": inter.most_common(12),
            "skills": skills.most_common(12),
            "roles": roles.most_common(),
            "hiring_demand": demand.most_common(),
            "job_supply": supply.most_common(),
            "mentors": goals.get("be_mentor", 0), "mentees": goals.get("find_mentor", 0),
            "feedback": {"met": fb.get("met", 0), "no": fb.get("no", 0)},
        }
