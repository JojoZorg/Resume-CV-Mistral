from app.schemas import FabricationFlag, ExperienceEntry, TailoredBullet
from app.tailoring.fabrication import check_fabrication
from app.tailoring.tailor import tailor_cv
from app.schemas import TailorOptions


def test_clean_tailoring_passes(en_cv, en_jd):
    tailored, report = tailor_cv(en_cv, en_jd, TailorOptions())
    assert report.passed, [f.detail for f in report.flags]
    local = check_fabrication(en_cv, tailored)
    assert local.passed


def test_injected_skill_is_caught(en_cv, en_jd):
    tailored, _ = tailor_cv(en_cv, en_jd, TailorOptions())
    tailored.skills = tailored.skills + ["BlockChain", "Kubernetes"]
    report = check_fabrication(en_cv, tailored)
    assert not report.passed
    kinds = {f.kind for f in report.flags}
    assert "skill" in kinds


def test_invented_metric_is_caught(en_cv, en_jd):
    tailored, _ = tailor_cv(en_cv, en_jd, TailorOptions())
    targeted = False
    for e in tailored.experience:
        for tb in e.bullets:
            if "requests per second" in tb.text:
                tb.text = tb.text.replace("120", "1200000")
                targeted = True
    assert targeted
    report = check_fabrication(en_cv, tailored)
    assert not report.passed
    assert any(f.kind == "metric" for f in report.flags)


def test_invented_date_is_caught(en_cv, en_jd):
    tailored, _ = tailor_cv(en_cv, en_jd, TailorOptions())
    tailored.experience[0].start = "03/2099"
    report = check_fabrication(en_cv, tailored)
    assert not report.passed
    assert any(f.kind == "date" for f in report.flags)


def test_invented_company_is_caught(en_cv, en_jd):
    tailored, _ = tailor_cv(en_cv, en_jd, TailorOptions())
    tailored.experience[0].company = "Fake Unicorn Inc"
    report = check_fabrication(en_cv, tailored)
    assert not report.passed
    assert any(f.kind == "company" for f in report.flags)


def test_bullet_without_trace_is_flagged(en_cv, en_jd):
    tailored, _ = tailor_cv(en_cv, en_jd, TailorOptions())
    tailored.experience[0].bullets.append(
        TailoredBullet(text="Used Kubernetes in production for 5 years", source_ids=[]))
    report = check_fabrication(en_cv, tailored)
    assert not report.passed
    assert any(f.kind == "other" for f in report.flags)


def test_every_bullet_is_traceable(en_cv, en_jd):
    tailored, _ = tailor_cv(en_cv, en_jd, TailorOptions())
    original_ids = {sid for sid, _ in en_cv.all_bullets()}
    for e in tailored.experience:
        for tb in e.bullets:
            assert tb.source_ids, f"untraceable bullet: {tb.text[:50]}"
            for sid in tb.source_ids:
                assert sid in original_ids
