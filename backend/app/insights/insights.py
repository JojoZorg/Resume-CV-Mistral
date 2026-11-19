"""Career insights: standalone CV analysis, grounded rule-based + optional LLM."""
from __future__ import annotations
import re

from ..llm.provider import get_provider
from ..schemas import CareerInsights, CVData, RoleRecommendation, SkillGroup
from ..taxonomy import (NEXT_LEVEL_SIGNALS, ROLE_PROFILES, SENIORITY_LADDER,
                        compiled_skills, detect_skills)


def _cv_text(cv: CVData) -> str:
    parts = [cv.summary, " ".join(cv.skills), cv.raw_text or ""]
    for e in cv.experience:
        parts.append(f"{e.title} {e.company}")
        parts.extend(e.bullets)
    for p in cv.projects:
        parts.append(p.name)
        parts.extend(p.bullets)
    for c in cv.certifications:
        parts.append(f"{c.name} {c.issuer}")
    for l in cv.languages:
        parts.append(f"{l.name} {l.level}")
    return " \n ".join(p for p in parts if p)


def _evidence_snippets(cv: CVData, matched_skills: list[str], limit: int = 3) -> list[str]:
    """Cite specific CV lines containing the matched skills."""
    snippets = []
    search_terms = [s.lower() for s in matched_skills]
    for e in cv.experience:
        for b in e.bullets:
            low = b.lower()
            if any(t in low or any(part in low for part in re.split(r"[\s/]+", t))
                   for t in search_terms):
                where = f"{e.title or 'Role'}"
                if e.company:
                    where += f" at {e.company}"
                snippets.append(f'{where}: "{b[:140]}"')
    for p in cv.projects:
        for b in p.bullets:
            low = b.lower()
            if any(t in low for t in search_terms):
                snippets.append(f'Project {p.name}: "{b[:140]}"')
    return snippets[:limit]


def _years_of_experience(cv: CVData) -> int:
    years: set[int] = set()
    for e in cv.experience:
        for y in re.findall(r"(?:19|20)\d{2}", f"{e.start} {e.end} {e.bullets[0] if e.bullets else ''}"):
            years.add(int(y))
    if len(years) >= 2:
        span = max(years) - min(years) + 1
        return min(span, max(1, len({y // 5 for y in years}) * 5))
    return len(years)


def _current_level(cv: CVData) -> str:
    text = _cv_text(cv).lower()
    if re.search(r"principal|staff", text):
        return "principal"
    if re.search(r"tech lead|lead engineer|l[íi]der t[ée]cnico|manager|gerente|coordenador", text):
        return "lead"
    yrs = _years_of_experience(cv)
    if re.search(r"intern|est[áa]gio", text) and yrs <= 1:
        return "intern"
    if yrs >= 6 or re.search(r"senior|s[êe]nior", text):
        return "senior"
    if yrs >= 3:
        return "mid"
    return "junior"


def _match_profile(profile: dict, cv_text: str, cv: CVData) -> tuple[float, list[str]]:
    total = sum(w for w in profile["skills"].values() if w > 0)
    got = 0.0
    matched = []
    found = detect_skills(cv_text)
    for key, weight in profile["skills"].items():
        if key in found and weight > 0:
            got += weight
            matched.append(found[key][0])
    if not total:
        return 0.0, matched
    return round(got / total, 3), matched


def _profile_justification(profile: dict, matched: list[str]) -> str:
    top = ", ".join(matched[:5]) if matched else "no matching skills found"
    return f"Matches {len(matched)} of the profile's core skills: {top}."


def _current_title_text(cv: CVData) -> str:
    return " ".join(e.title for e in cv.experience).lower()


def build_insights(cv: CVData) -> CareerInsights:
    cv_text = _cv_text(cv)
    title_text = _current_title_text(cv)
    strong, adjacent, latent = [], [], []

    for profile in ROLE_PROFILES:
        score, matched = _match_profile(profile, cv_text, cv)
        is_current_field = any(re.search(re.escape(a), title_text)
                               for a in profile["alt"]) if profile["alt"] else False
        rec = None
        if score >= 0.6:
            rec = RoleRecommendation(
                title=profile["title"], category="strong", score=score,
                justification=_profile_justification(profile, matched),
                evidence=_evidence_snippets(cv, matched),
                gaps=[],
            )
            if is_current_field or score >= 0.7:
                strong.append(rec)
            else:
                latent.append(rec)
        elif score >= 0.35:
            missing = [found_disp for key, (found_disp, _g, _rx, _b) in
                       compiled_skills().items()
                       if profile["skills"].get(key, 0) >= 2 and
                       key not in detect_skills(cv_text)]
            rec = RoleRecommendation(
                title=profile["title"], category="adjacent", score=score,
                justification=_profile_justification(profile, matched),
                evidence=_evidence_snippets(cv, matched),
                gaps=[f"Build evidence of: {m}" for m in sorted(set(missing))[:4]],
            )
            adjacent.append(rec)

    # ---- latent detection from behavioural/soft signals ---------------------
    text_low = cv_text.lower()
    latent_rules = [
        (r"mentor", ["Developer Advocate / DevRel", "Tech Lead"],
         "You have repeated mentoring activity in your CV — dev advocacy and tech "
         "leadership are one step from that."),
        (r"etl|data pipeline|pipeline de dados|airflow|dbt",
         ["Data Engineer"], "Data-pipeline work in your CV supports a data "
         "engineering path."),
        (r"code review|pull request|reviewed", ["Tech Lead"],
         "Regular code-review activity suggests readiness for technical leadership."),
        (r"stakeholder|cliente|customer", ["Technical Account Manager", "Solutions Architect"],
         "Customer-facing engineering work supports client-facing technical roles."),
    ]
    for pattern, roles, why in latent_rules:
        if re.search(pattern, text_low):
            for r in roles:
                if not any(x.title == r for x in strong + adjacent + latent):
                    latent.append(RoleRecommendation(
                        title=r, category="latent", score=0.35, justification=why,
                        evidence=_evidence_snippets(cv, [pattern]),
                        gaps=[],
                    ))

    strong.sort(key=lambda r: -r.score)
    adjacent.sort(key=lambda r: -r.score)

    # ---- skill inventory -----------------------------------------------------
    found = detect_skills(cv_text)
    inventory: dict[str, list[str]] = {}
    breadth: dict[str, str] = {}
    for key, hit in found.items():
        disp, group, _rx, broad = compiled_skills()[key]
        inventory.setdefault(group, [])
        if disp not in inventory[group]:
            inventory[group].append(disp)
        breadth[group] = "broadly valuable" if broad else "specialised"
    skill_groups = [SkillGroup(group=g, skills=sorted(s), breadth=breadth.get(g, ""))
                    for g, s in sorted(inventory.items())]

    # ---- next-level gaps ------------------------------------------------------
    level = _current_level(cv)
    idx = SENIORITY_LADDER.index(level)
    next_level = SENIORITY_LADDER[min(idx + 1, len(SENIORITY_LADDER) - 1)]
    gaps: list[str] = []
    for signal in NEXT_LEVEL_SIGNALS.get(next_level, []):
        pat = signal.lower().split("(")[0].strip()
        if not re.search(re.escape(pat.split()[0]) if pat.split() else pat, text_low):
            gaps.append(f"{next_level.title()}-level expectation not evidenced in your CV: {signal}")

    # ---- next steps -----------------------------------------------------------
    steps: list[str] = []
    if gaps:
        steps.append(f"Close the top {next_level} gap: {gaps[0].split(':')[-1].strip()}.")
    numeric_bullets = [b for _sid, b in cv.all_bullets() if re.search(r"\d", b)]
    total_bullets = len(list(cv.all_bullets()))
    if total_bullets and len(numeric_bullets) / max(total_bullets, 1) < 0.4:
        recent = cv.experience[0].company if cv.experience and cv.experience[0].company else "most recent role"
        steps.append(f"Add a measurable outcome to your {recent} role (e.g., time saved, "
                     "users affected) — only ones that are true for you.")
    if not cv.projects:
        niche = next((sg.skills[0] for sg in skill_groups if sg.breadth == "specialised"
                      and sg.skills), None)
        steps.append(f"Ship one small open-source or side project{f' using {niche}' if niche else ''} "
                     "to make a niche skill visible.")
    if not cv.certifications:
        steps.append("If a certification is expected in your target area, pursue one — "
                     "but only after checking role postings you actually want.")
    if not cv.languages:
        steps.append("List spoken languages with proficiency levels if you haven't.")
    steps = steps[:5] or ["Your CV is in good shape — keep adding measurable outcomes."]

    insights = CareerInsights(
        strong_fits=strong[:8],
        adjacent_roles=adjacent[:6],
        latent_paths=latent[:6],
        skill_inventory=skill_groups,
        next_level_gaps=gaps[:6],
        next_steps=steps,
    )

    provider = get_provider()
    if provider is not None:
        try:
            enriched = provider.complete_json(
                "You are a career advisor. Ground every claim in the CV facts given. "
                "Never suggest a role the CV does not plausibly support.",
                f"CV:\n{cv_text[:6000]}\n\nRule-based results: "
                f"{[r.title for r in strong]}"
                f"\nAdd up to 2 extra 'latent' role ideas with one-line evidence-based "
                f"justifications. Return JSON: {{\"latent\": [{{\"title\": \"...\", "
                f"\"justification\": \"...\"}}]}}")
            for item in enriched.get("latent", [])[:2]:
                title = str(item.get("title", "")).strip()
                just = str(item.get("justification", "")).strip()
                if title and just and not any(r.title.lower() == title.lower()
                                              for r in insights.latent_paths):
                    insights.latent_paths.append(RoleRecommendation(
                        title=title, category="latent", score=0.0, justification=just))
        except Exception:  # noqa: BLE001
            pass
    return insights
