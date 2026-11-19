import base64

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["llm"]["mode"] in ("deterministic", "local", "cloud")


def test_parse_cv_docx():
    from docx import Document
    import io
    doc = Document()
    doc.add_paragraph("Maria Silva")
    doc.add_paragraph("maria@example.com | +55 11 99999-0000")
    doc.add_paragraph("")
    doc.add_paragraph("Experience")
    doc.add_paragraph("Software Engineer, ACME Tech (03/2019 - 05/2023)")
    doc.add_paragraph("- Built python REST APIs with docker and CI/CD")
    doc.add_paragraph("- Led a team of 3 developers")
    doc.add_paragraph("")
    doc.add_paragraph("Skills")
    doc.add_paragraph("Python, Docker, PostgreSQL, SQL, Linux")
    buf = io.BytesIO()
    doc.save(buf)
    r = client.post("/api/parse-cv", files={
        "file": ("cv.docx", buf.getvalue(),
                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert r.status_code == 200
    cv = r.json()
    assert cv["contact"]["email"] == "maria@example.com"
    assert any("python" in s.lower() for s in cv["skills"])
    assert cv["experience"] and "ACME" in cv["experience"][0]["company"]
    for e in cv["experience"]:
        for i, b in enumerate(e["bullets"]):
            assert b  # no empty bullets


def test_parse_cv_pdf_roundtrip():
    """Covers acceptance criterion: upload a 2-page CV (PDF)."""
    from xhtml2pdf import pisa
    import io, re
    html = "<html><body>" + "".join(
        f"<p>Page content line {i} with python experience details, docker, sql, "
        f"and plenty of text so the extractor sees real content.</p>"
        for i in range(60)) + "</body></html>"
    buf = io.BytesIO()
    pisa.CreatePDF(html, dest=buf)
    r = client.post("/api/parse-cv", files={"file": ("cv.pdf", buf.getvalue(), "application/pdf")})
    assert r.status_code == 200
    assert "python" in r.json()["raw_text"]


def test_analyze_jd_text_and_url_errors():
    r = client.post("/api/analyze-jd", json={"mode": "text", "text": "short"})
    assert r.status_code == 422
    assert "paste" in r.json()["detail"].lower()
    r2 = client.post("/api/analyze-jd", json={"mode": "url", "url": "not a url"})
    assert r2.status_code == 422


def test_tailor_export_flow_requires_review():
    from tests.conftest import EN_CV, EN_JD
    payload = {
        "cv": EN_CV.model_dump(),
        "jd": EN_JD.model_dump(),
        "options": {"tone": "original", "target_language": "same", "max_pages": 1,
                    "user_notes": ""},
    }
    r = client.post("/api/tailor", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["fabrication"]["passed"], body["fabrication"]
    tailored = body["tailored"]

    # export without review acknowledgement -> blocked
    export = {"format": "ats_pdf", "reviewed": False, "cv": payload["cv"],
              "tailored": tailored}
    r2 = client.post("/api/export", json=export)
    assert r2.status_code == 428

    export["reviewed"] = True
    for fmt in ("ats_pdf", "designed_pdf", "ats_docx"):
        r3 = client.post("/api/export", json={**export, "format": fmt})
        assert r3.status_code == 200, (fmt, r3.text[:300])
        assert len(r3.content) > 500
        disp = r3.headers["content-disposition"]
        assert "Maria_Silva_Senior-Backend-Engineer_CV." in disp


def test_injected_fabrication_blocks_export():
    from tests.conftest import EN_CV, EN_JD
    payload = {
        "cv": EN_CV.model_dump(), "jd": EN_JD.model_dump(),
        "options": {"tone": "original", "target_language": "same", "max_pages": 2,
                    "user_notes": ""},
    }
    body = client.post("/api/tailor", json=payload).json()
    tailored = body["tailored"]
    tailored["skills"].append("Kubernetes")
    r = client.post("/api/export", json={
        "format": "ats_pdf", "reviewed": True, "cv": payload["cv"],
        "tailored": tailored})
    assert r.status_code == 409
    assert "Fabrication" in (r.json().get("message") or str(r.json()))


def test_insights_endpoint():
    from tests.conftest import EN_CV
    r = client.post("/api/insights", json=EN_CV.model_dump())
    assert r.status_code == 200
    body = r.json()
    assert body["strong_fits"], "expected at least one strong fit"
    assert body["skill_inventory"]
    assert body["next_steps"]
    for group in body["skill_inventory"]:
        assert group["skills"]


def test_full_pipeline_speed():
    import time
    from tests.conftest import EN_CV, EN_JD
    payload = {"cv": EN_CV.model_dump(), "jd": EN_JD.model_dump(),
               "options": {"tone": "original", "target_language": "same",
                           "max_pages": 1, "user_notes": ""}}
    t0 = time.time()
    r = client.post("/api/tailor", json=payload)
    dt = time.time() - t0
    assert r.status_code == 200
    assert dt < 10, "pipeline slower than 10s offline (LLM off)"
