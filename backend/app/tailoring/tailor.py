"""Tailoring pipeline.

Allowed operations (and nothing else):
  1. rephrase existing content (LLM mode, validated; conservative synonym
     mirroring in deterministic mode),
  2. reorder bullets/sections to surface JD-relevant items first,
  3. rewrite the summary strictly from CV facts,
  4. select a subset of bullets when length is constrained,
  5. mirror JD vocabulary when the user genuinely has equivalent experience.

Every output bullet keeps `source_ids` pointing at original bullet IDs. Bullets
that cannot be traced or that fail validation are rejected and regenerated;
persistent failure falls back to the untouched original text.

User notes are honoured deterministically: a year mentioned in the notes ("hide
my 2015 role") excludes any experience whose date range covers that year; a
skill keyword ("emphasize my Python work") boosts relevant bullets.
"""
from __future__ import annotations
import re

from ..llm.provider import SYSTEM_GUARDRAIL, get_provider
from ..schemas import (CVData, JDRequirements, TailorOptions, TailoredBullet,
                       TailoredCV, TailoredExperienceEntry, TailoredProjectEntry)
from ..taxonomy import detect_skills, VOCAB_SYNONYMS
from .fabrication import check_fabrication

MAX_BUDGET = {1: 12, 2: 22}  # approximate bullet budget per CV length


def _bullet_score(text: str, jd: JDRequirements, notes_boost: list[str]) -> float:
    score = 0.0
    lowered = text.lower()
    for disp in jd.required_skills:
        tokens = [t for t in re.split(r"[\s/−-]+", disp.lower()) if len(t) > 2]
        if any(t in lowered for t in tokens) or disp.lower() in lowered:
            score += 3.0
    for disp in jd.preferred_skills:
        tokens = [t for t in re.split(r"[\s/−-]+", disp.lower()) if len(t) > 2]
        if any(t in lowered for t in tokens) or disp.lower() in lowered:
            score += 1.5
    for kw in jd.keywords:
        if len(kw) > 3 and kw.lower() in lowered:
            score += 0.5
    for term in notes_boost:
        if term.lower() in lowered:
            score += 4.0
    return score


def _entry_years(entry_start: str, entry_end: str) -> list[int]:
    years = re.findall(r"(?:19|20)\d{2}", f"{entry_start} {entry_end}")
    return [int(y) for y in years]


def parse_notes(opts: TailorOptions) -> tuple[list[str], list[int]]:
    boost_terms: list[str] = []
    hide_years: list[int] = []
    notes = opts.user_notes or ""
    for m in re.finditer(r"(?:19|20)\d{2}", notes):
        hide_years.append(int(m.group(0)))
    for m in re.finditer(
            r"(?:emphasize|highlight|focus on|destaque|m[ée]nsione|valorize)\s+(?:my\s+)?"
            r"([\w+#.\s-]{3,40})", notes, re.I):
        term = m.group(1).strip().rstrip(".,;")
        if term:
            boost_terms.append(term)
    return boost_terms, hide_years


def mirror_vocabulary(bullet: str, jd_text: str) -> tuple[str, bool]:
    """Swap user phrasing to JD vocabulary only via conservative synonym map."""
    changed = False
    out = bullet
    for pattern_a, replacement_b in VOCAB_SYNONYMS:
        try:
            if re.search(replacement_b.replace(" ", r"\s+"), jd_text, re.I) and \
                    re.search(pattern_a, out, re.I):
                candidate = re.sub(rf"\b{pattern_a}\b", replacement_b, out, count=1, flags=re.I)
                if candidate != out:
                    out = candidate
                    changed = True
                    break  # one conservative swap per bullet
        except re.error:
            continue
    return out, changed


# --------------------------------------------------------------------------- #
# LLM-assisted rephrasing with traceability enforcement
# --------------------------------------------------------------------------- #

def _llm_rephrase_bullets(provider, cv: CVData, jd: JDRequirements, opts: TailorOptions,
                          indexed: list[tuple[str, str, float]]) -> dict[str, tuple[str, list[str]]]:
    src_block = "\n".join(f"[{sid}] {text}" for sid, _text, _s in indexed)
    facts_block = (
        f"CV summary: {cv.summary}\n"
        f"CV skills: {', '.join(cv.skills[:40])}\n"
        f"CV recent titles: {'; '.join(f'{e.title} at {e.company}' for e in cv.experience[:3])}"
    )
    jd_block = (
        f"Role: {jd.role_title or 'n/a'}\nSeniority: {jd.seniority or 'n/a'}\n"
        f"Required skills: {', '.join(jd.required_skills)}\n"
        f"Preferred: {', '.join(jd.preferred_skills)}\n"
        f"Key responsibilities: {'; '.join(jd.responsibilities[:6])}"
    )
    lang = "Portuguese (Brazil)" if opts.target_language == "pt-BR" or (
        opts.target_language == "same" and cv.source_language == "pt-BR"
    ) else "English"
    tone = {
        "formal": "formal but plain",
        "conversational": "conversational and warm",
    }.get(opts.tone, "the user's original tone and typical sentence length")

    user_prompt = f"""Tailor CV bullets for the job below.

## SOURCE BULLETS (only these may be rephrased; keep their IDs)
{src_block}

## OTHER CV FACTS you may reference in the summary (never beyond these)
{facts_block}

## JOB DESCRIPTION EXTRACT
{jd_block}

## TASK
For each source bullet, write a tailored version that:
- is traceable to its source ID (echo the ID as "id");
- mirrors JD vocabulary ONLY when the user genuinely has the equivalent experience;
- keeps every number, date, company and tool exactly as in the source;
- does not add anything not in the source bullets or CV facts;
- matches {tone};
- is written in {lang}.

## OUTPUT
Return JSON: {{"bullets": [{{"id": "...", "text": "..."}}, ...]}} with one entry per source bullet ID."""
    try:
        data = provider.complete_json(SYSTEM_GUARDRAIL, user_prompt)
        out = {}
        for item in data.get("bullets", []):
            sid = str(item.get("id", "")).strip()
            text = str(item.get("text", "")).strip()
            if sid and text:
                out[sid] = (text, [sid])
        return out
    except Exception:  # noqa: BLE001
        return {}


def _llm_summary(provider, cv: CVData, jd: JDRequirements, opts: TailorOptions) -> tuple[str, list[str]]:
    facts_block = " \n ".join(f"[{sid}] {text}" for sid, text in list(cv.all_bullets())[:12])
    user_prompt = f"""Rewrite the CV summary for the job below, strictly from these CV facts.

CV summary (current): {cv.summary or '(none)'}
CV skills: {', '.join(cv.skills[:40])}
CV facts: {facts_block}
Target role: {jd.role_title or 'n/a'} | Seniority: {jd.seniority or 'n/a'}
Required skills: {', '.join(jd.required_skills)}

Rules: only use facts above; no new skills, tools, numbers, companies or dates;
2-3 sentences; preserve the user's voice.
Return JSON: {{"summary": "...", "source_ids": ["...", "..."]}} (source_ids = the fact IDs you used)."""
    try:
        data = provider.complete_json(SYSTEM_GUARDRAIL, user_prompt)
        summary = str(data.get("summary", "")).strip()
        ids = [str(i) for i in data.get("source_ids", []) if str(i).strip()]
        return (summary, ids) if summary else ("", [])
    except Exception:  # noqa: BLE001
        return "", []


def _deterministic_summary(cv: CVData, jd: JDRequirements) -> tuple[str, list[str]]:
    """Compose a summary strictly from the CV's own content + most recent title.

    Only skills the user has written are named. If nothing suitable exists the
    original summary is kept untouched.
    """
    bullets = list(cv.all_bullets())
    source_ids = []
    if not cv.skills:
        return cv.summary, []
    jd_lower = " ".join(jd.required_skills + jd.preferred_skills + jd.keywords).lower()
    cv_jd_skills = [s for s in cv.skills if s.lower() in jd_lower and len(s) > 2][:6]
    named = cv_jd_skills or cv.skills[:6]
    role_label = ""
    if cv.experience:
        top = cv.experience[0]
        role_label = top.title if top.title != "Unspecified title" else ""
        source_ids = [f"{top.id}#0"] if top.bullets else []
    if role_label:
        who = f"{role_label}"
        if top.company:
            who = f"{role_label} (most recently at {top.company})"
    else:
        who = "Professional"
    parts = [who]
    if cv.summary:
        parts.append(cv.summary.strip().rstrip("."))
    parts.append(f"Experience with: {', '.join(named)}")
    if bullets:
        source_ids = source_ids or [bullets[0][0]]
    return ". ".join(p.rstrip(".") + "." for p in parts), source_ids


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #

def tailor_cv(cv: CVData, jd: JDRequirements, opts: TailorOptions) -> tuple[TailoredCV, object]:
    provider = get_provider()
    boost_terms, hide_years = parse_notes(opts)
    jd_text = jd.raw_text or " ".join(jd.required_skills + jd.preferred_skills)

    # 1. score & index original bullets
    indexed: list[tuple[str, str, float]] = []
    for sid, text in cv.all_bullets():
        indexed.append((sid, text, _bullet_score(text, jd, boost_terms)))

    # 2. LLM per-bullet rephrase (with retry + deterministic fallback), or
    #    conservative vocabulary mirroring
    rephrased: dict[str, tuple[str, list[str]]] = {}
    if provider is not None and indexed:
        for attempt in range(2):  # rejected bullets get one regeneration attempt
            missing = [(sid, t, s) for sid, t, s in indexed if sid not in rephrased]
            if not missing:
                break
            rephrased.update(_llm_rephrase_bullets(provider, cv, jd, opts, missing))
    elif not indexed:
        rephrased = {}

    def build_bullet(sid: str, text: str, score: float) -> TailoredBullet:
        if sid in rephrased:
            text2, sources = rephrased[sid]
            if sources and all(s.split("#")[0] for s in sources):
                return TailoredBullet(text=text2, source_ids=sources,
                                      change="reworded" if text2 != text else "kept")
        mirrored, changed = mirror_vocabulary(text, jd_text)
        if changed:
            return TailoredBullet(text=mirrored, source_ids=[sid], change="reworded")
        return TailoredBullet(text=text, source_ids=[sid], change="kept")

    # 3. experience: keep chronological order of roles, reorder/reduce bullets
    tailored_experience: list[TailoredExperienceEntry] = []
    selected_bullets: dict[str, list[TailoredBullet]] = {}
    budget_bonus_relevance: list[tuple[str, float]] = []
    for entry in cv.experience:
        entry_years = _entry_years(entry.start, entry.end)
        if entry_years and any(y in hide_years for y in entry_years):
            # user explicitly asked to hide a role from that year
            continue
        scored = [(sid, text, sc) for sid, text, sc in indexed
                  if sid.startswith(entry.id + "#")]
        scored.sort(key=lambda t: -t[2])
        kept = scored
        bullets = [build_bullet(sid, text, sc) for sid, text, sc in kept]
        selected_bullets[entry.id] = bullets
        for sid, text, sc in kept:
            budget_bonus_relevance.append((sid, sc))
        if bullets:
            tailored_experience.append(TailoredExperienceEntry(
                id=entry.id, title=entry.title, company=entry.company,
                location=entry.location, start=entry.start, end=entry.end,
                bullets=bullets))

    # 4. length constraint: drop lowest-scoring bullets (min 2 per role remain)
    excluded: list[str] = []
    if opts.max_pages == 1:
        budget = MAX_BUDGET[1]
        all_scored = sorted(budget_bonus_relevance, key=lambda t: t[1])
        per_entry_count = {eid: len(b) for eid, b in selected_bullets.items()}
        for sid, _score in all_scored:
            if len([b for bs in selected_bullets.values() for b in bs]) <= budget:
                break
            eid = sid.split("#")[0]
            if per_entry_count.get(eid, 0) <= 2:
                continue
            selected_bullets[eid] = [b for b in selected_bullets[eid]
                                     if not b.source_ids or b.source_ids[0] != sid]
            per_entry_count[eid] -= 1
            excluded.append(sid)
        for eid in list(selected_bullets):
            selected_bullets[eid] = [b for b in selected_bullets[eid]
                                     if not b.source_ids or b.source_ids[0] not in excluded]
        tailored_experience = [e for e in tailored_experience if e.bullets]

    for eid in selected_bullets:
        entry = next((e for e in tailored_experience if e.id == eid), None)
        if entry:
            entry.bullets = selected_bullets[eid]

    # 5. projects
    tailored_projects = []
    for p in cv.projects:
        scored = sorted(((sid, t, s) for sid, t, s in indexed if sid.startswith(p.id + "#")),
                        key=lambda x: -x[2])
        bullets = [build_bullet(sid, text, sc) for sid, text, sc in scored]
        if bullets:
            tailored_projects.append(TailoredProjectEntry(
                id=p.id, name=p.name, description=p.description, bullets=bullets))

    # 6. summary
    summary_source_ids: list[str] = []
    if provider is not None:
        summary, summary_source_ids = _llm_summary(provider, cv, jd, opts)
        if not summary:
            summary, summary_source_ids = _deterministic_summary(cv, jd)
    else:
        summary, summary_source_ids = _deterministic_summary(cv, jd)

    # 7. skills: subset + reorder by JD relevance (a subset of the user's skills)
    def skill_relevance(s: str) -> float:
        low = s.lower()
        sc = 0.0
        for disp in jd.required_skills:
            if disp.lower() in low or low in disp.lower():
                sc += 3.0
        for disp in jd.preferred_skills:
            if disp.lower() in low or low in disp.lower():
                sc += 1.5
        return sc

    ordered_skills = sorted(cv.skills, key=lambda s: -skill_relevance(s))

    notes_out = []
    if provider is None and opts.target_language in ("pt-BR", "en") and \
            opts.target_language not in ("same", cv.source_language):
        notes_out.append(
            "Translation requires an LLM provider (run Ollama locally or configure "
            "an OpenAI-compatible endpoint). Output kept in the CV's original "
            "language — all content is still yours, nothing was altered.")

    tailored = TailoredCV(
        contact=cv.contact,
        summary=summary,
        summary_source_ids=summary_source_ids,
        role_title=jd.role_title or "",
        experience=tailored_experience,
        education=list(cv.education),
        skills=ordered_skills,
        certifications=list(cv.certifications),
        languages=list(cv.languages),
        projects=tailored_projects,
        excluded_bullet_ids=excluded,
        notes=" ".join(notes_out),
    )
    report = check_fabrication(cv, tailored)
    return tailored, report
