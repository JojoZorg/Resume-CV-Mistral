"""Shared fixtures: a synthetic EN CV, a PT-BR CV, and JDs."""
import pytest

from app.schemas import (CVData, ContactInfo, ExperienceEntry, EducationEntry,
                         Certification, LanguageSkill, JDRequirements)

EN_CV = CVData(
    contact=ContactInfo(
        name="Maria Silva", email="maria@example.com", phone="+55 11 99999-0000",
        location="Sao Paulo, Brazil", links=["https://linkedin.com/in/maria"]),
    summary="Backend developer with experience in Python web services.",
    experience=[
        ExperienceEntry(
            id="exp-0", title="Software Engineer", company="ACME Tech",
            location="Sao Paulo", start="03/2019", end="05/2023",
            bullets=[
                "Built python REST APIs serving 120 requests per second",
                "Led a team of 3 junior developers through code review and mentoring",
                "Automated deployments with docker and CI/CD, cutting release time from 2 days to 2 hours",
                "Migrated legacy MySQL schemas to postgres",
            ]),
        ExperienceEntry(
            id="exp-1", title="Junior Developer", company="Beta Soft",
            location="Campinas", start="01/2016", end="02/2019",
            bullets=[
                "Developed internal tools in javascript and jquery",
                "Fixed bugs reported by customers and improved test coverage",
            ]),
    ],
    education=[EducationEntry(id="edu-0", degree="B.Sc. Computer Science",
                              institution="USP", start="2011", end="2015")],
    skills=["Python", "Django", "Docker", "PostgreSQL", "MySQL", "JavaScript",
            "REST APIs", "CI/CD", "Linux"],
    certifications=[Certification(id="cert-0", name="AWS Certified Developer",
                                  issuer="Amazon", year="2022")],
    languages=[LanguageSkill(name="Portuguese", level="Native"),
               LanguageSkill(name="English", level="Fluent")],
    raw_text="Software Engineer ACME Tech 03/2019 - 05/2023 Built python REST APIs ...",
    source_language="en",
)

PT_CV = CVData(
    contact=ContactInfo(name="Joao Souza", email="joao@example.com", phone="+55 21 90000-0000"),
    summary="Desenvolvedor de software com experiencia em servicos web em Python.",
    experience=[
        ExperienceEntry(
            id="exp-0", title="Engenheiro de Software", company="Tec bras Ltda",
            location="Rio de Janeiro", start="01/2020", end="Current",
            bullets=[
                "Desenvolvi APIs REST em Python para processamento de pagamentos",
                "Liderei uma equipe de 2 desenvolvedores e conduzi mentorias semanais",
                "Automatizei o pipeline de dados de vendas com SQL e Python",
            ]),
    ],
    skills=["Python", "SQL", "REST APIs", "Docker"],
    certifications=[],
    languages=[LanguageSkill(name="Portugues", level="Nativo")],
    raw_text="Engenheiro de Software Tec bras 01/2020 - atual Desenvolvi APIs REST ...",
    source_language="pt-BR",
)

EN_JD = JDRequirements(
    role_title="Senior Backend Engineer",
    seniority="senior",
    years_of_experience="5+ years",
    required_skills=["Python", "AWS", "REST APIs", "PostgreSQL"],
    preferred_skills=["Kubernetes", "Kafka"],
    responsibilities=["Design and build scalable backend services",
                      "Lead technical decisions across teams"],
    soft_skills=["Communication"],
    domain="SaaS",
    keywords=["Python", "AWS", "REST", "PostgreSQL", "scalable", "backend",
              " Leadership", "microservices"],
    language="en",
    raw_text=("Senior Backend Engineer. Requirements: 5+ years of experience with Python, "
              "AWS, REST APIs and PostgreSQL. Nice to have: Kubernetes, Kafka. "
              "Responsibilities: design and build scalable backend services, lead "
              "technical decisions across teams. Our SaaS company values communication."),
)


@pytest.fixture
def en_cv():
    return EN_CV.model_copy(deep=True)


@pytest.fixture
def pt_cv():
    return PT_CV.model_copy(deep=True)


@pytest.fixture
def en_jd():
    return EN_JD.model_copy(deep=True)
