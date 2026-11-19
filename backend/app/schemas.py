"""Pydantic models shared across the pipeline."""
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ContactInfo(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: list[str] = []


class ExperienceEntry(BaseModel):
    id: str
    title: str
    company: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    bullets: list[str] = []

    @field_validator("title")
    @classmethod
    def _title_not_none(cls, v):
        return v or "Unspecified title"


class EducationEntry(BaseModel):
    id: str
    degree: str
    institution: str = ""
    start: str = ""
    end: str = ""
    details: str = ""


class Certification(BaseModel):
    id: str
    name: str
    issuer: str = ""
    year: str = ""


class LanguageSkill(BaseModel):
    name: str
    level: str = ""


class ProjectEntry(BaseModel):
    id: str
    name: str
    description: str = ""
    bullets: list[str] = []


class CVData(BaseModel):
    contact: ContactInfo = ContactInfo()
    summary: str = ""
    experience: list[ExperienceEntry] = []
    education: list[EducationEntry] = []
    skills: list[str] = []
    certifications: list[Certification] = []
    languages: list[LanguageSkill] = []
    projects: list[ProjectEntry] = []
    raw_text: str = ""
    warnings: list[str] = []
    source_language: str = ""

    def all_bullets(self):
        """Yield (id, text) for every traceable bullet in the CV."""
        for e in self.experience:
            for i, b in enumerate(e.bullets):
                yield f"{e.id}#{i}", b
        for p in self.projects:
            for i, b in enumerate(p.bullets):
                yield f"{p.id}#{i}", b


class JDRequirements(BaseModel):
    role_title: str = ""
    seniority: str = ""
    years_of_experience: str = ""
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    responsibilities: list[str] = []
    soft_skills: list[str] = []
    domain: str = ""
    keywords: list[str] = []
    language: str = ""
    raw_text: str = ""


class TailorOptions(BaseModel):
    tone: str = "original"  # original | formal | conversational
    target_language: str = "same"  # same | pt-BR | en
    max_pages: int = Field(default=1, ge=1, le=2)
    user_notes: str = ""


class TailoredBullet(BaseModel):
    text: str
    source_ids: list[str]
    change: str = "kept"  # kept | reworded | moved | subset-dropped-not-shown


class TailoredExperienceEntry(BaseModel):
    id: str
    title: str
    company: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    bullets: list[TailoredBullet] = []


class TailoredProjectEntry(BaseModel):
    id: str
    name: str
    description: str = ""
    bullets: list[TailoredBullet] = []


class TailoredCV(BaseModel):
    contact: ContactInfo
    summary: str = ""
    summary_source_ids: list[str] = []
    role_title: str = ""
    experience: list[TailoredExperienceEntry] = []
    education: list[EducationEntry] = []
    skills: list[str] = []
    skill_order_note: str = ""
    certifications: list[Certification] = []
    languages: list[LanguageSkill] = []
    projects: list[TailoredProjectEntry] = []
    excluded_bullet_ids: list[str] = []
    notes: str = ""


class FabricationFlag(BaseModel):
    kind: str  # skill | company | date | metric | title | other
    value: str
    location: str
    detail: str


class FabricationReport(BaseModel):
    flags: list[FabricationFlag] = []
    checked_entities: int = 0
    passed: bool = True


class ChangeCount(BaseModel):
    section: str
    added: int = 0
    reworded: int = 0
    removed: int = 0


class DiffSummary(BaseModel):
    counts: list[ChangeCount] = []
    total: int = 0



class JDAnalysisRequest(BaseModel):
    mode: str = "text"  # text | file | url
    text: str = ""
    url: str = ""
    file_b64: str = ""
    filename: str = ""


class TailorRequest(BaseModel):
    cv: CVData
    jd: JDRequirements
    options: TailorOptions = TailorOptions()


class TailorResponse(BaseModel):
    tailored: "TailoredCV"
    fabrication: FabricationReport
    gaps: list[dict] = []
    diff: DiffSummary
    export_hint: str = ""



class RoleRecommendation(BaseModel):
    title: str
    category: str  # strong | adjacent | latent
    score: float
    justification: str
    evidence: list[str] = []
    gaps: list[str] = []


class SkillGroup(BaseModel):
    group: str
    skills: list[str] = []
    breadth: str = ""  # broadly valuable | specialised


class CareerInsights(BaseModel):
    strong_fits: list[RoleRecommendation] = []
    adjacent_roles: list[RoleRecommendation] = []
    latent_paths: list[RoleRecommendation] = []
    skill_inventory: list[SkillGroup] = []
    next_level_gaps: list[str] = []
    next_steps: list[str] = []
    grounding_note: str = "All recommendations are derived strictly from the uploaded CV."



