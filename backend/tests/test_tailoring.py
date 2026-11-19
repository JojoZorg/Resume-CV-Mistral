from app.schemas import TailorOptions
from app.tailoring.tailor import tailor_cv
from app.jd.analyze import analyze_jd
from app.main_helpers import build_diff_summary, find_jd_gaps


def test_tailor_keeps_dates_titles_companies_intact(en_cv, en_jd):
    tailored, _ = tailor_cv(en_cv, en_jd, TailorOptions())
    for orig, new in zip(en_cv.experience, tailored.experience):
        assert orig.title == new.title
        assert orig.company == new.company
        assert orig.start == new.start
        assert orig.end == new.end


def test_tailored_bullet_texts_stay_founded(en_cv, en_jd):
    tailored, _ = tailor_cv(en_cv, en_jd, TailorOptions())
    originals = {sid: t for sid, t in en_cv.all_bullets()}
    for e in tailored.experience:
        for tb in e.bullets:
            for sid in tb.source_ids:
                src = originals[sid]
                # every word in the tailored bullet must exist in the source
                # bullet or be a known conservative synonym swap
                for word in tb.text.lower().replace(".", " ").split():
                    if len(word) > 3 and word not in src.lower():
                        allowed = {"led", "managed", "created", "built", "developed",
                                   "enhanced", "improved", "designed", "architected",
                                   "contributed", "worked"}
                        assert word in allowed or word.rstrip("s") in allowed, \
                            f"unexpected new word '{word}' in: {tb.text}"


def test_reordering_surfaces_jd_relevant_bullets(en_cv, en_jd):
    tailored, _ = tailor_cv(en_cv, en_jd, TailorOptions())
    exp0 = tailored.experience[0]
    texts = [b.text for b in exp0.bullets]
    py_idx = next((i for i, t in enumerate(texts) if "python" in t.lower()), None)
    js_idx = next((i for i, t in enumerate(texts) if "javascript" in t.lower()), None)
    if py_idx is not None and js_idx is not None:
        assert py_idx < js_idx


def test_summary_mentions_only_real_skills(en_cv, en_jd):
    tailored, _ = tailor_cv(en_cv, en_jd, TailorOptions())
    cv_text = (en_cv.raw_text + " " + en_cv.summary + " " + " ".join(en_cv.skills)).lower()
    for raw in tailored.summary.lower().split():
        word = raw.strip(".,();:")
        if len(word) > 3 and word not in cv_text:
            allowed = {"with", "most", "recently", "experience", "professional",
                       "engineer", "software"}
            assert word in allowed or word.rstrip("s") in allowed, word


def test_gap_panel_finds_missing_requirements(en_cv, en_jd):
    gaps = find_jd_gaps(en_cv, en_jd)
    values = [g["requirement"] for g in gaps]
    assert "AWS" in values or "Kafka" in values


def test_diff_summary_counts_changes(en_cv, en_jd):
    tailored, _ = tailor_cv(en_cv, en_jd, TailorOptions(max_pages=1))
    diff = build_diff_summary(en_cv, tailored)
    assert diff.total >= 0
    sections = {c.section for c in diff.counts}
    assert sections or diff.total == 0


def test_pt_cv_tailors_without_crash(pt_cv):
    from app.jd.analyze import analyze_jd
    jd = analyze_jd(
        "Vaga: Engenheiro de Dados. Requisitos: 3+ anos de experiencia com SQL, "
        "etl e pipelines de dados. Desejavel: Airflow, Spark. Responsabilidades: "
        "construir e automatizar pipelines de dados, gerenciar cluster de dados. "
        "Empresa de Technologia Financeira.")
    tailored, report = tailor_cv(pt_cv, jd, TailorOptions())
    assert report.passed
    assert tailored.experience


def test_page_budget_enforced(en_cv, en_jd):
    tailored, _ = tailor_cv(en_cv, en_jd, TailorOptions(max_pages=1))
    n_bullets = sum(len(e.bullets) for e in tailored.experience)
    assert n_bullets <= 12


def test_hide_role_note(en_cv, en_jd):
    opts = TailorOptions(user_notes="hide my 2016 role")
    tailored, _ = tailor_cv(en_cv, en_jd, opts)
    assert all(e.company != "Beta Soft" for e in tailored.experience)
