"""Helpers kept out of the route module for readability."""
from __future__ import annotations
import re

from .schemas import ChangeCount, CVData, DiffSummary, JDRequirements


def build_diff_summary(cv: CVData, tailored) -> DiffSummary:
    """Count changed (reworded/removed) bullets per section, with totals."""
    counts: dict[str, ChangeCount] = {}
    total = 0

    def bump(section: str, kind: str):
        nonlocal total
        c = counts.setdefault(section, ChangeCount(section=section))
        setattr(c, kind, getattr(c, kind) + 1)
        total += 1

    if tailored.summary.strip() and tailored.summary.strip() != (cv.summary or "").strip():
        bump("Summary", "reworded")

    for e in tailored.experience:
        orig = next((o for o in cv.experience if o.id == e.id), None)
        orig_bullets = orig.bullets if orig else []
        kept_sources = {sid for b in e.bullets for sid in b.source_ids}
        seen_reworded = set()
        for b in e.bullets:
            for sid in b.source_ids:
                if sid in seen_reworded:
                    continue
                try:
                    idx = int(sid.split("#")[-1])
                    orig_text = orig_bullets[idx]
                except (ValueError, IndexError):
                    continue
                if b.text != orig_text:
                    seen_reworded.add(sid)
                    bump("Experience", "reworded")
        present_ids = {f"{e.id}#{i}" for i in range(len(orig_bullets))}
        for pid in present_ids - kept_sources:
            bump("Experience", "removed")

    orig_project_ids = {p.id for p in cv.projects}
    for p in tailored.projects:
        orig = next((o for o in cv.projects if o.id == p.id), None)
        orig_bullets = orig.bullets if orig else []
        for i, orig_text in enumerate(orig_bullets):
            sid = f"{p.id}#{i}"
            kept = any(sid in b.source_ids for b in p.bullets)
            if not kept:
                bump("Projects", "removed")
            elif any(b.text != orig_text and sid in b.source_ids for b in p.bullets):
                bump("Projects", "reworded")
    return DiffSummary(counts=list(counts.values()), total=total)


def find_jd_gaps(cv: CVData, jd: JDRequirements) -> list[dict]:
    """Flag JD requirements the CV does not evidence — nothing is hidden."""
    cv_lower = (cv.raw_text or "").lower()
    cv_skills_lower = {s.lower() for s in cv.skills}
    gaps = []

    def present(req: str) -> bool:
        rl = req.lower().strip()
        tokens = [t for t in re.split(r"[\s/]+", rl) if len(t) > 3]
        if rl in cv_skills_lower or rl in cv_lower:
            return True
        matches = [t for t in tokens if t in cv_lower]
        return len(matches) >= max(1, int(len(tokens) * 0.6)) if tokens else False

    for req in jd.required_skills:
        if not present(req):
            gaps.append({
                "requirement": req,
                "status": "missing",
                "message": f"JD requires {req}; not found in your CV.",
                "suggestions": [
                    "If you have adjacent experience with a similar tool, word it truthfully.",
                    "Address it in the cover letter instead of the CV.",
                    "Or omit it — the app will never add it to your CV.",
                ],
            })
    for pref in jd.preferred_skills:
        if not present(pref):
            gaps.append({
                "requirement": pref,
                "status": "preferred-missing",
                "message": f"JD prefers {pref}; not found in your CV.",
                "suggestions": ["Optional: mention in the cover letter if you have "
                                "adjacent experience."],
            })
    return gaps
