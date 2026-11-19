"""FastAPI application: a stateless private CV-tailoring API.

The backend holds no persistent storage of CVs or JDs. Each request carries the
session payload from the client; exports re-run the fabrication check and
require an explicit acknowledgement that the diff was reviewed.
"""
from __future__ import annotations
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .config import settings
from .insights.insights import build_insights
from .jd.analyze import analyze_jd
from .llm.provider import provider_status
from .main_helpers import build_diff_summary, find_jd_gaps
from .parsing.cv_parse import heuristic_parse
from .parsing.extract import ExtractionError, extract_any, fetch_url_text
from .render.pdf_docx import export_file_bytes
from .schemas import (CareerInsights, CVData, FabricationReport,
                      JDAnalysisRequest, JDRequirements, TailorRequest,
                      TailorResponse)
from .tailoring.fabrication import check_fabrication
from .tailoring.tailor import tailor_cv

app = FastAPI(title="CV Tailoring Tool", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "llm": provider_status()}


@app.post("/api/parse-cv", response_model=CVData)
async def parse_cv(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 10 MB).")
    try:
        text, warnings = extract_any(file.filename or "", data, file.content_type or "")
    except ExtractionError as exc:
        raise HTTPException(422, str(exc)) from exc
    cv = heuristic_parse(text)
    cv.warnings = warnings + cv.warnings
    cv.raw_text = text
    return cv


@app.post("/api/analyze-jd", response_model=JDRequirements)
async def analyze_jd_endpoint(payload: JDAnalysisRequest):
    text = ""
    if payload.mode == "text":
        text = payload.text or ""
    elif payload.mode == "file":
        if not payload.file_b64:
            raise HTTPException(422, "No file content received.")
        import base64
        try:
            raw = base64.b64decode(payload.file_b64)
        except Exception as exc:
            raise HTTPException(422, "Could not decode the uploaded file.") from exc
        try:
            text, _warnings = extract_any(payload.filename or "", raw)
        except ExtractionError as exc:
            raise HTTPException(422, str(exc)) from exc
    elif payload.mode == "url":
        try:
            text = fetch_url_text(payload.url or "")
        except ExtractionError as exc:
            raise HTTPException(422, str(exc)) from exc
    if len(text.strip()) < 120:
        raise HTTPException(
            422,
            "Not enough JD text to analyse. Paste the full job description "
            "(at least a few paragraphs).",
        )
    return analyze_jd(text)


@app.post("/api/tailor", response_model=TailorResponse)
def tailor_endpoint(payload: TailorRequest):
    cv = payload.cv
    jd = payload.jd
    if not cv.experience and not cv.skills and not cv.summary:
        raise HTTPException(422, "The CV has no content to tailor. Complete the "
                                 "parsed preview first.")
    if not (jd.raw_text or jd.required_skills or jd.role_title):
        raise HTTPException(422, "Analyse a JD first (paste text, upload a file, "
                                 "or give a URL).")

    gaps = find_jd_gaps(cv, jd)
    tailored, fab_report = tailor_cv(cv, jd, payload.options)
    # Defence in depth: verify again over the serialised payload.
    local_report = check_fabrication(cv, tailored)
    merged_flags = {(f.kind, f.value, f.location, f.detail): f
                    for f in fab_report.flags + local_report.flags}
    merged = FabricationReport(
        flags=list(merged_flags.values()),
        checked_entities=max(fab_report.checked_entities, local_report.checked_entities),
        passed=not merged_flags,
    )
    diff = build_diff_summary(cv, tailored)
    return TailorResponse(
        tailored=tailored,
        fabrication=merged,
        gaps=gaps,
        diff=diff,
        export_hint=("Use the ATS version for online portals and job boards; use "
                     "the designed version for direct emails, referrals, and "
                     "recruiters."),
    )


@app.post("/api/export")
def export_endpoint(payload: dict):
    fmt = payload.get("format", "")
    reviewed = payload.get("reviewed", False)
    cv = CVData(**payload["cv"])
    from .schemas import TailoredCV
    tailored = TailoredCV(**payload["tailored"])
    if not reviewed:
        raise HTTPException(
            428, "Review the diff first — export unlocks with the "
                 "\"I have reviewed the changes\" acknowledgement.")
    if not payload.get("force", False):
        report = check_fabrication(cv, tailored)
        if not report.passed:
            raise HTTPException(
                409,
                {"message": "Fabrication check failed. Resolve the flagged items "
                            "before exporting, or fix them in the diff editor.",
                 "flags": [f.model_dump() for f in report.flags]},
            )
    try:
        data, filename, media = export_file_bytes(
            tailored, fmt, cv, max_pages=payload.get("max_pages", 2))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=data, media_type=media, headers=headers)


@app.post("/api/insights", response_model=CareerInsights)
def insights_endpoint(cv: CVData):
    if not (cv.experience or cv.skills or cv.summary):
        raise HTTPException(422, "Upload a CV first — insights are derived from "
                                 "your CV only.")
    return build_insights(cv)
