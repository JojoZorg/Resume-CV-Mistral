"""Structured CV parsing.

Strategy: an LLM (if configured) extracts a strict-JSON structure with a
"copy verbatim, never invent" instruction; otherwise a deterministic heuristic
parser runs. The heuristic parser is also the validation/fallback layer — a CV
parsed by the LLM but missing sections is re-processed heuristically and any
blended result is marked for user review in the preview step.
"""
import json
import re
import unicodedata

from ..schemas import (CVData, ContactInfo, ExperienceEntry, EducationEntry,
                       Certification, LanguageSkill, ProjectEntry)
from .extract import find_urls

EMAIL_RX = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RX = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
LINKEDIN_RX = re.compile(r"(https?://(?:www\.)?(?:linkedin\.com|github\.com|gitlab\.com)[^\s,;]+|"
                         r"(?:www\.)?(?:linkedin\.com|github\.com|gitlab\.com)/[\w./-]+)", re.I)
DATE_RX = re.compile(
    r"(?:(?P<m1>\d{1,2})/(?P<y1>\d{4})|(?P<mon1>[A-Za-zçãéê.]{3,9})\.?\s*/?\s*(?P<y1b>\d{2,4}))"
    r"\s*[-–—]|(?:\/|até|hasta|to|current|atual|present|hoje)\s*$",
    re.IGNORECASE)
RANGE_RX = re.compile(
    r"(?P<start>(?:\d{1,2}/\d{4})|(?:[A-Za-zçã]{3,9}\.?\s*\d{2,4})|(?:\d{4}))"
    r"\s*[-–—–]+\s*(?P<end>(?:\d{1,2}/\d{4})|(?:[A-Za-zçã]{3,9}\.?\s*\d{2,4})|(?:\d{4})|"
    r"present|current|atual|atualmente|now|today|hoje)",
    re.IGNORECASE)

BULLET_RX = re.compile(r"^\s*(?:[•▪‣●○*\-–—·>]\s+|\d{1,2}[.)]\s+)")

SECTION_HEADERS = {
    "summary": re.compile(r"^(?:professional\s+)?(?:summary|profile| objetivo|objetivo"
                          r"|resumo|perfil|about me|sobre mim|sobre)\b", re.I),
    "experience": re.compile(r"^(?:work\s+|professional\s+|employment\s+)?(?:experience|"
                             r"experi[êe]ncia|experi[êe]ncia profissional|hist[óo]rico"
                             r"pro?fissional|carreira|employment)\b", re.I),
    "education": re.compile(r"^(?:education|forma[çc][aã]o|escolaridade|acad[êe]mic"
                            r"o|academic background|estudos)\b", re.I),
    "skills": re.compile(r"^(?:technical\s+)?(?:skills|compet[êe]ncias|habilidades"
                         r"|hard skills|tecnologias|conhecimentos|skils)\b", re.I),
    "certifications": re.compile(r"^(?:certifications?|certifica[çc][õo]es|certificados"
                                 r"|licen[çc]as)\b", re.I),
    "languages": re.compile(r"^(?:languages?|idiomas)\b", re.I),
    "projects": re.compile(r"^(?:projects?|projetos|portfolio|portf[óo]lio)\b", re.I),
}


def normalize_text(raw: str) -> str:
    text = raw.replace("\u00a0", " ")
    text = unicodedata.normalize("NFC", text)
    lines = [ln.rstrip() for ln in text.splitlines()]
    text = "\n".join(ln for ln in lines if ln.strip() or True)
    return text


def looks_like_language(text: str) -> str:
    """Crude PT vs EN detection from common CV words."""
    pt_markers = len(re.findall(
        r"\b(experi[êe]ncia|forma[çc][aã]o|compet[êe]ncias|idiomas|empresa|"
        r"desenvolvi|respons[áa]vel|gradua[çc][aã]o|tecnologia)\b", text, re.I))
    en_markers = len(re.findall(
        r"\b(experience|education|skills|company|developed|responsible|bachelor|"
        r"technology|summary|manage(?:d|ment))\b", text, re.I))
    if pt_markers > en_markers:
        return "pt-BR"
    return "en"


def parse_contact(text: str) -> ContactInfo:
    head = "\n".join(text.splitlines()[:12])
    email = EMAIL_RX.search(text)
    phone = PHONE_RX.search(text)
    links = find_urls(text)
    linkedin = [l for l in links if "linkedin" in l.lower()]
    name = ""
    for line in head.splitlines():
        s = line.strip()
        if not s or EMAIL_RX.search(s) or PHONE_RX.search(s) or LINKEDIN_RX.search(s):
            continue
        if re.search(r"(curriculum|curriculum vitae|resume|curr[ií]culo|cv)\b", s, re.I):
            continue
        words = s.split()
        if 1 < len(words) <= 5 and all(re.match(r"^[\wÀ-ÿ'._-]+$", w) for w in words):
            name = s
            break
    return ContactInfo(
        name=name,
        email=email.group(0) if email else "",
        phone=phone.group(0).strip() if phone else "",
        location="",
        links=[l if l.startswith("http") else "https://" + l for l in links[:4]],
    )


def split_sections(text: str) -> tuple[dict[str, list[str]], list[str]]:
    sections: dict[str, list[str]] = {}
    unmatched: list[str] = []
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                sections[current].append("")
            continue
        if len(stripped) > 80:  # too long to be a section header
            target = current if current else "experience"
            sections.setdefault(target, []).append(stripped)
            continue
        matched = False
        for key, rx in SECTION_HEADERS.items():
            if rx.match(stripped):
                current = key
                sections.setdefault(current, [])
                matched = True
                break
        if not matched:
            if current:
                sections[current].append(stripped)
            else:
                unmatched.append(stripped)
    return sections, unmatched


def _norm_dates(seg: str) -> tuple[str, str]:
    m = RANGE_RX.search(seg)
    if not m:
        return "", ""
    return m.group("start").strip(), m.group("end").strip()


_company_hint = re.compile(r"\b(ltda|s\.?a\.?|inc\.?|llc|corp\.?| ltd|gmbh|\| |– | - |@|na |em |at |)[A-ZÀ-ÿ]", re.X)


def parse_experience(seg_lines: list[str]) -> list[ExperienceEntry]:
    entries: list[ExperienceEntry] = []
    cur: ExperienceEntry | None = None
    for line in seg_lines:
        if BULLET_RX.match(line):
            text = BULLET_RX.sub("", line).strip()
            if cur is not None and text:
                cur.bullets.append(text)
            elif text and not entries:
                # bullets before a dated header — keep as pending title company? skip
                continue
            continue
        start, end = _norm_dates(line)
        is_header = bool(start) or bool(re.search(r"\|", line)) and len(line) < 140
        if is_header:
            header = line
            dates_part = RANGE_RX.search(header)
            rest = RANGE_RX.sub("", header).strip(" |–—-\t")
            rest = re.split(r"\|{2,}", rest)[0] if " || " in header else rest
            title, company, location = _split_header(rest)
            cur = ExperienceEntry(
                id=f"exp-{len(entries)}",
                title=title or "Unspecified title",
                company=company,
                location=location,
                start=start,
                end=end,
                bullets=[],
            )
            entries.append(cur)
        elif cur is not None:
            # continuation line (e.g., long title) — append to last bullet-less header
            if cur.bullets:
                cur.bullets[-1] += " " + line.strip()
            elif cur.title == "Unspecified title":
                cur.title = line.strip()
            else:
                cur.bullets.append(line.strip())
    return entries


def _split_header(rest: str) -> tuple[str, str, str]:
    """Split 'Title — Company, City' style headers."""
    rest = re.sub(r"\s*\(\s*\)", "", rest)
    for sep in (" | ", " | ", " — ", " – ", " - ", " • ", " · ", " @ ", " na ", " em ", " at ", ", "):
        if sep in rest:
            parts = [p.strip() for p in rest.split(sep, 1)]
            title, rest2 = parts[0], parts[1]
            company, location = rest2, ""
            for sep2 in (",", " | ", " — ", " – ", " - "):
                if sep2 in company:
                    company, location = [p.strip() for p in company.split(sep2, 1)]
                    break
            return title.strip(" -—–|"), company.strip(" -—–|,"), location.strip(" -—–|,")
    parts = rest.split(",")
    if len(parts) >= 2 and len(parts[1].split()) <= 3:
        return parts[0].strip(), "", ",".join(parts[1:]).strip()
    return rest.strip(), "", ""


def parse_education(seg_lines: list[str]) -> list[EducationEntry]:
    entries = []
    for line in seg_lines:
        if not line.strip() or BULLET_RX.match(line) and len(line.strip()) < 3:
            continue
        text = BULLET_RX.sub("", line).strip()
        start, end = _norm_dates(text)
        body = RANGE_RX.sub("", text).strip(" |–—-,")
        parts = [p.strip(" |–—-") for p in re.split(r" \| | — | – ", body) if p.strip()]
        if not body:
            continue
        degree = parts[0] if parts else body
        institution = parts[1] if len(parts) > 1 else ""
        entries.append(EducationEntry(
            id=f"edu-{len(entries)}", degree=degree, institution=institution,
            start=start, end=end, details=parts[2] if len(parts) > 2 else "",
        ))
    return entries


def parse_simple_list(seg_lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in seg_lines:
        text = BULLET_RX.sub("", line).strip().strip("-–—:;")
        if not text:
            continue
        if len(text) < 60 or any(s in text for s in (",", "/", ";", "|")):
            for piece in re.split(r",|;|/|\s\|\s|\n", text):
                piece = piece.strip(" -–—•·")
                if 1 < len(piece) <= 60 and not piece.lower().startswith(("including", "como")):
                    items.append(piece)
        else:
            items.append(text)
    seen, out = set(), []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def parse_languages(seg_lines: list[str]) -> list[LanguageSkill]:
    skills = []
    known_levels = r"(fluent|native|advanced|intermediate|basic|beginner| profissional| " \
                   r"fluente|nativo|avan[çc]ado|intermedi[áa]rio|b[áa]sico|c\d|b\d|a\d)"
    combined = " \n ".join(seg_lines)
    for piece in re.split(r"[,;\n•·]", combined):
        piece = piece.strip(" -–—")
        m = re.match(rf"^([\wÀ-ÿ ]{{2,25}}?)\s*[:-]?\s*({known_levels})\.?$", piece.strip(), re.I)
        if m:
            skills.append(LanguageSkill(name=m.group(1).strip(), level=m.group(2).strip()))
    return skills


def parse_certifications(seg_lines: list[str]) -> list[Certification]:
    certs = []
    for line in seg_lines:
        text = BULLET_RX.sub("", line).strip()
        if not text or len(text) > 160:
            continue
        m = re.match(r"^(.{4,120}?)\s*(?:[-–—|(]\s*)?((?:19|20)\d{2})?\s*(?:\|\s*(.{3,60}))?$", text)
        name, year, issuer = m.group(1).strip(), m.group(2) or "", m.group(3) or ""
        certs.append(Certification(id=f"cert-{len(certs)}", name=name, issuer=issuer, year=year))
    return certs


def parse_projects(seg_lines: list[str]) -> list[ProjectEntry]:
    projects = []
    cur: ProjectEntry | None = None
    for line in seg_lines:
        if BULLET_RX.match(line):
            if cur is not None:
                cur.bullets.append(BULLET_RX.sub("", line).strip())
            continue
        if ":" in line and len(line) < 120:
            name, desc = line.split(":", 1)
        elif len(line) < 60:
            name, desc = line, ""
        else:
            if cur is not None:
                cur.bullets.append(line.strip())
            continue
        cur = ProjectEntry(id=f"proj-{len(projects)}", name=name.strip(" -–—"),
                           description=desc.strip(), bullets=[])
        projects.append(cur)
    return projects


def heuristic_parse(raw_text: str) -> CVData:
    text = normalize_text(raw_text)
    if not text.strip():
        return CVData(warnings=["The file contained no readable text."])
    sections, unmatched = split_sections(text)
    contact = parse_contact(text)
    summary = " ".join(sections.get("summary", [])[:3]).strip()
    experience = parse_experience(sections.get("experience", []))
    if not experience and unmatched:
        # aggressive fallback: scan whole doc for date-ranged headers
        experience = parse_experience(
            [ln for ln in text.splitlines() if _norm_dates(ln)[0] or BULLET_RX.match(ln)])
    education = parse_education(sections.get("education", []))
    skills = parse_simple_list(sections.get("skills", []))
    certs = parse_certifications(sections.get("certifications", []))
    languages = parse_languages(sections.get("languages", []))
    projects = parse_projects(sections.get("projects", []))

    warnings = []
    if not experience:
        warnings.append("No experience entries detected — check the structured preview "
                        "below and fix anything the parser missed.")
    if not skills:
        warnings.append("No skills section found — add your skills manually below so "
                        "tailoring and insights can use them.")
    if unmatched and not summary:
        sentence_like = [u for u in unmatched
                         if len(u) > 40 and not EMAIL_RX.search(u) and not PHONE_RX.search(u)]
        if sentence_like:
            summary = " ".join(sentence_like[:2])
    return CVData(
        contact=contact, summary=summary, experience=experience, education=education,
        skills=skills[:40], certifications=certs, languages=languages, projects=projects,
        raw_text=text, warnings=warnings, source_language=looks_like_language(text),
    )
