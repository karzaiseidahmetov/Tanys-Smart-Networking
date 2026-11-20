"""Shared dictionaries: roles, goals, skills, interests, aliases, i18n labels."""

GOALS = ["job_seek", "hire", "find_mentor", "be_mentor", "find_cofounder", "exchange"]

GOAL_LABELS = {
    "job_seek":       {"ru": "Найти работу",        "kk": "Жұмыс табу",            "en": "Find a job"},
    "hire":           {"ru": "Нанять",              "kk": "Қызметкер жалдау",      "en": "Hire"},
    "find_mentor":    {"ru": "Найти ментора",       "kk": "Ментор табу",           "en": "Find a mentor"},
    "be_mentor":      {"ru": "Стать ментором",      "kk": "Ментор болу",           "en": "Become a mentor"},
    "find_cofounder": {"ru": "Найти кофаундера",    "kk": "Серіктес-негізін қалаушы табу", "en": "Find a co-founder"},
    "exchange":       {"ru": "Обмен опытом",        "kk": "Тәжірибе алмасу",       "en": "Exchange experience"},
}

# Primary (strict) reciprocity: whose goal fits mine.
GOAL_PRIMARY = {
    "job_seek": ["hire"],
    "hire": ["job_seek"],
    "find_mentor": ["be_mentor"],
    "be_mentor": ["find_mentor"],
    "find_cofounder": ["find_cofounder"],
    "exchange": ["exchange"],
}
# Fallback tier, used only if primary pool is exhausted (never job_seek -> job_seek).
GOAL_SECONDARY = {
    "job_seek": ["be_mentor"],
    "hire": ["find_mentor"],
    "find_mentor": ["exchange"],
    "be_mentor": ["job_seek"],
    "find_cofounder": ["exchange"],
    "exchange": ["be_mentor", "find_cofounder"],
}

ROLES = {
    "backend":   {"ru": "Backend-разработчик",  "kk": "Backend-әзірлеуші",  "en": "Backend developer", "tech": True},
    "frontend":  {"ru": "Frontend-разработчик", "kk": "Frontend-әзірлеуші", "en": "Frontend developer", "tech": True},
    "mobile":    {"ru": "Mobile-разработчик",   "kk": "Mobile-әзірлеуші",   "en": "Mobile developer", "tech": True},
    "data_ml":   {"ru": "ML / Data Scientist",  "kk": "ML / Data Scientist", "en": "ML / Data Scientist", "tech": True},
    "analyst":   {"ru": "Аналитик данных",      "kk": "Дерек талдаушы",     "en": "Data analyst", "tech": True},
    "devops":    {"ru": "DevOps-инженер",       "kk": "DevOps-инженер",     "en": "DevOps engineer", "tech": True},
    "qa":        {"ru": "QA-инженер",           "kk": "QA-инженер",         "en": "QA engineer", "tech": True},
    "security":  {"ru": "Специалист по ИБ",     "kk": "Ақпараттық қауіпсіздік маманы", "en": "Security engineer", "tech": True},
    "gamedev":   {"ru": "GameDev-разработчик",  "kk": "GameDev-әзірлеуші",  "en": "Game developer", "tech": True},
    "design":    {"ru": "UI/UX-дизайнер",       "kk": "UI/UX-дизайнер",     "en": "UI/UX designer", "tech": False},
    "product":   {"ru": "Product / Project Manager", "kk": "Product / Project менеджер", "en": "Product / Project manager", "tech": False},
    "hr":        {"ru": "IT-рекрутер / HR",     "kk": "IT-рекрутер / HR",   "en": "IT recruiter / HR", "tech": False},
    "founder":   {"ru": "Фаундер / бизнес",     "kk": "Фаундер / бизнес",   "en": "Founder / business", "tech": False},
    "student":   {"ru": "Студент",              "kk": "Студент",            "en": "Student", "tech": True},
}

# Roles that are "close" to each other (partial credit).
RELATED_ROLES = {
    "backend": {"devops", "data_ml", "frontend", "qa", "security"},
    "frontend": {"backend", "mobile", "design"},
    "mobile": {"frontend", "backend"},
    "data_ml": {"analyst", "backend"},
    "analyst": {"data_ml", "product"},
    "devops": {"backend", "security"},
    "qa": {"backend", "frontend"},
    "security": {"devops", "backend"},
    "gamedev": {"frontend", "mobile", "design"},
    "design": {"frontend", "product"},
    "product": {"analyst", "design", "founder"},
    "hr": {"founder", "product"},
    "founder": {"product", "hr"},
    "student": set(),
}

ROLE_SKILLS = {
    "backend": ["python", "django", "fastapi", "postgresql", "redis", "docker", "go", "java", "spring", "node.js", "kafka", "rest api"],
    "frontend": ["javascript", "typescript", "react", "vue", "next.js", "css", "html", "figma"],
    "mobile": ["kotlin", "swift", "flutter", "react native", "firebase", "dart"],
    "data_ml": ["python", "pytorch", "tensorflow", "pandas", "sql", "llm", "nlp", "computer vision", "mlops", "scikit-learn"],
    "analyst": ["sql", "python", "power bi", "tableau", "excel", "pandas", "a/b testing"],
    "devops": ["docker", "kubernetes", "aws", "terraform", "ci/cd", "linux", "grafana", "ansible"],
    "qa": ["selenium", "pytest", "postman", "playwright", "java", "rest api"],
    "security": ["pentest", "linux", "network security", "siem", "python", "owasp"],
    "gamedev": ["unity", "c#", "unreal engine", "c++", "blender"],
    "design": ["figma", "ui/ux", "prototyping", "user research", "design systems"],
    "product": ["product management", "jira", "a/b testing", "sql", "scrum", "customer development"],
    "hr": ["it recruiting", "sourcing", "hr analytics", "employer branding"],
    "founder": ["business development", "fundraising", "sales", "marketing", "pitching"],
    "student": ["python", "c++", "java", "javascript", "sql", "html"],
}

ALL_SKILLS = sorted({s for v in ROLE_SKILLS.values() for s in v})

INTERESTS = {
    "ai":           {"ru": "ИИ и ML",          "kk": "ЖИ және ML",          "en": "AI & ML"},
    "llm":          {"ru": "LLM и агенты",     "kk": "LLM және агенттер",   "en": "LLMs & agents"},
    "fintech":      {"ru": "Финтех",           "kk": "Финтех",              "en": "Fintech"},
    "edtech":       {"ru": "EdTech",           "kk": "EdTech",              "en": "EdTech"},
    "govtech":      {"ru": "GovTech",          "kk": "GovTech",             "en": "GovTech"},
    "healthtech":   {"ru": "HealthTech",       "kk": "HealthTech",          "en": "HealthTech"},
    "ecommerce":    {"ru": "E-commerce",       "kk": "E-commerce",          "en": "E-commerce"},
    "startups":     {"ru": "Стартапы",         "kk": "Стартаптар",          "en": "Startups"},
    "opensource":   {"ru": "Open Source",      "kk": "Open Source",         "en": "Open source"},
    "cloud":        {"ru": "Облака и DevOps",  "kk": "Бұлт және DevOps",    "en": "Cloud & DevOps"},
    "cybersecurity": {"ru": "Кибербезопасность", "kk": "Киберқауіпсіздік",  "en": "Cybersecurity"},
    "gamedev":      {"ru": "Геймдев",          "kk": "Геймдев",             "en": "Game dev"},
    "mobile":       {"ru": "Мобильные приложения", "kk": "Мобильді қосымшалар", "en": "Mobile apps"},
    "data":         {"ru": "Данные и аналитика", "kk": "Деректер және аналитика", "en": "Data & analytics"},
    "design":       {"ru": "Дизайн и UX",      "kk": "Дизайн және UX",      "en": "Design & UX"},
    "product":      {"ru": "Продуктовое мышление", "kk": "Өнімдік ойлау",   "en": "Product thinking"},
    "career":       {"ru": "Карьера в IT",     "kk": "IT-дағы мансап",      "en": "IT career"},
    "hackathons":   {"ru": "Хакатоны",         "kk": "Хакатондар",          "en": "Hackathons"},
    "agritech":     {"ru": "AgriTech",         "kk": "AgriTech",            "en": "AgriTech"},
    "robotics":     {"ru": "Робототехника и IoT", "kk": "Робототехника және IoT", "en": "Robotics & IoT"},
    "web3":         {"ru": "Web3 и блокчейн",  "kk": "Web3 және блокчейн",  "en": "Web3 & blockchain"},
    "qazaq_lang":   {"ru": "IT на казахском языке", "kk": "Қазақ тіліндегі IT", "en": "Tech in Kazakh language"},
}

# Free-text keyword -> canonical skill / interest (ru, kk, en, slang). Matched on lowercase text.
SKILL_ALIASES = {
    "питон": "python", "пайтон": "python", "py": "python", "python": "python",
    "джанго": "django", "django": "django", "fastapi": "fastapi", "фастапи": "fastapi",
    "postgres": "postgresql", "постгрес": "postgresql", "postgresql": "postgresql",
    "redis": "redis", "docker": "docker", "докер": "docker", "golang": "go", " go ": "go",
    "java": "java", "джава": "java", "spring": "spring", "node": "node.js", "nodejs": "node.js", "node.js": "node.js",
    "kafka": "kafka", "кафка": "kafka", "rest": "rest api", "api": "rest api",
    "js": "javascript", "javascript": "javascript", "джаваскрипт": "javascript",
    "ts": "typescript", "typescript": "typescript", "react": "react", "реакт": "react",
    "vue": "vue", "next": "next.js", "next.js": "next.js", "css": "css", "html": "html",
    "figma": "figma", "фигма": "figma", "kotlin": "kotlin", "котлин": "kotlin", "swift": "swift",
    "flutter": "flutter", "флаттер": "flutter", "dart": "dart", "firebase": "firebase",
    "react native": "react native",
    "pytorch": "pytorch", "torch": "pytorch", "tensorflow": "tensorflow", "pandas": "pandas",
    "sql": "sql", "llm": "llm", "gpt": "llm", "rag": "llm", "nlp": "nlp", "cv": "computer vision",
    "computer vision": "computer vision", "компьютерное зрение": "computer vision", "mlops": "mlops",
    "sklearn": "scikit-learn", "scikit": "scikit-learn",
    "power bi": "power bi", "powerbi": "power bi", "tableau": "tableau", "excel": "excel", "эксель": "excel",
    "a/b": "a/b testing", "ab-тест": "a/b testing",
    "k8s": "kubernetes", "kubernetes": "kubernetes", "кубер": "kubernetes", "aws": "aws", "terraform": "terraform",
    "ci/cd": "ci/cd", "cicd": "ci/cd", "linux": "linux", "линукс": "linux", "grafana": "grafana", "ansible": "ansible",
    "selenium": "selenium", "pytest": "pytest", "postman": "postman", "playwright": "playwright",
    "pentest": "pentest", "пентест": "pentest", "siem": "siem", "owasp": "owasp",
    "unity": "unity", "юнити": "unity", "c#": "c#", "unreal": "unreal engine", "c++": "c++", "blender": "blender",
    "ui/ux": "ui/ux", "ux": "ui/ux", "ui": "ui/ux", "прототип": "prototyping", "user research": "user research",
    "jira": "jira", "scrum": "scrum", "скрам": "scrum", "custdev": "customer development",
    "рекрутинг": "it recruiting", "recruiting": "it recruiting", "найм": "it recruiting", "sourcing": "sourcing",
    "fundraising": "fundraising", "инвестиции": "fundraising", "инвестиц": "fundraising", "продажи": "sales", "sales": "sales",
    "маркетинг": "marketing", "marketing": "marketing", "питчинг": "pitching",
}

INTEREST_ALIASES = {
    "ии": "ai", " ai ": "ai", "ml": "ai", "машинн": "ai", "нейросет": "ai", "жасанды интеллект": "ai", "жи": "ai",
    "машиналық": "ai", "нейрожел": "ai", "machine learning": "ai", "deep learning": "ai",
    "кибер": "cybersecurity", "пентест": "cybersecurity", "хакер": "cybersecurity",
    "бағдарлама": "career", "оқу": "edtech", "университет": "edtech", "студент": "career",
    "llm": "llm", "агент": "llm", "chatgpt": "llm", "gpt": "llm", "rag": "llm",
    "финтех": "fintech", "fintech": "fintech", "банк": "fintech", "платеж": "fintech", "төлем": "fintech",
    "edtech": "edtech", "образован": "edtech", "білім": "edtech", "education": "edtech", "обучени": "edtech",
    "govtech": "govtech", "госуслуг": "govtech", "мемлекет": "govtech",
    "health": "healthtech", "медицин": "healthtech", "денсаулық": "healthtech", "здоров": "healthtech",
    "e-commerce": "ecommerce", "ecommerce": "ecommerce", "маркетплейс": "ecommerce", "ритейл": "ecommerce",
    "стартап": "startups", "startup": "startups", "стартаптар": "startups",
    "open source": "opensource", "опенсорс": "opensource", "opensource": "opensource",
    "облак": "cloud", "cloud": "cloud", "devops": "cloud", "бұлт": "cloud",
    "безопасн": "cybersecurity", "security": "cybersecurity", "қауіпсіз": "cybersecurity", "ctf": "cybersecurity",
    "игр": "gamedev", "game": "gamedev", "ойын": "gamedev",
    "мобильн": "mobile", "mobile": "mobile", "мобильді": "mobile",
    "данн": "data", "аналитик": "data", "data": "data", "дерек": "data",
    "дизайн": "design", "design": "design",
    "продукт": "product", "product": "product", "өнім": "product",
    "карьер": "career", "career": "career", "мансап": "career", "трудоустр": "career", "стажиров": "career", "тағылымдама": "career",
    "хакатон": "hackathons", "hackathon": "hackathons",
    "агро": "agritech", "agri": "agritech", "ауыл шаруашылығ": "agritech",
    "робот": "robotics", "iot": "robotics", "дрон": "robotics",
    "блокчейн": "web3", "web3": "web3", "крипт": "web3",
    "казахск": "qazaq_lang", "қазақ тіл": "qazaq_lang", "kazakh": "qazaq_lang",
}

LANGS = ["ru", "kk", "en"]
LANG_LABELS = {"ru": "Русский", "kk": "Қазақша", "en": "English"}

SLOTS = ["11:00", "11:30", "12:00", "12:30", "13:00", "13:30", "14:00", "14:30",
         "15:00", "15:30", "16:00", "16:30", "17:00", "17:30", "18:00", "18:30"]

# Fictional partner booths at the event (COULD item).
BOOTHS = [
    {"id": "b1", "name": "AI Lab", "tags": ["ai", "llm", "data"], "goals": []},
    {"id": "b2", "name": "Career Hub", "tags": ["career"], "goals": ["job_seek", "hire"]},
    {"id": "b3", "name": "Startup Alley", "tags": ["startups", "product", "fintech"], "goals": ["find_cofounder"]},
    {"id": "b4", "name": "Mentor Desk", "tags": ["career"], "goals": ["find_mentor", "be_mentor"]},
    {"id": "b5", "name": "Cloud Zone", "tags": ["cloud", "opensource"], "goals": []},
    {"id": "b6", "name": "CyberSec Corner", "tags": ["cybersecurity"], "goals": []},
    {"id": "b7", "name": "GameDev Arena", "tags": ["gamedev", "design"], "goals": []},
    {"id": "b8", "name": "EdTech & GovTech Space", "tags": ["edtech", "govtech", "qazaq_lang"], "goals": []},
    {"id": "b9", "name": "Hardware & Robotics", "tags": ["robotics", "agritech"], "goals": []},
]
