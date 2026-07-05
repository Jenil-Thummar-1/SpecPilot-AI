# SpecPilot AI
> **AI Project Architect & Software Planning Agent**

SpecPilot AI is an enterprise-grade AI-powered Project Architect Agent that transforms simple software ideas into complete, production-ready project blueprints. Rather than behaving as a simple chat interface, it implements a highly structured 14-phase software architecture design and development planning pipeline.

---

## 🛠️ Technology Stack & Architecture

- **Backend**: Python 3.12+ & Django 5.x
- **Frontend**: HTML5, Vanilla JavaScript, CSS3 variables, and Bootstrap 5 (incorporating custom Material-inspired styling, theme selectors, and glassmorphic panels)
- **AI Engine**: Google Gemini API Integration Layer
- **Architecture Style**: Clean Architecture with a decoupled Service Layer to isolate business logic from model entities and views.

---

## 📂 Modular Django Apps

1. **`core`**: Contains base class mixins, prompt sanitizers, and the `GeminiService` client.
2. **`accounts`**: Custom authentication user schema and workspace profiles.
3. **`dashboard`**: Aggregates workspace KPIs, active agent states, memory footprint, and compile outputs.
4. **`projects`**: Project details, idea scopes, and target architecture styles.
5. **`planner`**: A 14-step planning finite state machine.
6. **`agents`**: Specialization parameters (Architect, Planner, QA, Writer) and system directive setups.
7. **`skills`**: Programs capability specifications (SQL tables layout, REST route mapping).
8. **`memory`**: Context managers handling short/long term logs and window limit summaries.
9. **`generator`**: Outputs files repository (Markdown, JSON schemas).
9. **`evaluation`**: automated parsing guards scoring formatting checks and compliance.
10. **`exports`**: Package builders converting blueprints into unified Markdown, PDF, or JSON.

---

## 🚀 Getting Started

### 1. Requirements
Ensure Python 3.12+ is installed on your local host machine.

### 2. Setup Virtual Environment & Install Dependencies
```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows Powershell)
.venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

### 3. Setup Configuration
A default `.env` file has been configured for local development. For production usage, update credentials inside:
- `.env`

### 4. Running Migrations & Startup
```bash
# Run database migrations
python manage.py migrate

# Launch the development server
python manage.py runserver
```
Visit http://127.0.0.1:8000/ to access the application.

---

## 🔑 Administrative Access
A default superuser account has been initialized for workspace configuration:
- **Username**: `admin`
- **Password**: `adminpassword123`
- **Email**: `admin@specpilot.ai`

Admin URL: http://127.0.0.1:8000/admin/

---

## 🔄 The 14-Step Planning Lifecycle

Every software project moves through these structured planning steps:
1. **Project Idea**: Concept overview.
2. **Requirements**: Feature list boundaries and integrations.
3. **PRD**: Product Requirements Document detailing prioritization and release criteria.
4. **User Stories**: Actions statements with acceptance criteria.
5. **Functional Requirements**: System actions mapping.
6. **Non-Functional Requirements**: Speeds, limits, availability, and safety rules.
7. **Architecture**: Technology recommendations, patterns, and diagrams.
8. **Database Design**: Model tables schemas, keys, constraints, and indexes.
9. **API Design**: Routes paths, headers, and request/response payloads.
10. **Folder Structure**: Directory structures tree layout.
11. **Development Roadmap**: Milestone sprints and task schedulers.
12. **Security Checklist**: Access policies and vulnerability protection guards.
13. **Testing Checklist**: QA strategies, API mocks, and E2E cases.
14. **Deployment Plan**: CI/CD pipelines, container orchestration, and configs.
