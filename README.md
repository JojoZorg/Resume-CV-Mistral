# CV Tailoring Tool with Career Insights

Tailor a CV to a specific job description **without fabricating anything**, review every
change in a side-by-side diff, export an ATS-optimized PDF/DOCX plus a designed PDF, and
get standalone career recommendations grounded in your CV.

## Core guarantee: no fabrication

The tailoring step may only **rephrase**, **reorder**, **subset**, and **re-summarize**
content that already exists in your CV. Every tailored bullet carries `source_ids`
referencing the exact original bullet it came from:

- A second, independent **fabrication check** compares the tailored CV against the
  original and flags any skill, company, date, metric, or title that was not in the
  original. Flagged exports are **blocked** (an explicit override exists, clearly
  marked).
- If the JD requires something you don't have, it surfaces in a **Gaps panel** with
  suggested ways to address it — it is never silently added to your CV.
- Bullets that cannot be traced to a source are rejected during generation.

## Architecture

```
backend/                 FastAPI (Python)
  app/
    parsing/             PDF/DOCX text extraction (scanned-PDF detection included),
                         bilingual (EN/PT-BR) structural CV parser, JD URL fetch
    jd/                  JD analysis: skills (required vs nice-to-have), seniority,
                         years, responsibilities, soft skills, domain, ATS keywords
    llm/                 Provider layer: Ollama (local) / OpenAI-compatible /
                         deterministic offline mode (default)
    tailoring/           Bullet scoring + reorder + subset + vocabulary mirroring,
                         per-bullet traceability, independent fabrication check
    insights/            Career insights: strong fits, adjacent roles, latent paths,
                         skill inventory, next-level gaps, next steps
    render/              ATS PDF (single column, no tables), Designed PDF (two-column
                         accent layout), ATS DOCX — via xhtml2pdf / python-docx
  tests/                 pytest suite incl. deliberate fabrication-injection tests

frontend/                React + Vite
  src/components/
    CvStep.jsx           Upload → parsed-structure preview + inline corrections
    JdStep.jsx           JD via paste / PDF / DOCX / URL + editable extraction
                         + tone / language / 1-2 pages / notes
    DiffView.jsx         Side-by-side diff, word-level highlights, per-bullet
                         Edit/Revert/Trace links, Gaps panel, export gate
    Insights.jsx         Career insights tab
```

The API is **stateless**: no CV or JD is stored server-side; the client sends the full
session payload with each request. CV data persists only in your browser's
`localStorage`, with a **Delete my data** button in the header.

## Privacy

- **Default (no LLM configured):** 100% deterministic, on-machine processing.
- **Ollama (recommended):** set `LLM_PROVIDER=ollama` — your data never leaves the
  machine.
- **Cloud (optional):** set `LLM_PROVIDER=openai` with `OPENAI_BASE_URL` +
  `OPENAI_API_KEY` + `OPENAI_MODEL` — use a **no-training / enterprise** endpoint. The
  active mode is shown by `GET /api/health` and disclosed in the UI.
- No analytics. No accounts. No server-side persistence.

## Running

Backend (Python 3.9+; tested on 3.9 and 3.12):

```bash
pip install -r backend/requirements.txt
python run.py                    # starts the API on http://127.0.0.1:8000
```

`run.py` is a convenience launcher — equivalent to:

```bash
cd backend
uvicorn app.main:app --port 8000
```

Run the two processes in separate terminals (backend first, then the
frontend). On Windows, use your venv for both:
`venv\Scripts\activate` before each command.

Frontend:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api to :8000
```

Optional local LLM (better rephrasing, translation and richer insights):

```bash
ollama pull llama3.1
LLM_PROVIDER=ollama OLLAMA_MODEL=llama3.1 uvicorn app.main:app --port 8000
```

Without a provider, everything still works: tailoring falls back to conservative,
fully-traceable vocabulary mirroring (translation between PT/EN requires an LLM and is
skipped with an explanatory note).

Tests:

```bash
cd backend && python -m pytest tests -q
```

## LLM quality bar

The tailoring prompt includes the extracted CV structured data, JD requirements, the
explicit no-fabrication rules, and the allowed operations list. Every output bullet must
reference its original bullet ID; untraceable bullets are rejected and regenerated, with
a verbatim-original fallback. Tone instructs the model to preserve your voice and
sentence length rather than rewriting the CV in "LLM register".

## MVP acceptance coverage

- 2-page PDF CV + pasted JD → ATS PDF, designed PDF, DOCX (filename
  `First_Last_Role_CV.ext`), export blocked until diff review acknowledgement.
- Diff view: word-level add/remove highlighting, per-bullet trace links that scroll to
  the source bullet, per-section change banner.
- Deliberate fabrication attempts (injected skills/dates/metrics/companies) are caught
  by tests and block export.
- Career insights tab: strong fits / adjacent / latent paths / skill inventory /
  next-level gaps / next steps, each with CV citations.
- PT-BR and EN CVs and JDs supported (mixed pairs work fully with an LLM configured).
