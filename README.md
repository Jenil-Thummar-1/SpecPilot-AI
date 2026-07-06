# SpecPilot AI
> **Enterprise-Grade AI Project Architect & Software Planning Platform**

SpecPilot AI is a production-ready Autonomous AI Project Architect Platform designed to transform raw software ideas into complete, production-ready project blueprints, technical designs, database schemas, and deployment plans. Rather than behaving as a simple chat interface, it implements a highly structured, state-locked 15-phase software design and planning pipeline.

---

## 🛠️ Technology Stack & Architecture

- **Backend Framework**: Python 3.12+ & Django 5.x
- **Frontend Architecture**: HTML5, Vanilla JavaScript, CSS3 custom variables, and Bootstrap 5 (styled with a premium glassmorphic, dark-mode design language)
- **AI Orchestration**: Google Gemini API client integration layer (`GeminiService`) with mock failover safety support
- **Design Pattern**: Clean Architecture with decoupled business logic Service Layers (`ProjectService`, `PlannerService`, `MemoryService`, `ExportService`, `EvaluationService`)

---

## 📂 Project Structure & Directories Layout

```
SpecPilot AI/
│
├── apps/
│   ├── core/         # Shared helpers, prompt builders, and Gemini client wrappers
│   ├── accounts/     # Custom user profiles, theme states, and custom API key overrides
│   ├── dashboard/    # Analytics panels, KPI widgets, and static pages
│   ├── projects/     # Project workspaces details, CRUD operations, and revisions seeder
│   ├── planner/      # 15-step Finite State Machine (FSM) workflow engine
│   ├── agents/       # AI Role models (Architect, Planner, QA, Writer) & orchestrator
│   ├── skills/       # Custom skillsets (RESTful definitions, DB schemas layout)
│   ├── memory/       # Context workspace memory logs (Short/Long term banks)
│   ├── generator/    # Outputs files repository (Markdown, JSON specifications)
│   ├── evaluation/   # Automated 10-metric compliance QA checks
│   └── exports/      # Output packaging engine (Markdown, PDF, JSON, ZIP bundles)
│
├── static/           # Stylesheets, micro-animations, and scripts
├── templates/        # Django HTML templates (Glassmorphic dashboard portal)
├── config/           # URL mapping routes and global Django project configuration
├── db.sqlite3        # Local SQLite database
├── manage.py         # Django execution manager
└── requirements.txt  # Dependencies list
```

---

## 🚀 Getting Started & Installation Guide

### 1. Prerequisite Installations
Ensure Python 3.12+ is installed on your local host system.

### 2. Setup Virtual Environment & Install Packages
```bash
# Create local virtual environment
python -m venv .venv

# Activate Virtual Environment (Windows Powershell)
.venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

### 3. Setup Configuration
Ensure your root environment file is configured:
Create or edit the `.env` file in the root workspace and add your credentials:
```env
SECRET_KEY=django-insecure-development-key
DEBUG=True
GEMINI_API_KEY=your-google-gemini-studio-api-key-here
```
*Note: If `GEMINI_API_KEY` is not provided, the platform automatically runs in Mock Fallback Mode using mock specifications templates.*

### 4. Database Migrations & Seeding
```bash
# Apply database schemas migrations
python manage.py migrate

# Seed baseline AI Agents, skills, and admin credentials
python manage.py runserver
```

---

## 🔑 Default Credentials & Access Logins
A default administrator account is pre-configured:
- **Username**: `admin`
- **Password**: `adminpassword123`
- **Email**: `admin@specpilot.ai`

Admin Dashboard access: http://127.0.0.1:8000/admin/

---

## 🌟 Demo Mode: Seeding Completed Workspaces
To explore the platform instantly without manual data entry:
1. Log in using the admin credentials above.
2. If no projects are loaded, a banner will appear: **"Explore SpecPilot AI instantly! Initialize Demo Workspaces"**.
3. Click the button to automatically seed:
   - **Hospital Management System (HMS)**
   - **AI HRMS Platform**
   - **Enterprise E-Commerce Engine**
4. All 15 planning stages will be generated with realistic specifications, quality ratings, activity timelines, and exports.

---

## 🔄 The 15-Stage Planning Lifecycle
Every software project progresses through this structured sequence:
1. **Project Idea**: Elevator pitch and category assignment.
2. **Core Requirements**: Functional boundaries.
3. **PRD**: Product Requirements Document (PRD).
4. **User Stories**: Functional stories with user persona guides.
5. **Functional Requirements**: Clear system actions list.
6. **Non-Functional Requirements**: Technical thresholds (latency, uptime).
7. **System Architecture Design**: System patterns, layers, and flows.
8. **Database Design**: Schema models, tables, indexes, and keys.
9. **API Design**: HTTP routes, payloads, and parameter definitions.
10. **Codebase Folder Structure**: File structures structure layouts.
11. **Development Roadmap**: Milestones sprints schedules.
12. **Security Checklist**: Safety guards and encryption checkers.
13. **Testing Checklist**: QA unit test cases and mock plans.
14. **Deployment Plan**: CI/CD pipelines and Docker containers.
15. **Export Preparation**: Output compilation packaging.
