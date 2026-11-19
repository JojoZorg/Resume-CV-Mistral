"""Export renderers: ATS PDF, designed PDF (both from HTML via xhtml2pdf)
and ATS DOCX (python-docx). Single accent color, latin-1-safe fonts."""
from __future__ import annotations
import html
import io
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

ACCENT = "#1a5276"
ACCENT_LIGHT = "#d6e4f0"

_lat1_replacements = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u2022": "-",
    "\u00a0": " ", "\u2212": "-", "\u00ba": "o",
}


def _latin(s: str) -> str:
    for k, v in _lat1_replacements.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def esc(s: str) -> str:
    return html.escape(_latin(s or ""))


def fmt_date(d: str, target: str = "MM/YYYY") -> str:
    """Normalize dates to MM/YYYY, falling back to YYYY."""
    d = (d or "").strip()
    if not d:
        return ""
    m = re.match(r"^(\d{1,2})/(\d{4})$", d)
    if m:
        return f"{int(m.group(1)):02d}/{m.group(2)}"
    m = re.match(r"^([A-Za-zçã]+)\.?/?\s*(\d{4})$", d)
    if m:
        months = {**{en: i + 1 for i, en in enumerate(
            ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
             "nov", "dec"])},
            **{pt: i + 1 for i, pt in enumerate(
            ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out",
             "nov", "dez"])}}
        mm = months.get(m.group(1)[:3].lower())
        if mm:
            return f"{mm:02d}/{m.group(2)}"
    if re.match(r"^(?:19|20)\d{2}$", d):
        return d
    return d


def fmt_range(start: str, end: str) -> str:
    a, b = fmt_date(start), fmt_date(end)
    if not a and not b:
        return ""
    if b.lower() in ("present", "current", "atual", "atualmente", "now", "today", "hoje"):
        b = "Current" if not any(x.isdigit() for x in b) else b
    return f"{a} - {b}" if a and b else (a or b)


# --------------------------------------------------------------------------- #
# ATS version: single column, no tables, no images, standard headings
# --------------------------------------------------------------------------- #

def ats_html(cv, tailored) -> str:
    contact = tailored.contact
    role = tailored.role_title
    lines = [f"<h1>{esc(role + ' - ' + (contact.name or '')) if role else esc(contact.name or '')}</h1>"]
    meta = [x for x in [contact.email, contact.phone, contact.location] if x]
    if contact.links:
        meta.extend(contact.links)
    if meta:
        lines.append("<p>" + esc(" | ".join(meta)) + "</p>")
    if tailored.summary:
        lines.append(f"<h2>Summary</h2><p>{esc(tailored.summary)}</p>")
    if tailored.experience:
        lines.append("<h2>Experience</h2>")
        for e in tailored.experience:
            header = f"{esc(e.title)}" + (f", {esc(e.company)}" if e.company else "")
            rng = fmt_range(e.start, e.end)
            if rng:
                header += f" ({esc(rng)})"
            loc = f" - {esc(e.location)}" if e.location else ""
            lines.append(f"<p><b>{header}</b>{loc}</p>")
            if e.bullets:
                lines.append("<ul>" + "".join(f"<li>{esc(b.text)}</li>" for b in e.bullets) + "</ul>")
    if tailored.skills:
        lines.append("<h2>Skills</h2><ul>" +
                     "".join(f"<li>{esc(s)}</li>" for s in tailored.skills) + "</ul>")
    if tailored.certifications:
        lines.append("<h2>Certifications</h2><ul>" + "".join(
            f"<li>{esc(c.name)}" + (f" - {esc(c.issuer)}" if c.issuer else "") +
            (f" ({esc(c.year)})" if c.year else "") + "</li>"
            for c in tailored.certifications) + "</ul>")
    if tailored.languages:
        lines.append("<h2>Languages</h2><ul>" + "".join(
            f"<li>{esc(l.name)}" + (f" ({esc(l.level)})" if l.level else "") + "</li>"
            for l in tailored.languages) + "</ul>")
    if tailored.education:
        lines.append("<h2>Education</h2>")
        for ed in tailored.education:
            hdr = f"<p><b>{esc(ed.degree)}</b>"
            if ed.institution:
                hdr += f", {esc(ed.institution)}"
            rng = fmt_range(ed.start, ed.end)
            if rng:
                hdr += f" ({esc(rng)})"
            lines.append(hdr + "</p>")
            if ed.details:
                lines.append(f"<p>{esc(ed.details)}</p>")
    if tailored.projects:
        lines.append("<h2>Projects</h2>")
        for p in tailored.projects:
            lines.append(f"<p><b>{esc(p.name)}</b></p>")
            if p.description:
                lines.append(f"<p>{esc(p.description)}</p>")
            if p.bullets:
                lines.append("<ul>" + "".join(f"<li>{esc(b.text)}</li>" for b in p.bullets) + "</ul>")
    body = "\n".join(lines)
    return f"""<html><head><style>
@page {{ size: A4; margin: 1.7cm; }}
body {{ font-family: Helvetica; font-size: 10.5pt; color: black; line-height: 1.35; }}
h1 {{ font-size: 14pt; margin: 0 0 2pt 0; }}
h2 {{ font-size: 12pt; margin: 8pt 0 2pt 0; border-bottom: 0.5pt solid black; }}
p {{ margin: 0 0 3pt 0; }}
ul {{ margin: 0 0 4pt 14pt; padding: 0; }}
li {{ margin: 0 0 1.5pt 0; }}
</style></head><body>{body}</body></html>"""


# --------------------------------------------------------------------------- #
# Designed version: two-column layout, one accent color
# --------------------------------------------------------------------------- #

def designed_html(cv, tailored) -> str:
    contact = tailored.contact
    role = tailored.role_title
    main_rows = []
    if tailored.summary:
        main_rows.append(
            f"<h2>Summary</h2><p class='sum'>{esc(tailored.summary)}</p>")
    if tailored.experience:
        main_rows.append("<h2>Experience</h2>")
        for e in tailored.experience:
            rng = fmt_range(e.start, e.end)
            main_rows.append(
                f"<p class='role'><b>{esc(e.title)}</b>"
                + (f" · {esc(e.company)}" if e.company else "")
                + (f"<br/><span class='dates'>{esc(rng)}"
                   + (f" · {esc(e.location)}" if e.location else "") + "</span>" if rng else "")
                + "</p>")
            if e.bullets:
                main_rows.append("<ul>" + "".join(
                    f"<li>{esc(b.text)}</li>" for b in e.bullets) + "</ul>")
    for ed in tailored.education:
        rng = fmt_range(ed.start, ed.end)
        main_rows.append(f"<h2>Education</h2><p class='role'><b>{esc(ed.degree)}</b>"
                         + (f" · {esc(ed.institution)}" if ed.institution else "")
                         + (f"<br/><span class='dates'>{esc(rng)}</span>" if rng else "") + "</p>")
        if ed.details:
            main_rows.append(f"<p>{esc(ed.details)}</p>")
    for p in tailored.projects:
        main_rows.append(f"<p class='role'><b>{esc(p.name)}</b></p>")
        if p.description:
            main_rows.append(f"<p>{esc(p.description)}</p>")
        if p.bullets:
            main_rows.append("<ul>" + "".join(f"<li>{esc(b.text)}</li>" for b in p.bullets) + "</ul>")

    side_rows = []
    if tailored.skills:
        side_rows.append("<h2>Skills</h2><p>" + esc(", ".join(tailored.skills)) + "</p>")
    if tailored.languages:
        side_rows.append("<h2>Languages</h2>" + "".join(
            f"<p>{esc(l.name)}" + (f" - {esc(l.level)}" if l.level else "") + "</p>"
            for l in tailored.languages))
    if tailored.certifications:
        side_rows.append("<h2>Certifications</h2>" + "".join(
            f"<p>{esc(c.name)}" + (f" - {esc(c.issuer)}" if c.issuer else "")
            + (f" ({esc(c.year)})" if c.year else "") + "</p>"
            for c in tailored.certifications))

    meta = [x for x in [contact.email, contact.phone, contact.location] if x]
    header = (f"<h1>{esc(contact.name or '')}</h1>"
              + (f"<p class='tagline'>{esc(role)}</p>" if role else "")
              + (f"<p class='meta'>{esc(' | '.join(meta))}</p>" if meta else "")
              + ("".join(f"<p class='meta'>{esc(l)}</p>" for l in contact.links)))

    return f"""<html><head><style>
@page {{ size: A4; margin: 1.4cm; }}
body {{ font-family: Helvetica; font-size: 10pt; color: #2c3e50; line-height: 1.45; }}
h1 {{ font-size: 19pt; color: {ACCENT}; margin: 0; letter-spacing: 1px; }}
.tagline {{ color: #5d6d7e; font-size: 11.5pt; margin: 2pt 0 4pt 0; }}
.meta {{ color: #5d6d7e; font-size: 8.5pt; margin: 1pt 0; }}
h2 {{ color: {ACCENT}; font-size: 11pt; margin: 8pt 0 3pt 0;
      border-bottom: 1pt solid {ACCENT_LIGHT}; padding-bottom: 2pt; }}
.sum {{ margin: 0 0 4pt 0; }}
.role {{ margin: 5pt 0 0 0; }}
.dates {{ color: #5d6d7e; font-size: 9pt; }}
ul {{ margin: 2pt 0 5pt 13pt; padding: 0; }}
li {{ margin: 0 0 2pt 0; }}
td {{ vertical-align: top; }}
.side {{ background-color: #f4f8fb; padding: 8pt; }}
.side h2 {{ font-size: 10pt; border-bottom: none; margin: 0 0 3pt 0; }}
.side p {{ margin: 0 0 5pt 0; font-size: 9pt; }}
</style></head><body>
{header}
<table width="100%" cellspacing="0" cellpadding="0"><tr>
<td width="67%" style="padding-right: 10pt;">{''.join(main_rows)}</td>
<td width="33%"><div class="side">{''.join(side_rows)}</div></td>
</tr></table>
</body></html>"""


_RENDERERS = None


def _renderers():
    global _RENDERERS
    if _RENDERERS is None:
        from xhtml2pdf import pisa
        _RENDERERS = pisa
    return _RENDERERS


def count_pdf_pages(pdf_bytes: bytes) -> int:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return len(reader.pages)


def render_pdf(html_doc: str) -> bytes:
    pisa = _renderers()
    buf = io.BytesIO()
    result = pisa.CreatePDF(html_doc, dest=buf, encoding="latin-1")
    if result.err > 1:
        raise RuntimeError(f"PDF rendering failed ({result.err} errors)")
    return buf.getvalue()


def render_designed_pdf_with_limit(cv, tailored, max_pages: int = 2) -> bytes:
    pdf = render_pdf(designed_html(cv, tailored))
    pages = count_pdf_pages(pdf)
    while pages > max_pages and (tailored.projects or
                                 len(tailored.experience) > 1):
        if tailored.projects:
            tailored.projects = tailored.projects[:-1]
        elif len(tailored.experience) > 1 and len(tailored.experience[-1].bullets) > 2:
            tailored.experience[-1].bullets = tailored.experience[-1].bullets[:-1]
        new = render_pdf(designed_html(cv, tailored))
        if count_pdf_pages(new) >= pages:
            break
        pdf, pages = new, count_pdf_pages(new)
    return pdf


def export_file_bytes(tailored, fmt: str, cv=None, max_pages: int = 2) -> tuple[bytes, str, str]:
    """Returns (bytes, filename, media_type). cv is needed for nothing currently."""
    first, *rest = (tailored.contact.name or "Name").split()
    last = rest[-1] if rest else ""
    role = re.sub(r"[^A-Za-zÀ-ÿ0-9]+", "-", tailored.role_title or "CV").strip("-") or "CV"
    base = f"{first}_{last}_{role}_CV".strip("_")
    if fmt == "ats_pdf":
        pdf = render_pdf(ats_html(cv, tailored))
        return pdf, f"{base}.pdf", "application/pdf"
    if fmt == "designed_pdf":
        pdf = render_designed_pdf_with_limit(cv, tailored, max_pages)
        return pdf, f"{base}.pdf", "application/pdf"
    if fmt == "ats_docx":
        return export_docx(tailored), f"{base}.docx", \
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    raise ValueError(f"Unknown export format: {fmt}")


# --------------------------------------------------------------------------- #
# DOCX (ATS)
# --------------------------------------------------------------------------- #

def export_docx(tailored) -> bytes:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(10.5)

    contact = tailored.contact
    name_line = tailored.contact.name or ""
    if tailored.role_title:
        name_line = f"{tailored.role_title} - {name_line}"
    h = doc.add_paragraph()
    run = h.add_run(name_line)
    run.bold = True
    run.font.size = Pt(14)

    meta = [x for x in [contact.email, contact.phone, contact.location] if x] + list(contact.links)
    if meta:
        p = doc.add_paragraph(" | ".join(meta))
        p.paragraph_format.space_after = Pt(6)

    def heading(text):
        p = doc.add_paragraph()
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(12)
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)

    def bullets(items):
        for it in items:
            doc.add_paragraph(it, style="List Bullet")

    if tailored.summary:
        heading("Summary")
        doc.add_paragraph(tailored.summary)
    if tailored.experience:
        heading("Experience")
        for e in tailored.experience:
            title = f"{e.title}" + (f", {e.company}" if e.company else "")
            rng = fmt_range(e.start, e.end)
            if e.location:
                title += f" - {e.location}"
            p = doc.add_paragraph()
            run = p.add_run(title)
            run.bold = True
            if rng:
                p2 = doc.add_paragraph(rng)
                p2.paragraph_format.space_after = Pt(1)
            bullets([b.text for b in e.bullets]) if e.bullets else None
    if tailored.skills:
        heading("Skills")
        doc.add_paragraph(", ".join(tailored.skills))
    if tailored.certifications:
        heading("Certifications")
        for c in tailored.certifications:
            line = c.name + (f" - {c.issuer}" if c.issuer else "") + (f" ({c.year})" if c.year else "")
            doc.add_paragraph(line, style="List Bullet")
    if tailored.languages:
        heading("Languages")
        for l in tailored.languages:
            doc.add_paragraph(l.name + (f" - {l.level}" if l.level else ""), style="List Bullet")
    if tailored.education:
        heading("Education")
        for ed in tailored.education:
            line = ed.degree + (f", {ed.institution}" if ed.institution else "")
            rng = fmt_range(ed.start, ed.end)
            if rng:
                line += f" ({rng})"
            doc.add_paragraph(line)
    if tailored.projects:
        heading("Projects")
        for p_ in tailored.projects:
            p = doc.add_paragraph()
            run = p.add_run(p_.name)
            run.bold = True
            if p_.description:
                doc.add_paragraph(p_.description)
            bullets([b.text for b in p_.bullets]) if p_.bullets else None

    for section in doc.sections:
        section.top_margin = Inches(0.7)
        section.bottom_margin = Inches(0.7)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
