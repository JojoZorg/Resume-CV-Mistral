"""JD requirement extraction: skills, seniority, keywords, responsibilities, domain."""
import re

from ..schemas import JDRequirements
from ..taxonomy import STOPWORDS, detect_skills, SKILLS
from ..parsing.extract import fetch_url_text


def detect_language(text: str) -> str:
    pt_markers = len(re.findall(
        r"\b(várias?|desejável|diferencial|responsabilidades|competências|"
        r"requisitos|experiência|anos|empresa|vaga)\b", text, re.I))
    en_markers = len(re.findall(
        r"\b(requirements?|responsibilities|experience|years?|nice to have|preferred|"
        r"about (?:the|us)|you will|skills?)\b", text, re.I))
    return "pt-BR" if pt_markers > en_markers else "en"


SENIORITY_PATTERNS = [
    ("principal", r"principal\b|especialista s[êe]nior"),
    ("staff", r"\bstaff engineer\b"),
    ("lead", r"\blead\b|l[íi]der t[ée]cnico|tech lead|coordenador"),
    ("senior", r"senior|s[êe]nior|pleno iii"),
    ("mid", r"mid[- ]level|pleno|intermedi[áa]ri"),
    ("junior", r"junior|j[úu]nior|trainee|entry[- ]level"),
    ("intern", r"intern|est[áa]gio|estagi[áa]ri"),
]

YEARS_RX = re.compile(r"(\d+)\+?\s*(?:a\s*anos|anos de|years)", re.I)

PREFERRED_MARKERS = re.compile(
    r"(nice to have|desirable|preferred|desej[áa]vel|diferencial|differentials?|plus\b|"
    r"bonus(?: points)?|qualifications?|qualifica[çc][õo]es|we'd love)", re.I)
REQUIRED_MARKERS = re.compile(
    r"(requirements?|must have|obrigat[óo]ri|requisitos|you have|qualifications)", re.I)

RESPONSIBILITY_VERBS = r"(?:develop|design|build|implement|lead|manage|maintain|create|drive|"
r"own|collaborate|mentor|deliver|optimize|automate|support|write|review|integrate|"
r"desenvolver|idealizar|construir|implementar|liderar|gerenciar|manter|criar|"
r"conduzir|colaborar|automatizar|entregar|otimizar|modelar)"

SOFT_SKILLS = [
    ("communication", r"communica|comunica|stakeholder"),
    ("teamwork", r"team\s?work|collaborat|colabora|trabalho em equipe"),
    ("leadership", r"leadership|lideran[çc]a"),
    ("proactivity", r"proactive|proativ|ownership|autonomy|aut[ôo]nom"),
    ("problem_solving", r"problem[- ]solving|problem solving|resolu[çc][aã]o de problemas"),
    ("adaptability", r"adaptab|flexib|feedback"),
    ("organization", r"organi[sz]|detail[- ]oriented|details|aten[çc][aã]o a detalhe"),
]

DOMAIN_PATTERNS = [
    ("FinTech / banking", r"fintech|bank|pagamento|payment|banco\b|seguro|insurance|cr[ée]dito"),
    ("E-commerce / retail", r"e-?commerce|retail|varejo|marketplace"),
    ("Health", r"health|sa[úu]de|m[ée]dic|hospital"),
    ("Education", r"educa|edtech|e-?learning|escola"),
    ("Logistics", r"log[íi]stic|supply|transport"),
    ("Telecom / IoT", r"telecom|iot|embedded|embarcado"),
    ("SaaS / software", r"\bsaas\b|software house|software"),
    ("Data / AI", r"data[- ]driven|intelig[êe]ncia artificial|artificial intelligence|\bai\b"),
]


SOFT_SKILL_KEYS = {"product_thinking", "leadership", "communication",
                      "mentoring", "hiring", "customer_facing"}


def analyze_jd(text: str, source_language: str = "") -> JDRequirements:
    jd_lang = source_language or detect_language(text)
    lowered = text.lower()

    role_title = ""
    for line in text.splitlines():
        line_s = line.strip()
        if not (3 < len(line_s) < 90):
            continue
        if YEARS_RX.search(line_s) or re.search(
                r"\b(requirements?|responsibilit|nice to have|about|we are|salary|"
                r"location|apply|benefits)\b", line_s, re.I):
            continue
        clean = re.sub(r"^(?:vaga|job title|position|role|fun\u00e7\u00e3o)[:\s-]*", "",
                       line_s, flags=re.I)
        clean = re.sub(r"\s*[-|(].*$", "", clean).strip(" -|")
        if len(clean) > 2:
            role_title = clean
            break
    if not role_title:
        first_sent = re.split(r"(?<=[.!?])\s+", text.strip())[0]
        if len(first_sent) <= 90 and not YEARS_RX.search(first_sent) and \
                not re.search(r"\b(requirements?|responsibilit|nice to have)\b",
                              first_sent, re.I):
            role_title = re.sub(r"\s*[-|(].*$", "", first_sent).strip(" -|")

    seniority = ""
    for label, pat in SENIORITY_PATTERNS:
        if re.search(pat, lowered):
            seniority = label
            break

    years = ""
    m = YEARS_RX.search(text)
    if m:
        years = f"{m.group(1)}+ years" if jd_lang == "en" else f"{m.group(1)}+ anos"

    found = detect_skills(text)
    required = []
    preferred = []
    bucket = required
    sentences = re.split(r"(?<=[.;:!?])\s+|\n+", text)
    for sent in sentences:
        low = sent.lower().strip()
        if not low:
            continue
        if PREFERRED_MARKERS.search(low):
            bucket = preferred
        elif REQUIRED_MARKERS.search(low):
            bucket = required
        for key in detect_skills(sent):
            if key in SOFT_SKILL_KEYS:
                continue  # soft skills are detected separately below
            disp = SKILLS[key][0]
            if disp not in required and disp not in preferred:
                bucket.append(disp)

    keywords = list(dict.fromkeys(
        [SKILLS[k][0] for k in found.keys() if k != "git_any"]))
    freq: dict[str, int] = {}
    for word in re.findall(r"[A-Za-zÀ-ÿ][\w+#.-]{2,}", text):
        wl = word.lower()
        if wl in STOPWORDS or any(s in wl for s in ("@", "http", ".com", "www.")):
            continue
        freq[wl] = freq.get(wl, 0) + 1
    top_terms = [w.capitalize() for w, c in sorted(freq.items(), key=lambda kv: -kv[1])
                 if c >= 3][:15]
    keywords = list(dict.fromkeys(keywords + [t for t in top_terms if t.lower() not in
                                              {k.lower() for k in keywords}]))[:25]

    responsibilities = []
    for line in text.splitlines():
        low = line.strip().lower()
        if 25 < len(line.strip()) < 240 and re.match(rf"^\s*-?\s*({RESPONSIBILITY_VERBS})\b",
                                                     line.strip(), re.I):
            responsibilities.append(line.strip().lstrip("-• ").strip())
        if len(responsibilities) >= 10:
            break

    soft = [label.title() for label, pat in SOFT_SKILLS if re.search(pat, lowered)]

    domain = ""
    for label, pat in DOMAIN_PATTERNS:
        if re.search(pat, lowered):
            domain = label
            break

    return JDRequirements(
        role_title=role_title, seniority=seniority, years_of_experience=years,
        required_skills=list(dict.fromkeys(required))[:20],
        preferred_skills=list(dict.fromkeys(preferred))[:20],
        responsibilities=responsibilities, soft_skills=soft, domain=domain,
        keywords=keywords, language=jd_lang, raw_text=text,
    )
