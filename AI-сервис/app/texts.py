"""Template-based explanations and icebreakers in ru / kk / en (no LLM needed, < 1 ms)."""
import re
from .catalog import ROLES, INTERESTS, GOAL_LABELS, RELATED_ROLES


def _exp(years, lang):
    if lang == "ru":
        if years == 0:
            return "без опыта"
        return f"{years} " + ("год" if years % 10 == 1 and years != 11 else "года" if 2 <= years % 10 <= 4 and not 12 <= years <= 14 else "лет")
    if lang == "kk":
        return "тәжірибесіз" if years == 0 else f"{years} жыл"
    return "no experience" if years == 0 else f"{years} yr"


def _roles(lst, lang):
    return ", ".join(ROLES[r][lang] for r in lst)


T = {
    "ru": {
        "job_seek": "{name} нанимает ({roles}) — это совпадает с вашей ролью «{urole}».",
        "job_seek_rel": "{name} нанимает ({roles}) — смежное направление с вашей ролью «{urole}».",
        "job_seek_other": "{name} нанимает в команду ({roles}) — стоит спросить и о вакансиях для «{urole}».",
        "hire": "{name} ищет работу: {role} ({exp}).",
        "find_mentor": "{name} — {role} с опытом {exp} и хочет менторить начинающих.",
        "be_mentor": "{name} ({role}, {exp}) ищет ментора — у вас на {gap} лет больше опыта.",
        "cof_comp": "{name} — {role} и тоже ищет кофаундера: вместе вы закрываете и технологии, и бизнес.",
        "cof_same": "{name} — {role} и тоже ищет кофаундера.",
        "exchange": "{name} — {role}, тоже хочет обменяться опытом.",
        "fallback": " (Прямых совпадений по цели мало — это близкий по смыслу вариант.)",
        "shared": "Общее: {parts}.",
        "sk": "стек — {x}", "in": "интересы — {x}",
        "text": "Похожие темы в описании профиля.",
        "ib_inter": "Привет! Вижу, тебе тоже интересна тема «{i}». Над чем сейчас работаешь?",
        "ib_skill": "Привет! Ты тоже работаешь с {s}? Какой самый интересный проект на нём был?",
        "ib_job_seek": "Здравствуйте! Я {urole}. Расскажете, кого вы сейчас ищете в команду?",
        "ib_hire": "Привет! Мы сейчас нанимаем{sk}. Расскажешь, какой проект хочешь делать дальше?",
        "ib_find_mentor": "Здравствуйте! Хочу расти как {urole}. Можно пару вопросов о вашем карьерном пути?",
        "ib_be_mentor": "Привет! Вижу, ты ищешь ментора. Какая сейчас главная цель в развитии?",
        "ib_find_cofounder": "Привет! Ты тоже ищешь кофаундера — какую проблему хочешь решать?",
        "ib_exchange": "Привет! Какой самый полезный инсайт из работы был у тебя за последний месяц?",
        "ib_js_skill": "Здравствуйте! Я {urole}, работаю с {s}. Вам сейчас нужны такие люди в команду?",
        "ib_mentor_student": "Здравствуйте! Я {urole}. Подскажете, с чего лучше начать путь в профессии?",
        "booth_i": "Совпадает с интересами: {x}", "booth_g": "Подходит для цели «{g}»",
    },
    "kk": {
        "job_seek": "{name} маман іздейді ({roles}) — бұл сіздің «{urole}» рөліңізге сәйкес.",
        "job_seek_rel": "{name} маман іздейді ({roles}) — сіздің «{urole}» рөліңізге жақын бағыт.",
        "job_seek_other": "{name} командаға маман іздейді ({roles}) — «{urole}» үшін бос орын бар-жоғын сұраған жөн.",
        "hire": "{name} жұмыс іздейді: {role} ({exp}).",
        "find_mentor": "{name} — {role}, тәжірибесі {exp}, жаңадан бастағандарға менторлық жасағысы келеді.",
        "be_mentor": "{name} ({role}, {exp}) ментор іздейді — сіздің тәжірибеңіз {gap} жылға көп.",
        "cof_comp": "{name} — {role}, ол да серіктес іздейді: бірге технологияны да, бизнесті де қамтисыздар.",
        "cof_same": "{name} — {role}, ол да серіктес іздейді.",
        "exchange": "{name} — {role}, ол да тәжірибе алмасқысы келеді.",
        "fallback": " (Мақсат бойынша тікелей сәйкестік аз — бұл мағынасы жақын нұсқа.)",
        "shared": "Ортақ: {parts}.",
        "sk": "стек — {x}", "in": "қызығушылықтар — {x}",
        "text": "Профиль сипаттамаларындағы тақырыптар ұқсас.",
        "ib_inter": "Сәлем! «{i}» тақырыбы саған да қызық екен. Қазір не істеп жатырсың?",
        "ib_skill": "Сәлем! Сен де {s} қолданасың ба? Ең қызық жобаң қандай болды?",
        "ib_job_seek": "Сәлеметсіз бе! Мен — {urole}. Қазір командаға қандай маман іздеп жатырсыз?",
        "ib_hire": "Сәлем! Біз қазір маман іздеп жатырмыз{sk}. Келесі қандай жобамен айналысқың келеді?",
        "ib_find_mentor": "Сәлеметсіз бе! {urole} ретінде өскім келеді. Мансап жолыңыз туралы бірнеше сұрақ қоюға бола ма?",
        "ib_be_mentor": "Сәлем! Ментор іздеп жүргеніңді көрдім. Қазіргі басты мақсатың қандай?",
        "ib_find_cofounder": "Сәлем! Сен де серіктес іздейсің — қандай мәселені шешкің келеді?",
        "ib_exchange": "Сәлем! Соңғы айдағы жұмысыңнан ең пайдалы түйгенің не болды?",
        "ib_js_skill": "Сәлеметсіз бе! Мен — {urole}, {s} қолданамын. Командаңызға осындай маман керек пе?",
        "ib_mentor_student": "Сәлеметсіз бе! Мен — {urole}. Мамандықта жолды неден бастаған дұрыс?",
        "booth_i": "Қызығушылықтарыңызға сәйкес: {x}", "booth_g": "«{g}» мақсатына сай",
    },
    "en": {
        "job_seek": "{name} is hiring ({roles}) — a match for your role “{urole}”.",
        "job_seek_rel": "{name} is hiring ({roles}) — close to your role “{urole}”.",
        "job_seek_other": "{name} is hiring ({roles}) — worth asking about openings for a “{urole}”.",
        "hire": "{name} is looking for a job: {role} ({exp}).",
        "find_mentor": "{name} is a {role} with {exp} of experience and wants to mentor newcomers.",
        "be_mentor": "{name} ({role}, {exp}) is looking for a mentor — you have {gap} more years of experience.",
        "cof_comp": "{name} is a {role} also looking for a co-founder: together you cover both tech and business.",
        "cof_same": "{name} is a {role} also looking for a co-founder.",
        "exchange": "{name} is a {role} who also wants to exchange experience.",
        "fallback": " (Few direct goal matches — this is the closest alternative.)",
        "shared": "In common: {parts}.",
        "sk": "stack — {x}", "in": "interests — {x}",
        "text": "Similar topics in your profile descriptions.",
        "ib_inter": "Hi! I see you're into {i} too. What are you working on right now?",
        "ib_skill": "Hi! You also work with {s}? What's the coolest project you've built with it?",
        "ib_job_seek": "Hi! I'm a {urole}. What kind of people are you looking for on your team?",
        "ib_hire": "Hi! We're hiring{sk}. What kind of project would you like to work on next?",
        "ib_find_mentor": "Hi! I want to grow as a {urole}. Could I ask a couple of questions about your career path?",
        "ib_be_mentor": "Hi! I saw you're looking for a mentor. What's your main growth goal right now?",
        "ib_find_cofounder": "Hi! You're looking for a co-founder too — what problem do you want to solve?",
        "ib_exchange": "Hi! What's the most useful insight from your work this past month?",
        "ib_js_skill": "Hi! I'm a {urole} working with {s}. Are you looking for people like that on your team?",
        "ib_mentor_student": "Hi! I'm a {urole}. Where would you recommend starting in this field?",
        "booth_i": "Matches your interests: {x}", "booth_g": "Fits your goal “{g}”",
    },
}


def explain(u, c, goal, comp, shared_skills, shared_inter, lang):
    t = T[lang]
    name, role = c["name"], ROLES[c["role"]][lang]
    urole = ROLES[u["role"]][lang]
    exp = _exp(c.get("experience_years", 0), lang)
    cg = c["goal"]
    if cg == "hire":
        hr = c.get("hiring_roles") or [c["role"]]
        hr = sorted(hr, key=lambda r: (r != u["role"], r not in RELATED_ROLES.get(u["role"], ())))
        if u["role"] in hr:
            key = "job_seek"
        elif any(r in RELATED_ROLES.get(u["role"], ()) for r in hr) or u["role"] == "student":
            key = "job_seek_rel"
        else:
            key = "job_seek_other"
        s1 = t[key].format(name=name, roles=_roles(hr, lang), urole=urole)
    elif cg == "job_seek":
        s1 = t["hire"].format(name=name, role=role, exp=exp)
    elif cg == "be_mentor":
        s1 = t["find_mentor"].format(name=name, role=role, exp=exp)
    elif cg == "find_mentor":
        gap = max(u.get("experience_years", 0) - c.get("experience_years", 0), 1)
        s1 = t["be_mentor"].format(name=name, role=role, exp=exp, gap=gap)
    elif cg == "find_cofounder":
        comp_team = ROLES[u["role"]]["tech"] != ROLES[c["role"]]["tech"]
        s1 = t["cof_comp" if comp_team else "cof_same"].format(name=name, role=role)
    else:
        s1 = t["exchange"].format(name=name, role=role)
    if cg not in _primary_of(goal):
        s1 += t["fallback"]

    parts = []
    if shared_skills:
        parts.append(t["sk"].format(x=", ".join(shared_skills[:3])))
    if shared_inter:
        parts.append(t["in"].format(x=", ".join(INTERESTS[i][lang] for i in shared_inter[:2] if i in INTERESTS)))
    if parts:
        s2 = t["shared"].format(parts="; ".join(parts))
    elif comp.get("text", 0) > 0.08:
        s2 = t["text"]
    else:
        s2 = ""
    return (s1 + " " + s2).strip()


def _primary_of(goal):
    from .catalog import GOAL_PRIMARY
    return GOAL_PRIMARY[goal]


def icebreaker(u, c, goal, shared_skills, shared_inter, lang):
    t = T[lang]
    urole = ROLES[u["role"]][lang].lower() if lang != "en" else ROLES[u["role"]][lang]
    if u["role"] == "student":
        sk = ", ".join((shared_skills or u.get("stack") or ["IT"])[:2])
        urole = {"ru": f"студент, изучаю {sk}", "kk": f"{sk} үйреніп жүрген студент",
                 "en": f"student learning {sk}"}[lang]
    if goal == "hire":
        sk = f" ({', '.join(shared_skills[:2])})" if shared_skills else ""
        return t["ib_hire"].format(sk=sk)
    if goal == "job_seek" and shared_skills:
        return t["ib_js_skill"].format(urole=urole, s=", ".join(shared_skills[:2]))
    if goal == "find_mentor" and u["role"] == "student":
        return t["ib_mentor_student"].format(urole=urole)
    if goal in ("job_seek", "find_mentor"):
        return t["ib_" + goal].format(urole=urole)
    if shared_inter and shared_inter[0] in INTERESTS:
        return t["ib_inter"].format(i=INTERESTS[shared_inter[0]][lang])
    if shared_skills:
        return t["ib_skill"].format(s=shared_skills[0])
    return t["ib_" + goal].format(urole=urole)


REPLY = {
    "ru": {
        "hire": "Привет! Да, мы сейчас нанимаем. Расскажи коротко о своём опыте — и давай встретимся у стенда{slot}.",
        "job_seek": "Здравствуйте! Спасибо, что написали. Да, я ищу работу — с удовольствием пообщаюсь{slot}.",
        "be_mentor": "Привет! Конечно, помогу чем смогу. Подготовь 2–3 вопроса — обсудим{slot}.",
        "find_mentor": "Здравствуйте! Спасибо, что написали — мне как раз нужен ментор. Можем встретиться{slot}?",
        "find_cofounder": "Привет! Да, ищу кофаундера. Интересно узнать про твою идею — давай встретимся{slot}.",
        "exchange": "Привет! С удовольствием обменяюсь опытом. Предлагаю пересечься{slot}.",
        "slot": " в {s}", "demo": "демо-ответ",
    },
    "kk": {
        "hire": "Сәлем! Иә, біз қазір маман іздеп жатырмыз. Тәжірибең туралы қысқаша айтып берші — стенд жанында кездесейік{slot}.",
        "job_seek": "Сәлеметсіз бе! Жазғаныңызға рахмет. Иә, жұмыс іздеп жүрмін — қуана сөйлесемін{slot}.",
        "be_mentor": "Сәлем! Әрине, қолымнан келгенше көмектесемін. 2–3 сұрақ дайында — талқылаймыз{slot}.",
        "find_mentor": "Сәлеметсіз бе! Өте қуаныштымын — маған дәл ментор керек. Кездесейік{slot}?",
        "find_cofounder": "Сәлем! Иә, серіктес іздеп жүрмін. Идеяң туралы білгім келеді — кездесейік{slot}.",
        "exchange": "Сәлем! Тәжірибе алмасуға қуаныштымын. Кездесіп сөйлесейік{slot}.",
        "slot": " сағат {s}-де", "demo": "демо-жауап",
    },
    "en": {
        "hire": "Hi! Yes, we're hiring right now. Tell me briefly about your experience — let's meet at the booth{slot}.",
        "job_seek": "Hi! Thanks for reaching out. Yes, I'm looking for a job — happy to chat{slot}.",
        "be_mentor": "Hi! Sure, happy to help. Prepare 2–3 questions and we'll discuss them{slot}.",
        "find_mentor": "Hi! Great to hear from you — I'm looking for a mentor. Can we meet{slot}?",
        "find_cofounder": "Hi! Yes, I'm looking for a co-founder. Curious about your idea — let's meet{slot}.",
        "exchange": "Hi! Happy to exchange experience. Let's catch up{slot}.",
        "slot": " at {s}", "demo": "demo reply",
    },
}


def auto_reply(peer, lang, slot=None):
    t = REPLY.get(lang, REPLY["ru"])
    s = t["slot"].format(s=slot) if slot else ""
    return t.get(peer.get("goal"), t["exchange"]).format(slot=s)


FOLLOW = {
    "ru": {
        "time": ["Отлично, в {t} подходит! Встречаемся у главного входа.", "Договорились — {t}. Я буду в синей футболке с бейджем."],
        "thanks": ["Всегда пожалуйста! До встречи на мероприятии.", "Не за что! Приятно познакомиться."],
        "bye": ["До встречи!", "Увидимся! Хорошего дня."],
        "job": ["Сейчас открыты позиции: {roles}. Пришли резюме или просто подойди к стенду — поговорим.",
                "Да, вакансии есть — {roles}. Можно пройти короткое собеседование прямо здесь."],
        "stack": ["Я в основном работаю с {stack}. А какой у тебя стек?", "Мой стек — {stack}. Интересно, над чем ты сейчас работаешь?"],
        "question": ["Хороший вопрос! Давай обсудим это при встрече — так будет удобнее.", "Сложно ответить коротко 🙂 Давай встретимся, расскажу подробнее."],
        "meet": ["Давай! У меня свободно в {slots}. Какое время удобно?", "С удовольствием. Могу в {slots}."],
        "default": ["Звучит интересно! Давай продолжим вживую — когда удобно встретиться?",
                    "Классно! Расскажешь подробнее при встрече? У меня свободно в {slots}.",
                    "Хорошая мысль. Предлагаю пересечься на мероприятии — так быстрее договоримся."],
    },
    "kk": {
        "time": ["Тамаша, {t} маған ыңғайлы! Бас кіреберісте кездесейік.", "Келістік — {t}. Бейджім бар, оңай табасың."],
        "thanks": ["Оқасы жоқ! Іс-шарада кездескенше.", "Рахмет өзіңе! Танысқаныма қуаныштымын."],
        "bye": ["Кездескенше!", "Көріскенше! Күніңіз сәтті өтсін."],
        "job": ["Қазір ашық позициялар: {roles}. Түйіндемеңді жібер немесе стендке кел — сөйлесеміз.",
                "Иә, бос орындар бар — {roles}. Қысқа сұхбатты осында өтуге болады."],
        "stack": ["Мен негізінен {stack} қолданамын. Сенің стегің қандай?", "Менің стегім — {stack}. Қазір не істеп жатырсың?"],
        "question": ["Жақсы сұрақ! Кездескенде талқылайық — солай ыңғайлырақ.", "Қысқаша жауап беру қиын 🙂 Кездесейік, толығырақ айтамын."],
        "meet": ["Келістік! Мен {slots} босмын. Саған қай уақыт ыңғайлы?", "Қуана. {slots} кездесе аламын."],
        "default": ["Түсіндім, қызық екен! Жүзбе-жүз жалғастырайық — қашан кездескен ыңғайлы?",
                    "Керемет! Кездескенде толығырақ айтып бересің бе? Мен {slots} босмын.",
                    "Келісемін. Іс-шарада кездесейік — солай тезірек келісеміз."],
    },
    "en": {
        "time": ["Great, {t} works for me! Let's meet at the main entrance.", "Deal — {t}. I'll be wearing my badge."],
        "thanks": ["You're welcome! See you at the event.", "No problem! Nice to meet you."],
        "bye": ["See you!", "See you there! Have a great day."],
        "job": ["We have open roles: {roles}. Send your CV or just come to the booth — let's talk.",
                "Yes, we're hiring — {roles}. We can do a short interview right here."],
        "stack": ["I mostly work with {stack}. What's your stack?", "My stack is {stack}. What are you working on now?"],
        "question": ["Good question! Let's discuss it in person — easier that way.", "Hard to answer briefly 🙂 Let's meet and I'll tell you more."],
        "meet": ["Sure! I'm free at {slots}. What time works for you?", "Happy to. I can do {slots}."],
        "default": ["Got it, sounds interesting! Let's continue in person — when is good for you?",
                    "Cool! Tell me more when we meet? I'm free at {slots}.",
                    "Agreed. Let's catch up at the event — faster to sort things out."],
    },
}

_TIME = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")
_KW = {
    "thanks": ["спасиб", "рахмет", "thank", "thx", "благодар"],
    "bye": ["до встреч", "пока", "көріскенше", "кездескенше", "bye", "see you"],
    "job": ["ваканс", "работ", "позици", "резюме", "бос орын", "жұмыс", "vacanc", "job", "position", "hiring", "cv", "нанима", "стажир"],
    "stack": ["стек", "stack", "технолог", "на чём", "на чем", "қолдан", "tech"],
    "meet": ["встрет", "встреч", "кездес", "meet", "увид", "когда", "қашан", "when"],
}


def follow_reply(peer, text, lang, n_prev=0):
    """Rule-based conversational reply of a demo profile to any later message."""
    t = FOLLOW.get(lang, FOLLOW["ru"])
    low = text.lower()
    slots = ", ".join((peer.get("slots") or ["15:00"])[:2])
    roles = ", ".join(ROLES[r][lang] for r in (peer.get("hiring_roles") or [peer["role"]]))
    stack = ", ".join(peer.get("stack", [])[:3]) or "—"
    m = _TIME.search(low)
    if m:
        kind, fmt = "time", {"t": f"{int(m.group(1)):02d}:{m.group(2)}"}
    else:
        kind = next((k for k in ("thanks", "bye", "job", "stack", "meet") if any(w in low for w in _KW[k])), None)
        if kind == "job" and peer.get("goal") != "hire":
            kind = "question"
        if kind is None:
            kind = "question" if "?" in low else "default"
        fmt = {"slots": slots, "roles": roles, "stack": stack}
    opts = t[kind]
    return opts[n_prev % len(opts)].format(**fmt)


def booth_why(b, inter, goal, lang):
    t = T[lang]
    common = [INTERESTS[i][lang] for i in b["tags"] if i in inter]
    if common:
        return t["booth_i"].format(x=", ".join(common))
    return t["booth_g"].format(g=GOAL_LABELS[goal][lang])
