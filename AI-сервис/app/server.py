"""Tanys HTTP server (Python standard library only).

Run:  python -m app.server        -> http://localhost:8090   (PORT env var to change)

Features: accounts (PBKDF2 password hashes + bearer session tokens), recommendations,
feedback/history, 1:1 chat with an "initial message" rule, organizer stats, PWA files.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
import uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from .catalog import (GOALS, GOAL_LABELS, ROLES, ALL_SKILLS, INTERESTS, SLOTS, LANG_LABELS)
from .recommender import Recommender
from . import texts
from . import jobs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
STATIC = os.path.join(ROOT, "static")
STATE = os.environ.get("STATE_DIR", DATA)   # where users/feedback/chats are persisted
USERS_FILE = os.path.join(STATE, "users.json")
FEEDBACK_FILE = os.path.join(STATE, "feedback.json")
SESSIONS_FILE = os.path.join(STATE, "sessions.json")
CHATS_FILE = os.path.join(STATE, "chats.json")
USER_EVENTS_FILE = os.path.join(STATE, "user_events.json")      # events created in the app
REGISTRATIONS_FILE = os.path.join(STATE, "registrations.json")  # event_id -> [uid] of real accounts
EVENT_TYPES = ("meetup", "conference", "hackathon")
SEATS_FILE = os.path.join(STATE, "seats.json")                  # event_id -> {uid: {zone, table}}
USER_VAC_FILE = os.path.join(STATE, "user_vacancies.json")      # vacancies posted in the app
APPS_FILE = os.path.join(STATE, "applications.json")            # vacancy_id -> [{uid, ts}]
HALL_ZONES = [
    {"id": "A", "label": {"ru": "Сцена", "kk": "Сахна", "en": "Stage"}},
    {"id": "B", "label": {"ru": "AI Lab", "kk": "AI Lab", "en": "AI Lab"}},
    {"id": "C", "label": {"ru": "Career Hub", "kk": "Career Hub", "en": "Career Hub"}},
    {"id": "D", "label": {"ru": "Startup Alley", "kk": "Startup Alley", "en": "Startup Alley"}},
    {"id": "E", "label": {"ru": "Кофе-зона", "kk": "Кофе аймағы", "en": "Coffee area"}},
    {"id": "F", "label": {"ru": "Mentor Desk", "kk": "Mentor Desk", "en": "Mentor Desk"}},
]
ZONE_IDS = [z["id"] for z in HALL_ZONES]
TABLES = 30

LOCK = threading.RLock()
USERNAME_RE = re.compile(r"^[a-z0-9_.]{3,32}$")
AUTO_REPLY_DELAY = 2      # seconds before a demo profile "answers"
MAX_MSG = 1000


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


PROFILES = load_json(os.path.join(DATA, "profiles.json"), [])
USERS = load_json(USERS_FILE, {})          # uid -> {"profile", "visible", "account"?}
SESSIONS = load_json(SESSIONS_FILE, {})    # token -> uid
CHATS = load_json(CHATS_FILE, {"conv": {}, "read": {}})   # conv: key -> [msg], read: uid -> {key: ts}
REC = Recommender(PROFILES + [u["profile"] for u in USERS.values() if u.get("visible") and u.get("profile")])
REC.feedback = load_json(FEEDBACK_FILE, {})
SEED_EVENTS = load_json(os.path.join(DATA, "events.json"), [])
USER_EVENTS = load_json(USER_EVENTS_FILE, [])
REG = load_json(REGISTRATIONS_FILE, {})
SEATS = load_json(SEATS_FILE, {})
SEED_VAC = load_json(os.path.join(DATA, "vacancies.json"), [])
USER_VAC = load_json(USER_VAC_FILE, [])
APPS = load_json(APPS_FILE, {})


def _h(s):
    return int(hashlib.md5(s.encode("utf-8")).hexdigest(), 16)


def default_seat(pid, eid, profile=None):
    """Deterministic seat: people tend to sit in the zone that fits their goal."""
    p = profile or REC.profiles.get(pid) or {}
    h = _h(pid + "|" + eid)
    goal_zone = {"hire": "C", "job_seek": "C", "be_mentor": "F", "find_mentor": "F", "find_cofounder": "D"}.get(p.get("goal"))
    if not goal_zone:
        goal_zone = "B" if set(p.get("interests", [])) & {"ai", "llm", "data"} else "E"
    zone = goal_zone if h % 100 < 60 else ZONE_IDS[(h // 100) % len(ZONE_IDS)]
    return {"zone": zone, "table": (h // 1000) % TABLES + 1}


def seat_of(pid, eid):
    return SEATS.get(eid, {}).get(pid) or default_seat(pid, eid)


def all_vacancies():
    return SEED_VAC + USER_VAC


def get_vacancy(vid):
    return next((v for v in all_vacancies() if v["id"] == vid), None)


def vacancy_card(v, lang, uid=None):
    owner = person(v.get("owner", ""), lang) or {"id": v.get("owner"), "name": "?"}
    d = v.get("description") or {}
    apps = APPS.get(v["id"], [])
    return {"id": v["id"], "title": jobs.title_of(v, lang), "role": v["role"], "role_label": ROLES[v["role"]][lang],
            "level": v["level"], "format": v.get("format", "office"), "city": v.get("city", ""),
            "salary_from": v.get("salary_from"), "stack": v.get("stack", []), "company": v.get("company", ""),
            "description": (d.get(lang) or d.get("ru") or "") if isinstance(d, dict) else str(d),
            "owner": {"id": owner["id"], "name": owner["name"]}, "created": v.get("created", 0),
            "applications": len(apps), "applied": bool(uid and any(a["uid"] == uid for a in apps)),
            "own": bool(uid and v.get("owner") == uid)}


def all_events():
    return SEED_EVENTS + USER_EVENTS


def get_event(eid):
    return next((e for e in all_events() if e["id"] == eid), None)


def event_pool(eid):
    """Participant ids of an event: synthetic participants + registered accounts."""
    e = get_event(eid)
    if not e:
        return None
    return set(e.get("participants", [])) | set(REG.get(eid, []))


def event_card(e, lang, uid=None):
    pool = event_pool(e["id"])
    d = e.get("description") or {}
    return {"id": e["id"], "name": e["name"], "type": e.get("type", "meetup"),
            "date": e.get("date", ""), "date_end": e.get("date_end", ""),
            "city": e.get("city", ""), "place": e.get("place", ""),
            "description": d.get(lang) or d.get("ru") or next(iter(d.values()), "") if isinstance(d, dict) else str(d),
            "participants": len([p for p in pool if p in REC.profiles]) if pool else 0,
            "registered": bool(uid and uid in REG.get(e["id"], [])),
            "my_seat": seat_of(uid, e["id"]) if uid and uid in REG.get(e["id"], []) else None,
            "active": bool(uid and (USERS.get(uid) or {}).get("active_event") == e["id"]),
            "own": e.get("owner") == uid if uid else False}


def resolve_event(uid, data):
    """Event for a request: explicit event_id, else the user's active event, else None (= everyone)."""
    eid = data.get("event_id") or (USERS.get(uid) or {}).get("active_event")
    return eid if eid and get_event(eid) else None


# ---------------------------------------------------------------- helpers
def hash_pw(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 120_000).hex()


def clean_profile(data, uid, name=None):
    goal = data.get("goal") if data.get("goal") in GOALS else "exchange"
    role = data.get("role") if data.get("role") in ROLES else "student"

    def as_list(v):
        if isinstance(v, str):
            v = [x.strip() for x in v.split(",")]
        if not isinstance(v, list):
            return []
        return [str(x).strip().lower() for x in v if str(x).strip()][:20]
    try:
        exp = max(0, min(50, int(data.get("experience_years", 0))))
    except (TypeError, ValueError):
        exp = 0
    return {
        "id": uid,
        "name": (name or str(data.get("name") or "Участник"))[:60],
        "role": role,
        "stack": as_list(data.get("stack")),
        "experience_years": exp,
        "interests": [i for i in as_list(data.get("interests")) if i in INTERESTS],
        "about": str(data.get("about") or "")[:1500],
        "goal": goal,
        "hiring_roles": [r for r in as_list(data.get("hiring_roles")) if r in ROLES],
        "company": str(data.get("company") or "")[:80],
        "languages": [l for l in as_list(data.get("languages")) if l in LANG_LABELS] or ["ru"],
        "slots": [s for s in (data.get("slots") or []) if s in SLOTS] if isinstance(data.get("slots"), list) else [],
        "synthetic": False,
    }


def meta():
    return {
        "goals": [{"id": g, "label": GOAL_LABELS[g]} for g in GOALS],
        "roles": [{"id": r, "label": {k: v for k, v in ROLES[r].items() if k != "tech"}} for r in ROLES],
        "interests": [{"id": i, "label": INTERESTS[i]} for i in INTERESTS],
        "skills": ALL_SKILLS,
        "slots": SLOTS,
        "languages": LANG_LABELS,
        "zones": HALL_ZONES,
        "tables": TABLES,
    }


def me_payload(uid):
    u = USERS[uid]
    acc = u.get("account") or {}
    ev = get_event(u.get("active_event") or "")
    return {"id": uid, "username": acc.get("username"), "name": acc.get("name"),
            "profile": u.get("profile"), "visible": u.get("visible", True),
            "active_event": {"id": ev["id"], "name": ev["name"]} if ev else None,
            "events": [eid for eid, us in REG.items() if uid in us]}


def person(pid, lang="ru"):
    """Public card of anyone you can chat with (demo profile or real account)."""
    p = REC.profiles.get(pid) or (USERS.get(pid) or {}).get("profile")
    if not p:
        acc = (USERS.get(pid) or {}).get("account")
        if not acc:
            return None
        return {"id": pid, "name": acc["name"], "role_label": "", "goal_label": "", "synthetic": False}
    return {"id": pid, "name": p["name"], "role_label": ROLES[p["role"]][lang],
            "goal_label": GOAL_LABELS[p["goal"]][lang], "synthetic": bool(p.get("synthetic")),
            "experience_years": p.get("experience_years", 0), "slots": p.get("slots", [])}


def conv_key(a, b):
    return "|".join(sorted([a, b]))


def visible_msgs(key):
    now = time.time()
    return [m for m in CHATS["conv"].get(key, []) if m["ts"] <= now]


def msgs_for(uid, key, include_pending=False):
    """Messages this user sees: delivered, and newer than the moment they deleted the chat."""
    cut = CHATS.setdefault("deleted", {}).get(uid, {}).get(key, 0)
    now = time.time()
    return [m for m in CHATS["conv"].get(key, []) if m["ts"] > cut and (include_pending or m["ts"] <= now)]


TYPING = {}      # (from, to) -> last keystroke ts (in memory, ephemeral)
TYPING_TTL = 4   # seconds


def is_typing(who, to):
    return time.time() - TYPING.get((who, to), 0) < TYPING_TTL


def mark_seen(uid):
    """Client of `uid` fetched its inbox -> messages to uid are 'delivered'."""
    CHATS.setdefault("seen", {})[uid] = time.time()


def status_of(m, key):
    """WhatsApp-style ticks for a message: sent (✓) / delivered (✓✓) / read (blue ✓✓)."""
    peer = m["to"]
    if (REC.profiles.get(peer) or {}).get("synthetic"):
        return "read" if time.time() >= m["ts"] + 1 else "delivered"
    if CHATS["read"].get(peer, {}).get(key, 0) >= m["ts"]:
        return "read"
    if CHATS.setdefault("seen", {}).get(peer, 0) >= m["ts"]:
        return "delivered"
    return "sent"


def with_status(uid, key, msgs):
    return [dict(m, status=status_of(m, key)) if m["from"] == uid else m for m in msgs]


def send_message(uid, to, text, lang, target):
    """Store a message (initial-message rule applies). Returns the message, or None if waiting for a reply."""
    with LOCK:
        if not can_send(uid, to):
            return None
        key = conv_key(uid, to)
        now = time.time()
        msg = {"id": uuid.uuid4().hex[:12], "from": uid, "to": to, "text": text, "ts": now}
        conv = CHATS["conv"].setdefault(key, [])
        conv.append(msg)
        TYPING.pop((uid, to), None)
        CHATS["read"].setdefault(uid, {})[key] = now
        if target.get("synthetic"):
            # demo profile answers EVERY message (one pending reply at a time)
            pending = [m for m in conv if m["from"] == to and m["ts"] > now]
            peer_p = REC.profiles[to]
            replies = sum(1 for m in conv if m["from"] == to)
            if replies == 0:
                me_p = (USERS[uid].get("profile") or {})
                slot = next((s for s in target.get("slots", []) if s in set(me_p.get("slots", []))), None) \
                    or (target.get("slots") or [None])[0]
                reply = texts.auto_reply(peer_p, lang, slot)
            else:
                reply = texts.follow_reply(peer_p, text, lang, replies)
            if pending:                       # user typed again before the answer: answer the latest
                pending[-1]["text"] = reply
            else:
                conv.append({"id": uuid.uuid4().hex[:12], "from": to, "to": uid, "demo": True,
                             "text": reply, "ts": now + AUTO_REPLY_DELAY})
        save_json(CHATS_FILE, CHATS)
        return msg


def can_send(uid, peer):
    """Initial-message rule: until the peer replies, you can send only ONE message."""
    msgs = visible_msgs(conv_key(uid, peer))      # a scheduled (not yet delivered) reply doesn't count
    if any(m["from"] == peer for m in msgs):
        return True
    return not any(m["from"] == uid for m in CHATS["conv"].get(conv_key(uid, peer), []))


# ---------------------------------------------------------------- handler
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8", cache="no-store"):
        if not isinstance(body, (bytes, bytearray)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return {}
        if n > 200_000:
            return {}
        try:
            d = json.loads(self.rfile.read(n) or b"{}")
            return d if isinstance(d, dict) else {}
        except ValueError:
            return {}

    def _auth(self):
        h = self.headers.get("Authorization", "")
        if h.startswith("Bearer "):
            uid = SESSIONS.get(h[7:].strip())
            if uid in USERS:
                return uid
        return None

    def _uid(self, data, create=False):
        """Account via token; guests (no account) may pass user_id. Accounts can't be impersonated."""
        uid = self._auth()
        if uid:
            return uid
        guest = data.get("user_id")
        if guest and guest in USERS and not USERS[guest].get("account"):
            return guest
        if guest and guest in USERS:
            return None                      # belongs to an account -> token required
        return ("u-" + uuid.uuid4().hex[:8]) if create else None

    def _static(self, name, ctype):
        try:
            with open(os.path.join(STATIC, name), "rb") as f:
                return self._send(200, f.read(), ctype, cache="no-cache")
        except OSError:
            return self._send(404, {"error": "not found"})

    # ---------------- GET
    def do_GET(self):
        url = urlparse(self.path)
        path, qs = url.path, parse_qs(url.query)
        lang = (qs.get("lang") or ["ru"])[0]
        lang = lang if lang in LANG_LABELS else "ru"
        if path in ("/", "/index.html"):
            return self._static("index.html", "text/html; charset=utf-8")
        if path == "/manifest.webmanifest":
            return self._static("manifest.webmanifest", "application/manifest+json")
        if path == "/sw.js":
            return self._static("sw.js", "text/javascript; charset=utf-8")
        if path in ("/icon.svg", "/icon-maskable.svg"):
            return self._static(path[1:], "image/svg+xml")
        if path == "/api/meta":
            return self._send(200, meta())
        ev_q = (qs.get("event") or [""])[0]
        pool_q = event_pool(ev_q) if ev_q else None
        if path == "/api/profiles":
            rows = [p for p in REC.profiles.values() if pool_q is None or p["id"] in pool_q]
            if pool_q is not None:
                rows = [dict(p, seat=seat_of(p["id"], ev_q)) for p in rows]
            return self._send(200, rows)
        if path == "/api/jobs":
            me = self._auth()
            vs = sorted(all_vacancies(), key=lambda v: -v.get("created", 0))
            return self._send(200, {"vacancies": [vacancy_card(v, lang, me) for v in vs]})
        if path == "/api/stats":
            return self._send(200, REC.stats(pool_q))
        if path == "/api/events":
            me = self._auth()
            evs = [event_card(e, lang, me) for e in all_events()]
            evs.sort(key=lambda e: e["date"])
            return self._send(200, {"events": evs})
        if path == "/health":
            return self._send(200, {"ok": True, "profiles": len(REC.profiles)})

        uid = self._auth()
        if path in ("/api/jobs/match", "/api/jobs/mine", "/api/jobs/candidates"):
            if not uid:
                return self._send(401, {"error": "auth"})
            if path == "/api/jobs/match":
                prof = USERS[uid].get("profile")
                if not prof:
                    return self._send(400, {"error": "no_profile"})
                skills = REC._features(prof)["skills"]
                by_id = {v["id"]: v for v in all_vacancies()}
                ms = jobs.match_jobs(prof, skills, all_vacancies(), lang, exclude_owner=uid)
                return self._send(200, {"matches": [dict(vacancy_card(by_id[m["id"]], lang, uid), **m) for m in ms]})
            if path == "/api/jobs/mine":
                mine = [v for v in all_vacancies() if v.get("owner") == uid]
                out = []
                for v in sorted(mine, key=lambda v: -v.get("created", 0)):
                    card = vacancy_card(v, lang, uid)
                    card["applicants"] = [dict(person(a["uid"], lang) or {"id": a["uid"], "name": "?"}, ts=a["ts"])
                                          for a in APPS.get(v["id"], [])]
                    out.append(card)
                return self._send(200, {"vacancies": out})
            v = get_vacancy((qs.get("id") or [""])[0])
            if not v:
                return self._send(404, {"error": "no such vacancy"})
            if v.get("owner") != uid:
                return self._send(403, {"error": "not_owner"})
            return self._send(200, {"candidates": jobs.match_candidates(v, list(REC.profiles.values()), REC.feats, lang)})
        if path == "/api/me":
            return self._send(200, me_payload(uid)) if uid else self._send(401, {"error": "auth"})
        if path == "/api/chats":
            if not uid:
                return self._send(401, {"error": "auth"})
            out = []
            with LOCK:
                mark_seen(uid)
                for key in CHATS["conv"]:
                    a, b = key.split("|")
                    if uid not in (a, b):
                        continue
                    peer = b if a == uid else a
                    msgs = msgs_for(uid, key)
                    if not msgs:
                        continue
                    last_read = CHATS["read"].get(uid, {}).get(key, 0)
                    info = person(peer, lang) or {"id": peer, "name": "?"}
                    pending = len(msgs_for(uid, key, include_pending=True)) > len(msgs)
                    out.append({"peer": info, "last": with_status(uid, key, msgs[-1:])[0],
                                "typing": pending or is_typing(peer, uid),
                                "unread": sum(1 for m in msgs if m["from"] == peer and m["ts"] > last_read)})
            out.sort(key=lambda c: -c["last"]["ts"])
            return self._send(200, {"chats": out, "unread": sum(c["unread"] for c in out)})
        if path == "/api/chat":
            if not uid:
                return self._send(401, {"error": "auth"})
            peer = (qs.get("with") or [""])[0]
            info = person(peer, lang)
            if not info or peer == uid:
                return self._send(404, {"error": "no such person"})
            with LOCK:
                key = conv_key(uid, peer)
                msgs = msgs_for(uid, key)
                mark_seen(uid)
                if (qs.get("read") or ["1"])[0] != "0":
                    CHATS["read"].setdefault(uid, {})[key] = time.time()
                pending = len(msgs_for(uid, key, include_pending=True)) > len(msgs)
                msgs = with_status(uid, key, msgs)
            return self._send(200, {"peer": info, "messages": msgs, "can_send": can_send(uid, peer),
                                    "typing": pending or is_typing(peer, uid)})
        return self._send(404, {"error": "not found"})

    # ---------------- POST
    def do_POST(self):
        path = urlparse(self.path).path
        data = self._body()
        lang = data.get("lang") if data.get("lang") in LANG_LABELS else "ru"

        # ---- auth
        if path == "/api/register":
            username = str(data.get("username") or "").strip().lower()
            password = str(data.get("password") or "")
            name = str(data.get("name") or "").strip()[:60]
            if not USERNAME_RE.match(username):
                return self._send(400, {"error": "username"})
            if len(password) < 6:
                return self._send(400, {"error": "password"})
            if not name:
                return self._send(400, {"error": "name"})
            with LOCK:
                if any((u.get("account") or {}).get("username") == username for u in USERS.values()):
                    return self._send(409, {"error": "taken"})
                uid = "a-" + uuid.uuid4().hex[:10]
                salt = secrets.token_hex(16)
                USERS[uid] = {"account": {"username": username, "name": name, "salt": salt,
                                          "hash": hash_pw(password, salt), "created": int(time.time())},
                              "profile": None, "visible": True}
                token = secrets.token_urlsafe(32)
                SESSIONS[token] = uid
                save_json(USERS_FILE, USERS)
                save_json(SESSIONS_FILE, SESSIONS)
            return self._send(200, {"token": token, "me": me_payload(uid)})
        if path == "/api/login":
            username = str(data.get("username") or "").strip().lower()
            password = str(data.get("password") or "")
            with LOCK:
                uid = next((k for k, u in USERS.items() if (u.get("account") or {}).get("username") == username), None)
                acc = USERS[uid]["account"] if uid else None
                if not acc or not hmac.compare_digest(acc["hash"], hash_pw(password, acc["salt"])):
                    return self._send(401, {"error": "credentials"})
                token = secrets.token_urlsafe(32)
                SESSIONS[token] = uid
                save_json(SESSIONS_FILE, SESSIONS)
            return self._send(200, {"token": token, "me": me_payload(uid)})
        if path == "/api/logout":
            h = self.headers.get("Authorization", "")
            with LOCK:
                SESSIONS.pop(h[7:].strip(), None)
                save_json(SESSIONS_FILE, SESSIONS)
            return self._send(200, {"ok": True})

        # ---- profile without an event (needed for the job board)
        if path == "/api/profile":
            uid = self._auth()
            if not uid:
                return self._send(401, {"error": "auth"})
            acc = USERS[uid].get("account") or {}
            profile = clean_profile(data.get("profile") or {}, uid, name=acc.get("name"))
            visible = bool(data.get("visible", True))
            with LOCK:
                USERS[uid]["profile"], USERS[uid]["visible"] = profile, visible
                if visible:
                    REC.add(profile)
                elif uid in REC.profiles:
                    REC.remove(uid)
                save_json(USERS_FILE, USERS)
            return self._send(200, {"ok": True, "me": me_payload(uid)})

        # ---- hall seat
        if path == "/api/events/seat":
            uid = self._auth()
            if not uid:
                return self._send(401, {"error": "auth"})
            eid = str(data.get("event_id") or "")
            if uid not in REG.get(eid, []):
                return self._send(403, {"error": "not_registered"})
            zone = str(data.get("zone") or "").upper()
            try:
                table = int(data.get("table"))
            except (TypeError, ValueError):
                table = 0
            if zone not in ZONE_IDS or not 1 <= table <= TABLES:
                return self._send(400, {"error": "seat"})
            with LOCK:
                SEATS.setdefault(eid, {})[uid] = {"zone": zone, "table": table}
                save_json(SEATS_FILE, SEATS)
            return self._send(200, {"seat": SEATS[eid][uid]})

        # ---- job board (works without events)
        if path in ("/api/jobs/create", "/api/jobs/delete", "/api/jobs/apply"):
            uid = self._auth()
            if not uid:
                return self._send(401, {"error": "auth"})
            if path == "/api/jobs/create":
                role = data.get("role") if data.get("role") in ROLES else None
                level = data.get("level") if data.get("level") in jobs.LEVELS else "middle"
                fmt = data.get("format") if data.get("format") in jobs.FORMATS else "office"
                if not role or role in ("hr", "founder", "student"):
                    return self._send(400, {"error": "vac_role"})
                stack = data.get("stack") or []
                if isinstance(stack, str):
                    stack = stack.split(",")
                stack = [str(s).strip().lower() for s in stack if str(s).strip()][:12] if isinstance(stack, list) else []
                try:
                    sal = max(0, int(data.get("salary_from") or 0)) or None
                except (TypeError, ValueError):
                    sal = None
                desc = str(data.get("description") or "").strip()[:1500]
                prof = USERS[uid].get("profile") or {}
                v = {"id": "v-" + uuid.uuid4().hex[:8], "owner": uid, "role": role, "level": level, "stack": stack,
                     "format": fmt, "city": str(data.get("city") or "").strip()[:60], "salary_from": sal,
                     "title": str(data.get("title") or "").strip()[:100] or None,
                     "company": str(data.get("company") or prof.get("company") or "").strip()[:80],
                     "description": {"ru": desc, "kk": desc, "en": desc}, "created": int(time.time())}
                with LOCK:
                    USER_VAC.append(v)
                    save_json(USER_VAC_FILE, USER_VAC)
                return self._send(200, {"vacancy": vacancy_card(v, lang, uid)})
            v = get_vacancy(str(data.get("id") or ""))
            if not v:
                return self._send(404, {"error": "no such vacancy"})
            if path == "/api/jobs/delete":
                if v.get("owner") != uid:
                    return self._send(403, {"error": "not_owner"})
                with LOCK:
                    USER_VAC[:] = [x for x in USER_VAC if x["id"] != v["id"]]
                    APPS.pop(v["id"], None)
                    save_json(USER_VAC_FILE, USER_VAC)
                    save_json(APPS_FILE, APPS)
                return self._send(200, {"ok": True})
            # apply
            if v.get("owner") == uid:
                return self._send(400, {"error": "own_vacancy"})
            target = person(v["owner"], lang)
            if not target:
                return self._send(404, {"error": "no such person"})
            prof = USERS[uid].get("profile") or {"role": "student", "experience_years": 0}
            text = str(data.get("text") or "").strip()[:MAX_MSG] or \
                jobs.apply_text(v, prof, REC._features(prof)["skills"] if prof.get("stack") is not None else set(), lang)
            with LOCK:
                apps = APPS.setdefault(v["id"], [])
                already = any(a["uid"] == uid for a in apps)
                if not already:
                    apps.append({"uid": uid, "ts": time.time()})
                    save_json(APPS_FILE, APPS)
            msg = send_message(uid, v["owner"], text, lang, target)
            return self._send(200, {"ok": True, "messaged": bool(msg), "already": already,
                                    "owner": v["owner"], "vacancy": vacancy_card(v, lang, uid)})

        # ---- events
        if path in ("/api/events/join", "/api/events/leave", "/api/events/active", "/api/events/create"):
            uid = self._auth()
            if not uid:
                return self._send(401, {"error": "auth"})
            if path == "/api/events/create":
                name = str(data.get("name") or "").strip()[:100]
                etype = data.get("type") if data.get("type") in EVENT_TYPES else "meetup"
                date = str(data.get("date") or "")[:10]
                if len(name) < 3:
                    return self._send(400, {"error": "event_name"})
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
                    return self._send(400, {"error": "event_date"})
                desc = str(data.get("description") or "").strip()[:500]
                ev = {"id": "e-" + uuid.uuid4().hex[:8], "type": etype, "name": name, "date": date,
                      "city": str(data.get("city") or "").strip()[:60], "place": str(data.get("place") or "").strip()[:100],
                      "description": {"ru": desc, "kk": desc, "en": desc}, "participants": [], "owner": uid}
                with LOCK:
                    USER_EVENTS.append(ev)
                    REG.setdefault(ev["id"], []).append(uid)
                    USERS[uid]["active_event"] = ev["id"]
                    SEATS.setdefault(ev["id"], {})[uid] = {"zone": "A", "table": 1}
                    save_json(SEATS_FILE, SEATS)
                    save_json(USER_EVENTS_FILE, USER_EVENTS)
                    save_json(REGISTRATIONS_FILE, REG)
                    save_json(USERS_FILE, USERS)
                return self._send(200, {"event": event_card(ev, lang, uid), "me": me_payload(uid)})
            eid = str(data.get("event_id") or "")
            ev = get_event(eid)
            if not ev:
                return self._send(404, {"error": "no such event"})
            with LOCK:
                regs = REG.setdefault(eid, [])
                if path == "/api/events/join":
                    if uid not in regs:
                        regs.append(uid)
                    USERS[uid]["active_event"] = eid
                    if uid not in SEATS.get(eid, {}):
                        SEATS.setdefault(eid, {})[uid] = default_seat(uid, eid, USERS[uid].get("profile"))
                        save_json(SEATS_FILE, SEATS)
                elif path == "/api/events/leave":
                    if uid in regs:
                        regs.remove(uid)
                    if USERS[uid].get("active_event") == eid:
                        mine = [k for k, us in REG.items() if uid in us and get_event(k)]
                        USERS[uid]["active_event"] = mine[0] if mine else None
                else:  # active
                    if uid not in regs:
                        return self._send(403, {"error": "not_registered"})
                    USERS[uid]["active_event"] = eid
                save_json(REGISTRATIONS_FILE, REG)
                save_json(USERS_FILE, USERS)
            return self._send(200, {"event": event_card(ev, lang, uid), "me": me_payload(uid)})

        # ---- recommendations
        if path == "/api/recommend":
            uid = self._uid(data, create=True)
            if not uid:
                return self._send(401, {"error": "auth"})
            acc = (USERS.get(uid) or {}).get("account")
            eid = resolve_event(uid, data)
            if acc and eid and uid not in REG.get(eid, []):
                return self._send(403, {"error": "not_registered"})
            if acc and not eid:
                return self._send(400, {"error": "no_event"})
            profile = clean_profile(data.get("profile") or {}, uid, name=acc["name"] if acc else None)
            visible = bool(data.get("visible", bool(acc)))
            with LOCK:
                entry = USERS.setdefault(uid, {})
                entry["profile"], entry["visible"] = profile, visible
                if visible:
                    REC.add(profile)
                elif uid in REC.profiles:
                    REC.remove(uid)
                save_json(USERS_FILE, USERS)
                res = REC.recommend(profile, lang=lang, user_id=uid, pool=event_pool(eid) if eid else None)
            res["user_id"] = uid
            ev = get_event(eid) if eid else None
            res["event"] = {"id": ev["id"], "name": ev["name"]} if ev else None
            if ev:
                for r in res["recommendations"]:
                    r["seat"] = seat_of(r["id"], ev["id"])
                res["my_seat"] = seat_of(uid, ev["id"])
            return self._send(200, res)
        if path == "/api/feedback":
            uid, target, kind = self._uid(data), data.get("target_id"), data.get("type")
            if not uid or not (USERS.get(uid) or {}).get("profile") or kind not in ("met", "no", "undo"):
                return self._send(400, {"error": "bad request"})
            with LOCK:
                REC.add_feedback(uid, target, kind)
                save_json(FEEDBACK_FILE, REC.feedback)
                eid = resolve_event(uid, data)
                res = REC.recommend(USERS[uid]["profile"], lang=lang, user_id=uid,
                                    pool=event_pool(eid) if eid else None)
            res["user_id"] = uid
            ev = get_event(eid) if eid else None
            res["event"] = {"id": ev["id"], "name": ev["name"]} if ev else None
            if ev:
                for r in res["recommendations"]:
                    r["seat"] = seat_of(r["id"], ev["id"])
                res["my_seat"] = seat_of(uid, ev["id"])
            res["history"] = REC.history(uid, lang)
            return self._send(200, res)
        if path == "/api/history":
            uid = self._uid(data)
            if not uid:
                return self._send(200, {"history": [], "profile": None})
            return self._send(200, {"history": REC.history(uid, lang), "profile": USERS[uid].get("profile"),
                                    "visible": USERS[uid].get("visible", False)})

        # ---- chat
        if path == "/api/chat/send":
            uid = self._auth()
            if not uid:
                return self._send(401, {"error": "auth"})
            to = str(data.get("to") or "")
            text = str(data.get("text") or "").strip()[:MAX_MSG]
            target = person(to, lang)
            if not target or to == uid:
                return self._send(404, {"error": "no such person"})
            if not text:
                return self._send(400, {"error": "empty"})
            msg = send_message(uid, to, text, lang, target)
            if not msg:
                return self._send(409, {"error": "wait_reply"})
            return self._send(200, {"message": msg, "can_send": can_send(uid, to)})
        if path == "/api/chat/typing":
            uid = self._auth()
            if not uid:
                return self._send(401, {"error": "auth"})
            to = str(data.get("to") or "")
            if to and to != uid and person(to):
                TYPING[(uid, to)] = time.time()
            return self._send(200, {"ok": True})
        if path == "/api/chat/delete":
            uid = self._auth()
            if not uid:
                return self._send(401, {"error": "auth"})
            peer = str(data.get("with") or "")
            key = conv_key(uid, peer)
            if key not in CHATS["conv"]:
                return self._send(404, {"error": "no such chat"})
            scope = "all" if data.get("scope") == "all" else "me"
            with LOCK:
                # "me": hide for me only, the other person keeps their copy; "all": remove for both
                CHATS.setdefault("deleted", {}).setdefault(uid, {})[key] = time.time()
                peer_is_demo = bool((REC.profiles.get(peer) or {}).get("synthetic"))
                if peer_is_demo or scope == "all":
                    for d in CHATS["deleted"].values():
                        d.pop(key, None)
                    for r in CHATS["read"].values():
                        r.pop(key, None)
                    CHATS["conv"].pop(key, None)    # demo profiles have no copy to keep -> start fresh
                    CHATS["deleted"][uid].pop(key, None)
                save_json(CHATS_FILE, CHATS)
            return self._send(200, {"ok": True})
        return self._send(404, {"error": "not found"})


def main():
    port = int(os.environ.get("PORT", 8090))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Tanys: {len(REC.profiles)} profiles loaded -> http://localhost:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
