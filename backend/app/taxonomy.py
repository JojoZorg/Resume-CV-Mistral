"""Bilingual (EN / PT-BR) skill taxonomy, role profiles, and tailoring vocabulary.

Everything in this module is used to keep the pipeline grounded: skills are only
ever matched against text the user actually wrote, and tailoring vocabulary
swaps are limited to conservative, meaning-preserving synonyms.
"""
from __future__ import annotations
import re

# Canonical skill -> (display, group, regex pattern, broadly valuable)
SKILLS: dict[str, tuple[str, str, str, bool]] = {
    # programming languages
    "python": ("Python", "Programming languages", r"python", True),
    "javascript": ("JavaScript", "Programming languages", r"javascript|\bjs\b|java[\s-]?script", True),
    "typescript": ("TypeScript", "Programming languages", r"typescript|\bts\b", True),
    "java": ("Java", "Programming languages", r"\bjava\b(?!script)", True),
    "c#": ("C#", "Programming languages", r"\bc#\b|c[\s-]?sharp", True),
    "c++": ("C++", "Programming languages", r"\bc\+\+|cpp\b", True),
    "go": ("Go", "Programming languages", r"\bgo(?:lang)?\b", True),
    "rust": ("Rust", "Programming languages", r"\brust\b", True),
    "php": ("PHP", "Programming languages", r"\bphp\b", False),
    "ruby": ("Ruby", "Programming languages", r"\bruby\b|\brails\b", False),
    "kotlin": ("Kotlin", "Programming languages", r"\bkotlin\b", False),
    "swift": ("Swift", "Programming languages", r"\bswift\b", False),
    "sql": ("SQL", "Programming languages", r"\bsql\b", True),
    "bash": ("Bash", "Programming languages", r"\bbash\b|shell script", False),
    "r_lang": ("R", "Programming languages", r"\br\b(?![a-z])", False),
    "scala": ("Scala", "Programming languages", r"\bscala\b", False),
    # frameworks
    "react": ("React", "Frameworks & libraries", r"\breact(?:js|\.js|\.jsx)?\b", True),
    "vue": ("Vue.js", "Frameworks & libraries", r"\bvue(?:js|\.js)?\b", False),
    "angular": ("Angular", "Frameworks & libraries", r"\bangular(?:js)?\b", False),
    "django": ("Django", "Frameworks & libraries", r"\bdjango\b", False),
    "flask": ("Flask", "Frameworks & libraries", r"\bflask\b", False),
    "fastapi": ("FastAPI", "Frameworks & libraries", r"\bfastapi\b", False),
    "spring": ("Spring", "Frameworks & libraries", r"\bspring(?: boot)?\b", False),
    "nodejs": ("Node.js", "Frameworks & libraries", r"\bnode(?:\.?js)?\b", True),
    "express": ("Express.js", "Frameworks & libraries", r"\bexpress(?:js|\.js)\b|\bnodejs\b", True),
    "dotnet": (".NET", "Frameworks & libraries", r"\.net\b|\bdotnet\b|asp\.net", True),
    "laravel": ("Laravel", "Frameworks & libraries", r"\blaravel\b", False),
    "nextjs": ("Next.js", "Frameworks & libraries", r"\bnext(?:\.js|js)\b", False),
    "tailwind": ("Tailwind CSS", "Frameworks & libraries", r"\btailwind\b", False),
    "pytest": ("pytest", "Frameworks & libraries", r"\bpytest\b", False),
    "jest": ("Jest", "Frameworks & libraries", r"\bjest\b", False),
    "selenium": ("Selenium", "Frameworks & libraries", r"\bselenium\b", False),
    "cypress": ("Cypress", "Frameworks & libraries", r"\bcypress\b", False),
    "rpgle": ("RPGILE", "Legacy & enterprise", r"\brpg\s?(?:ile|iv|4)?\b", False),
    "cobol": ("COBOL", "Legacy & enterprise", r"\bcobol\b", False),
    # data / ml
    "pandas": ("pandas", "Data & ML", r"\bpandas\b", False),
    "numpy": ("NumPy", "Data & ML", r"\bnumpy\b", False),
    "scikit": ("scikit-learn", "Data & ML", r"scikit[\s-]?learn|sklearn", False),
    "pytorch": ("PyTorch", "Data & ML", r"\bpytorch\b", False),
    "tensorflow": ("TensorFlow", "Data & ML", r"\btensorflow\b", False),
    "spark": ("Apache Spark", "Data & ML", r"\bspark\b", False),
    "airflow": ("Apache Airflow", "Data & ML", r"\bairflow\b", False),
    "dbt": ("dbt", "Data & ML", r"\bdbt\b", False),
    "kafka": ("Kafka", "Data & ML", r"\bkafka\b", False),
    "etl": ("ETL / data pipelines", "Data & ML", r"\betl\b|elt\b|data pipeline|pipeline de dados", True),
    "tableau": ("Tableau", "Data & ML", r"\btableau\b", False),
    "powerbi": ("Power BI", "Data & ML", r"power[\s-]?bi", False),
    "looker": ("Looker", "Data & ML", r"\blooker\b", False),
    "ml": ("Machine learning", "Data & ML", r"machine learning|aprendizado de m[aá]quina", True),
    "llm": ("LLMs / applied AI", "Data & ML", r"\bllm\b|llms\b|gpt\b|mistral\b|openai\b|generative ai|ia generativa", True),
    # infra / devops
    "aws": ("AWS", "Cloud & infra", r"\baws\b|amazon web services", True),
    "gcp": ("GCP", "Cloud & infra", r"\bgcp\b|google cloud", True),
    "azure": ("Azure", "Cloud & infra", r"\bazure\b", True),
    "docker": ("Docker", "Cloud & infra", r"\bdocker\b", True),
    "kubernetes": ("Kubernetes", "Cloud & infra", r"\bkubernetes\b|\bk8s\b", True),
    "terraform": ("Terraform", "Cloud & infra", r"\bterraform\b", False),
    "ci_cd": ("CI/CD", "Cloud & infra", r"ci\s?/?\s?cd|continuous (?:integration|delivery|deployment)|integra[aA][aA][- ]?o cont[uú]nua", True),
    "linux": ("Linux", "Cloud & infra", r"\blinux\b|ubuntu\b|debian\b", True),
    "nginx": ("Nginx", "Cloud & infra", r"\bnginx\b", False),
    "ansible": ("Ansible", "Cloud & infra", r"\bansible\b", False),
    "microservices": ("Microservices", "Architecture", r"microservi|micro-service|micro service", True),
    "rest": ("REST APIs", "Architecture", r"\brest(?:ful)?\b(?!\s+in\s+peace)", True),
    "graphql": ("GraphQL", "Architecture", r"\bgraphql\b", False),
    "grpc": ("gRPC", "Architecture", r"\bgrpc\b", False),
    "serverless": ("Serverless", "Cloud & infra", r"\bserverless\b|lambda\b", False),
    # databases
    "postgres": ("PostgreSQL", "Databases", r"postgres", True),
    "mysql": ("MySQL", "Databases", r"\bmysql\b|maria ?db", True),
    "mongodb": ("MongoDB", "Databases", r"mongo", False),
    "redis": ("Redis", "Databases", r"\bredis\b", False),
    "elasticsearch": ("Elasticsearch", "Databases", r"elastic ?search", False),
    "snowflake": ("Snowflake", "Databases", r"snowflake", False),
    "dynamodb": ("DynamoDB", "Databases", r"dynamo\s?db", False),
    "oracle_db": ("Oracle DB", "Legacy & enterprise", r"\boracle\b", False),
    "db2": ("DB2", "Legacy & enterprise", r"\bdb2\b", False),
    # practices
    "agile": ("Agile / Scrum", "Ways of working", r"\bagile\b|scrum\b|kanban\b|methodolog", True),
    "tdd": ("TDD / testing", "Ways of working", r"\btdd\b|test[- ]driven|testes unit", False),
    "code_review": ("Code review & mentoring", "Ways of working", r"code review|mentoria|mentor(?:ed|ing|ia)|code review|reviewed (?:code|prs)|pull request", True),
    "observability": ("Observability", "Cloud & infra", r"observab|monitoring|monitoramento|datadog|grafana|prometheus|sentry", False),
    # soft / leadership
    "leadership": ("Team leadership", "Leadership & soft skills", r"led (?:a|the|um|uma|o|as|os) (?:team|equipe)|managed (?:a|the|um|uma|o|as|os) (?:team|equipe)|team lead|l[uí]der (?:t[ée]cnico|de equipe)|lided|gerenciei|liderei", True),
    "mentoring": ("Mentoring", "Leadership & soft skills", r"mentor", True),
    "communication": ("Communication", "Leadership & soft skills", r"communica|comunica|stakeholder|apresenta", True),
    "product_thinking": ("Product thinking", "Leadership & soft skills", r"product (?:owner|thinking|backlog)|roadmap|requisitos|requirements", True),
    "hiring": ("Hiring & interviews", "Leadership & soft skills", r"hiring|entrevista|interview|recrut|candidat", False),
    "customer_facing": ("Customer-facing work", "Leadership & soft skills", r"customer|cliente|client-facing|atendimento", True),
    # domains
    "fintech": ("FinTech", "Domains", r"fintech|banking|ban[aá]rio|pagamento|payment|finance|financei", False),
    "ecommerce": ("E-commerce", "Domains", r"e-?commerce|marketplace|loja virtual", False),
    "healthtech": ("HealthTech", "Domains", r"health|sa[uú]de|m[eé]dic|hospital|cl[ií]nic", False),
    "edtech": ("EdTech", "Domains", r"edtech|educa|e-?learning|ensino", False),
    "logistics": ("Logistics", "Domains", r"log[íi]stic|supply chain|warehouse|fret", False),
    "telecom": ("Telecom / embedded", "Domains", r"telecom|iot\b|embedded|embarcad", False),
    "saas": ("SaaS", "Domains", r"\bsaas\b", True),
}

# JD vocabulary -> what a truthful CV equivalent may look like. Both directions
# must map to the SAME underlying experience; we never map concepts the user
# has not written anywhere.
VOCAB_SYNONYMS: list[tuple[str, str]] = [
    (r"\bled\b", "managed"),
    (r"\bmanaged\b", "led"),
    (r"\bmanaged a team\b", "led a team"),
    (r"\bcreated\b", "built"),
    (r"\bbuilt\b", "created"),
    (r"\bmade\b", "built"),
    (r"\bengineered\b", "built"),
    (r"\bdeveloped\b", "built"),
    (r"\bbuilt\b", "developed"),
    (r"\bworked on\b", "contributed to"),
    (r"\bcontributed to\b", "worked on"),
    (r"\bdesigned\b", "architected"),
    (r"\barchitected\b", "designed"),
    (r"\bimproved\b", "enhanced"),
    (r"\benhanced\b", "improved"),
    (r"\bdesenvolvi\b", "desenvolvido"),
    (r"\bgerenciei\b", "liderei"),
    (r"\bliderei\b", "gerenciei"),
    (r"\bparticipei de\b", "contribu[ií] em"),
    (r"\bresponsable por\b", "encarregado de"),
]

STOPWORDS = set(
    """a an the and or but if then else of for to in on at by with from as is are was were be been
de do da das dos das em no na nos nas um uma uns umas e ou para por com sem sobre entre que se ao
à às até após durante como onde quando who which what this that these those their our your its
will can may must have has had i you we they he she it é são foi era está estão the nós você""".split()
)

ROLE_PROFILES: list[dict] = [
    # title, aliases for matching, (skill key -> weight), seniority-ladder key
    {"title": "Backend Engineer", "cat": "strong", "alt": ["backend", "back-end"],
     "skills": {"python": 3, "java": 3, "go": 3, "nodejs": 2, "sql": 2, "postgres": 2, "rest": 3,
                "docker": 1, "ci_cd": 1, "microservices": 2, "redis": 1, "kafka": 2}},
    {"title": "Frontend Engineer", "cat": "strong", "alt": ["frontend", "front-end"],
     "skills": {"javascript": 3, "typescript": 2, "react": 3, "vue": 2, "angular": 2, "nextjs": 2,
                "tailwind": 1, "rest": 1}},
    {"title": "Full-Stack Engineer", "cat": "strong", "alt": ["full[- ]?stack", "desenvolvedor full"],
     "skills": {"javascript": 2, "typescript": 2, "react": 2, "nodejs": 2, "python": 2, "java": 2,
                "sql": 2, "postgres": 1, "rest": 2, "docker": 1}},
    {"title": "Data Engineer", "cat": "latent", "alt": ["data engineer", "engenheiro de dados"],
     "skills": {"python": 2, "sql": 3, "spark": 3, "airflow": 3, "etl": 3, "dbt": 2, "kafka": 2,
                "snowflake": 2, "aws": 1}},
    {"title": "Data Analyst", "cat": "latent", "alt": ["data analyst", "analista de dados"],
     "skills": {"sql": 3, "python": 1, "r_lang": 1, "tableau": 3, "powerbi": 3, "pandas": 2, "looker": 2}},
    {"title": "Machine Learning Engineer", "cat": "latent", "alt": ["machine learning engineer", "ml engineer"],
     "skills": {"python": 3, "pytorch": 3, "tensorflow": 3, "scikit": 2, "ml": 3, "pandas": 1, "spark": 1,
                "llm": 1, "docker": 1}},
    {"title": "DevOps Engineer", "cat": "latent", "alt": ["devops", "sre", "site reliability"],
     "skills": {"docker": 3, "kubernetes": 3, "terraform": 3, "aws": 2, "gcp": 2, "azure": 2,
                "ci_cd": 3, "linux": 2, "observability": 2, "ansible": 2}},
    {"title": "Mobile Engineer", "cat": "adjacent", "alt": ["mobile", "android", "ios"],
     "skills": {"swift": 3, "kotlin": 3}},
    {"title": "Platform Engineer", "cat": "adjacent", "alt": ["platform"],
     "skills": {"kubernetes": 3, "docker": 2, "ci_cd": 3, "terraform": 2, "aws": 2, "python": 1}},
    {"title": "QA Automation Engineer", "cat": "adjacent", "alt": ["qa", "test automation", "quality"],
     "skills": {"selenium": 3, "cypress": 3, "pytest": 2, "jest": 2, "tdd": 2, "python": 1, "javascript": 1}},
    {"title": "Engineering Manager", "cat": "latent", "alt": ["engineering manager", "gerente de engenharia"],
     "skills": {"leadership": 4, "hiring": 3, "mentoring": 2, "product_thinking": 1, "agile": 2, "code_review": 1}},
    {"title": "Tech Lead", "cat": "latent", "alt": ["tech lead", "lead engineer", "l[íi]der t[ée]cnico"],
     "skills": {"leadership": 3, "code_review": 2, "mentoring": 2, "agile": 1, "microservices": 1,
                "python": 1, "javascript": 1, "java": 1}},
    {"title": "Developer Advocate / DevRel", "cat": "latent", "alt": ["developer advocate", "devrel", "evangelist"],
     "skills": {"mentoring": 3, "communication": 3, "customer_facing": 2, "python": 1, "javascript": 1}},
    {"title": "Solutions Architect", "cat": "latent", "alt": ["solutions architect", "arquiteto"],
     "skills": {"aws": 2, "gcp": 2, "azure": 2, "microservices": 2, "rest": 1, "docker": 1,
                "communication": 2, "leadership": 1, "sql": 1}},
    {"title": "Product Manager (technical)", "cat": "latent", "alt": ["product manager"],
     "skills": {"product_thinking": 4, "agile": 2, "communication": 2, "customer_facing": 2, "sql": 1}},
    {"title": "API / Integration Engineer", "cat": "adjacent", "alt": ["integration"],
     "skills": {"rest": 3, "graphql": 2, "grpc": 2, "python": 1, "java": 1, "nodejs": 1, "sql": 1}},
    {"title": "Legacy Systems Engineer (IBM i / RPG)", "cat": "adjacent", "alt": ["legacy systems"],
     "skills": {"rpgle": 4, "db2": 3, "cobol": 3, "oracle_db": 1}},
    {"title": "Software Engineer (generalist)", "cat": "strong", "alt": ["software engineer"],
     "skills": {"python": 2, "java": 2, "javascript": 2, "sql": 2, "rest": 2, "docker": 1, "ci_cd": 1,
                "agile": 1, "git_any": 0}},
]

SENIORITY_LADDER = ["intern", "junior", "mid", "senior", "lead", "principal", "executive"]

NEXT_LEVEL_SIGNALS = {
    "junior": ["feature work", "code quality", "testing", "collaboration"],
    "mid": ["end-to-end ownership", "system design basics", "production incidents"],
    "senior": [r"led (?:a|the) (?:team|project)", "system architecture", "mentoring",
               "cross-functional work", "production scalability"],
    "lead": ["team leadership", "roadmap ownership", "hiring", "stakeholder management",
             "architectural decisions across teams"],
    "principal": ["org-wide technical strategy", "multi-team initiatives", "external influence (talks, OSS)"],
}

COMPILED_SKILLS = None


def compiled_skills():
    global COMPILED_SKILLS
    if COMPILED_SKILLS is None:
        COMPILED_SKILLS = {
            k: (disp, group, re.compile(pat, re.IGNORECASE), broad)
            for k, (disp, group, pat, broad) in SKILLS.items()
        }
    return COMPILED_SKILLS


def detect_skills(text: str) -> dict[str, list[str]]:
    """Return {skill_key: matched display names} found in text (CV or JD)."""
    findings: dict[str, list[str]] = {}
    lowered = text.lower()
    for key, (disp, group, rx, broad) in compiled_skills().items():
        for m in rx.finditer(lowered):
            findings.setdefault(key, [disp])
            break
    return findings
