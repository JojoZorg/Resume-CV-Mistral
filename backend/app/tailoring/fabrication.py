"""Independent fabrication check.

Compares the tailored CV against the original CV and flags any entity (skill,
company, date, metric, title) present in the tailored output but absent from
the original. Any flag blocks export until resolved.
"""
import re

from ..schemas import CVData, FabricationFlag, FabricationReport, TailoredCV
from ..taxonomy import detect_skills

NUMBER_RX = re.compile(r"\d+(?:[.,]\d+)?%?|\$\s?\d+|R\$\s?\d+")
DATE_TOKEN_RX = re.compile(
    r"(?:\d{1,2}/\d{4})|(?:\d{4}\s*[-–—]\s*(?:\d{4}|present|current|atual))|"
    r"(?:[A-Za-zçã]{3,9}\.?\s*\d{4})", re.I)


CURRENT_WORDS = {"present", "current", "atual", "atualmente", "now", "today", "hoje",
                 "current"}


def _original_numbers(cv: CVData) -> dict[str, list[str]]:
    """Per-bullet numeric entity sets, keyed by trace id ('exp-0#2')."""
    out: dict[str, list[str]] = {}
    for src_id, text in cv.all_bullets():
        out[src_id] = NUMBER_RX.findall(text)
    return out


def _summary_source_text(cv: CVData) -> str:
    return cv.summary


def check_fabrication(original: CVData, tailored: TailoredCV) -> FabricationReport:
    flags: list[FabricationFlag] = []
    checked = 0

    # --- entity ground truth from the original CV ---
    bullet_parts = [t for _sid, t in original.all_bullets()]
    original_text = " \n ".join(
        [original.raw_text, original.summary, " \n ".join(original.skills)]
        + [f"{e.title} {e.company} {e.location} {e.start} {e.end}" for e in original.experience]
        + [f"{ed.degree} {ed.institution}" for ed in original.education]
        + [f"{c.name} {c.issuer}" for c in original.certifications]
        + [f"{p.name} {p.description}" for p in original.projects]
        + bullet_parts)
    original_skill_keys = set(detect_skills(original_text).keys())
    original_skills_lower = {s.lower().strip() for s in original.skills}
    original_companies = {e.company.lower().strip() for e in original.experience if e.company}
    original_companies |= {p.name.lower().strip() for p in original.projects if p.name}
    original_titles = {e.title.lower().strip() for e in original.experience}
    original_dates = set(DATE_TOKEN_RX.findall(original_text))
    original_years = set(re.findall(r"\b(?:19|20)\d{2}\b", original_text))
    numbers_by_source = _original_numbers(original)
    all_original_numbers = {n for nums in numbers_by_source.values() for n in nums}

    # --- section-level fields that are copied, never rewritten ---
    for e in tailored.experience:
        if e.company.strip().lower() not in original_companies:
            flags.append(FabricationFlag(kind="company", value=e.company,
                                         location=e.id, detail="Company not present in the original CV."))
        checked += 1
        if e.title.strip().lower() not in original_titles:
            flags.append(FabricationFlag(kind="title", value=e.title, location=e.id,
                                         detail="Job title does not match any original title."))
        checked += 1
        for d in (e.start, e.end):
            if d and d.lower() in CURRENT_WORDS:
                continue
            if d and d not in original_dates and d not in original_years:
                flags.append(FabricationFlag(kind="date", value=d, location=e.id,
                                             detail="Date not present in the original CV."))
            checked += 1

    for edu in tailored.education:
        if edu.institution and edu.degree.lower() not in original_text.lower():
            flags.append(FabricationFlag(kind="other", value=edu.degree, location=edu.id,
                                         detail="Education entry not found in the original CV."))
        checked += 1

    # --- skills ---
    for skill in tailored.skills:
        checked += 1
        key_hits = set(detect_skills(skill).keys())
        if skill.lower().strip() in original_skills_lower:
            continue
        if key_hits and key_hits.issubset(original_skill_keys):
            continue
        if skill.lower() not in original_text.lower():
            flags.append(FabricationFlag(kind="skill", value=skill, location="skills",
                                         detail="Skill not present anywhere in the original CV."))

    # --- summary: skills it mentions must exist in the original ---
    original_lang = original.source_language
    summary = tailored.summary
    for key, hits in detect_skills(summary).items():
        if key not in original_skill_keys:
            flags.append(FabricationFlag(kind="skill", value=hits[0], location="summary",
                                         detail="Summary mentions a skill absent from the original CV."))
    checked += 1

    # --- every bullet, per source traceability + numeric containment ---
    bullet_checks = []
    for e in tailored.experience:
        for tb in e.bullets:
            bullet_checks.append((e.id, tb))
    for p in tailored.projects:
        for tb in p.bullets:
            bullet_checks.append((p.id, tb))

    for location, tb in bullet_checks:
        checked += 1
        if not tb.source_ids:
            flags.append(FabricationFlag(
                kind="other", value=tb.text[:60], location=location,
                detail="Bullet has no source traceability ID."))
            continue
        merged_numbers: list[str] = []
        for src_id in tb.source_ids:
            merged_numbers.extend(numbers_by_source.get(src_id, []))
        allowed = set(merged_numbers)
        src_texts_all = original_text  # for word-level fallback

        for num in NUMBER_RX.findall(tb.text):
            if num not in allowed and num not in all_original_numbers:
                flags.append(FabricationFlag(
                    kind="metric", value=num, location=location,
                    detail="Number/percentage in this bullet has no counterpart in its "
                           "source bullet(s)."))
                break

        for key, hits in detect_skills(tb.text).items():
            if key not in original_skill_keys:
                flags.append(FabricationFlag(
                    kind="skill", value=hits[0], location=location,
                    detail="Bullet mentions a skill absent from the original CV."))

        for d in DATE_TOKEN_RX.findall(tb.text):
            if d not in original_dates:
                flags.append(FabricationFlag(
                    kind="date", value=d, location=location,
                    detail="Date token in a bullet has no counterpart in the original CV."))

    report = FabricationReport(
        flags=list({(f.kind, f.value, f.location, f.detail): f for f in flags}.values()),
        checked_entities=checked,
        passed=not flags,
    )
    return report
