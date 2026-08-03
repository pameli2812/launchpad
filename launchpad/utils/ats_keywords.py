# ATS Keyword Library for different roles
# Used to evaluate keyword coverage and provide role-specific recommendations

ATS_KEYWORDS_BY_ROLE = {
    "backend_engineer": {
        "required": [
            "REST API", "microservices", "Docker", "Kubernetes", "AWS",
            "Python", "SQL", "database", "CI/CD", "Git",
            "Linux", "Docker", "Linux"
        ],
        "preferred": [
            "Kafka", "Redis", "RabbitMQ", "MongoDB", "PostgreSQL",
            "FastAPI", "Django", "Flask", "Spring", "Node.js",
            "Terraform", "Jenkins", "GitLab CI", "GitHub Actions",
            "gRPC", "GraphQL", "Elasticsearch", "Apache"
        ],
        "ai_keywords": [
            "LLM", "RAG", "Vector Database", "Pinecone", "Weaviate",
            "Prompt Engineering", "Fine-tuning", "Embeddings",
            "Agent", "OpenAI", "Claude", "Hugging Face"
        ]
    },
    "frontend_engineer": {
        "required": [
            "React", "JavaScript", "TypeScript", "HTML", "CSS",
            "Git", "REST API", "responsive design", "component",
            "state management", "testing"
        ],
        "preferred": [
            "Redux", "Vue", "Angular", "Next.js", "Webpack",
            "Jest", "Cypress", "Tailwind", "Material-UI", "Bootstrap",
            "GraphQL", "accessibility", "performance optimization",
            "SEO", "Web performance"
        ],
        "ai_keywords": [
            "AI UI", "prompt engineering", "LLM integration",
            "OpenAI API", "chatbot", "streaming", "real-time"
        ]
    },
    "full_stack_engineer": {
        "required": [
            "React", "Node.js", "JavaScript", "Python", "SQL",
            "REST API", "Git", "Docker", "database",
            "TypeScript", "HTML", "CSS"
        ],
        "preferred": [
            "FastAPI", "Django", "Express", "MongoDB", "PostgreSQL",
            "Redis", "AWS", "Kubernetes", "CI/CD", "testing",
            "GraphQL", "WebSocket", "authentication"
        ],
        "ai_keywords": [
            "LLM", "RAG", "Vector Database", "Agents",
            "Fine-tuning", "Embeddings", "OpenAI"
        ]
    },
    "data_engineer": {
        "required": [
            "Python", "SQL", "ETL", "Apache Spark", "Hadoop",
            "data pipeline", "Git", "AWS", "big data",
            "data warehouse", "schema design"
        ],
        "preferred": [
            "Airflow", "Snowflake", "Redshift", "BigQuery",
            "Kafka", "Scala", "PySpark", "dbt", "Tableau",
            "data quality", "metadata management", "optimization"
        ],
        "ai_keywords": [
            "Machine Learning", "data science", "MLOps",
            "feature engineering", "model pipeline", "data versioning"
        ]
    },
    "devops_engineer": {
        "required": [
            "Docker", "Kubernetes", "AWS", "Linux", "CI/CD",
            "Git", "infrastructure", "automation", "monitoring",
            "cloud", "shell scripting", "Terraform"
        ],
        "preferred": [
            "Jenkins", "GitLab CI", "GitHub Actions", "Ansible",
            "Prometheus", "Grafana", "ELK Stack", "CloudFormation",
            "security", "performance tuning", "disaster recovery"
        ],
        "ai_keywords": [
            "MLOps", "model deployment", "inference serving",
            "container orchestration", "edge computing"
        ]
    },
    "ai_ml_engineer": {
        "required": [
            "Python", "machine learning", "TensorFlow", "PyTorch",
            "data science", "model training", "SQL", "statistics",
            "deep learning", "neural networks"
        ],
        "preferred": [
            "scikit-learn", "Keras", "Hugging Face", "JAX",
            "GPU", "CUDA", "distributed training", "hyperparameter tuning",
            "computer vision", "NLP", "reinforcement learning"
        ],
        "ai_keywords": [
            "LLM", "transformer", "attention mechanism", "fine-tuning",
            "RAG", "prompt engineering", "agent", "multimodal",
            "embedding", "quantization", "RLHF"
        ]
    },
    "product_manager": {
        "required": [
            "product strategy", "roadmap", "metrics", "user research",
            "requirements", "prioritization", "agile", "cross-functional"
        ],
        "preferred": [
            "market analysis", "competitive analysis", "wireframing",
            "SQL", "analytics", "A/B testing", "user interviews",
            "product launch", "stakeholder management"
        ],
        "ai_keywords": [
            "AI/ML features", "generative AI", "LLM integration",
            "prompt engineering", "AI ethics", "responsible AI"
        ]
    },
    "qa_engineer": {
        "required": [
            "testing", "automation", "quality assurance", "test cases",
            "bug tracking", "Python", "Selenium", "Git", "testing framework"
        ],
        "preferred": [
            "Jest", "Cypress", "Appium", "performance testing",
            "load testing", "security testing", "CI/CD",
            "REST API testing", "database testing"
        ],
        "ai_keywords": [
            "AI testing", "LLM evaluation", "prompt testing",
            "model testing", "adversarial testing"
        ]
    }
}

# Keyword categories for skill extraction
SKILL_CATEGORIES = {
    "programming_languages": [
        "Python", "JavaScript", "TypeScript", "Java", "C++", "C#",
        "Go", "Rust", "Ruby", "PHP", "Swift", "Kotlin", "Scala",
        "R", "MATLAB", "Perl", "Bash", "Shell"
    ],
    "cloud_platforms": [
        "AWS", "Azure", "Google Cloud", "GCP", "DigitalOcean",
        "Heroku", "CloudFlare", "Linode", "AWS Lambda", "EC2",
        "S3", "RDS", "DynamoDB", "CloudFront", "Route 53"
    ],
    "ai_ml": [
        "TensorFlow", "PyTorch", "Keras", "scikit-learn", "XGBoost",
        "LLM", "OpenAI", "Claude", "Hugging Face", "transformer",
        "RAG", "vector database", "embeddings", "prompt engineering",
        "fine-tuning", "RLHF", "multimodal", "agent"
    ],
    "databases": [
        "PostgreSQL", "MySQL", "MongoDB", "Redis", "Cassandra",
        "DynamoDB", "Elasticsearch", "Oracle", "SQL Server", "SQLite",
        "MariaDB", "Neo4j", "Weaviate", "Pinecone", "Supabase"
    ],
    "devops_tools": [
        "Docker", "Kubernetes", "Terraform", "Ansible", "Jenkins",
        "GitLab CI", "GitHub Actions", "CircleCI", "Travis CI",
        "Prometheus", "Grafana", "ELK", "DataDog", "New Relic"
    ],
    "frameworks": [
        "React", "Vue", "Angular", "Django", "FastAPI", "Flask",
        "Spring", "Node.js", "Express", "Next.js", "Nuxt",
        "NestJS", "GraphQL", "REST", "gRPC"
    ],
    "version_control": [
        "Git", "GitHub", "GitLab", "Bitbucket", "SVN", "Mercurial"
    ],
    "soft_skills": [
        "leadership", "communication", "teamwork", "problem-solving",
        "project management", "agile", "scrum", "mentoring",
        "negotiation", "presentation", "cross-functional"
    ]
}

# Strong action verbs for resume
STRONG_ACTION_VERBS = {
    "leadership": ["led", "managed", "directed", "supervised", "oversaw", "orchestrated"],
    "creation": ["designed", "built", "developed", "created", "architected", "engineered"],
    "improvement": ["optimized", "improved", "enhanced", "refined", "accelerated", "streamlined"],
    "implementation": ["implemented", "deployed", "executed", "launched", "established", "rolled out"],
    "problem_solving": ["resolved", "debugged", "diagnosed", "fixed", "troubleshot", "solved"],
    "increase": ["increased", "boosted", "scaled", "expanded", "grew", "amplified"],
    "decrease": ["reduced", "decreased", "minimized", "lowered", "cut", "eliminated"],
    "automation": ["automated", "scripted", "configured", "integrated", "orchestrated"],
}

WEAK_ACTION_VERBS = {
    "worked", "helped", "responsible for", "did", "made", "was",
    "participated", "involved", "used", "tried", "handled", "performed",
    "managed", "maintained"
}

# ATS platform compatibility scores adjustment
ATS_PLATFORM_ADJUSTMENTS = {
    "greenhouse": {
        "name": "Greenhouse",
        "strengths": ["parsing", "formatting", "structure"],
        "weaknesses": ["ai_readiness"],
        "base_score_adjustment": 1.0
    },
    "lever": {
        "name": "Lever",
        "strengths": ["keywords", "skills", "experience"],
        "weaknesses": ["formatting"],
        "base_score_adjustment": 1.0
    },
    "workday": {
        "name": "Workday",
        "strengths": ["structure", "contact"],
        "weaknesses": ["ai_readiness", "keywords"],
        "base_score_adjustment": 0.95
    },
    "taleo": {
        "name": "Oracle Taleo",
        "strengths": ["structure"],
        "weaknesses": ["formatting", "ai_readiness", "keywords"],
        "base_score_adjustment": 0.92
    },
    "icims": {
        "name": "iCIMS",
        "strengths": ["parsing", "structure", "contact"],
        "weaknesses": ["ai_readiness"],
        "base_score_adjustment": 0.98
    },
    "smartrecruiters": {
        "name": "SmartRecruiters",
        "strengths": ["keywords", "skills"],
        "weaknesses": [],
        "base_score_adjustment": 0.96
    }
}

# Role experience duration expectations
ROLE_EXPERIENCE_YEARS = {
    "junior": (0, 3),
    "mid": (3, 7),
    "senior": (7, 12),
    "staff": (12, 100)
}
