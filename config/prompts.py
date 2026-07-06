"""
Centralized Prompt Library for SpecPilot AI.
Houses all system templates, instructions, and schemas for each lifecycle stage.
Updated to support enterprise-grade reasoning, long-term consistency, and collapsible thought processes.
"""

# Common thought process and formatting directives
THOUGHT_PROCESS_DIRECTIVE = """
You MUST start your response with a collapsible thought process block containing your domain reasoning:
<details>
<summary>🧠 AI Orchestrator Thought Process & Reasoning</summary>
Perform a rigorous, step-by-step analysis of:
1. Business Domain & Objectives
2. Tech Stack suitability & Scalability implications
3. Security, compliance, and regulatory considerations
4. Key architectural decisions and trade-offs
5. Dependencies on previously approved specifications
6. Technical risks and mitigation strategies
</details>

After the closing </details> tag, output the complete, professional, enterprise-grade specification document in clean Markdown.
NEVER generate placeholders, "TODO" notes, or generic chatbot filler. Every single section must be fully written, detailed, and ready for client delivery.
"""

# =====================================================================
# SYSTEM PROMPTS (Used as system instructions for the LLM)
# =====================================================================

SYSTEM_PROMPT_REQUIREMENTS = f"""You are a Principal Enterprise Solutions Architect with 15+ years of experience.
Your objective is to compile a comprehensive, implementation-ready Core Requirements specification document.
{THOUGHT_PROCESS_DIRECTIVE}
"""

SYSTEM_PROMPT_PRD = f"""You are a Lead Product Manager and Business Analyst.
Your objective is to translate the Core Requirements into a comprehensive Product Requirements Document (PRD) detailing user personas, prioritizations, and success KPIs.
{THOUGHT_PROCESS_DIRECTIVE}
"""

SYSTEM_PROMPT_USER_STORIES = f"""You are an Agile Product Owner and User Experience Architect.
Your objective is to write structured, action-oriented User Stories complete with detailed Given/When/Then acceptance criteria.
{THOUGHT_PROCESS_DIRECTIVE}
"""

SYSTEM_PROMPT_FUNCTIONAL_REQS = f"""You are a Senior Technical Writer and Software Architect.
Your objective is to translate user stories into system-level, testable Functional Requirements with inputs, outputs, validation constraints, and error behaviors.
{THOUGHT_PROCESS_DIRECTIVE}
"""

SYSTEM_PROMPT_NON_FUNCTIONAL_REQS = f"""You are a Systems and Infrastructure Architect.
Your objective is to define the Non-Functional Requirements (NFR) spanning performance SLAs, scalability, security, availability, and regulatory compliance.
{THOUGHT_PROCESS_DIRECTIVE}
"""

SYSTEM_PROMPT_ARCHITECTURE = f"""You are a Principal Software Architect.
Your objective is to design a robust, production-grade System Architecture Blueprint mapping components, service layers, and data flows.
{THOUGHT_PROCESS_DIRECTIVE}
"""

SYSTEM_PROMPT_DATABASE_DESIGN = f"""You are a Database Architect and Administrator.
Your objective is to design a detailed relational/non-relational database layout, schema tables, keys, indexing strategies, and migration scripts.
{THOUGHT_PROCESS_DIRECTIVE}
"""

SYSTEM_PROMPT_API_DESIGN = f"""You are a Senior API Engineer.
Your objective is to plan and document a complete, secure API Interface design, including endpoint tables, request/response payloads, and error codes.
{THOUGHT_PROCESS_DIRECTIVE}
"""

SYSTEM_PROMPT_FOLDER_STRUCTURE = f"""You are a Lead Software Developer.
Your objective is to design a modular, production-ready codebase directory tree structure aligned with modern development best practices.
{THOUGHT_PROCESS_DIRECTIVE}
"""

SYSTEM_PROMPT_DEVELOPMENT_ROADMAP = f"""You are a Senior Agile Scrum Master and Project Manager.
Your objective is to schedule a multi-phase, sprint-based agile Development Roadmap tracking tasks, dependencies, story points, and risks.
{THOUGHT_PROCESS_DIRECTIVE}
"""

SYSTEM_PROMPT_SECURITY_CHECKLIST = f"""You are an Enterprise Security Architect and OWASP Lead.
Your objective is to compile a secure-by-design checklist detailing authentication mechanisms, CORS, data encryption, and injection mitigations.
{THOUGHT_PROCESS_DIRECTIVE}
"""

SYSTEM_PROMPT_TESTING_CHECKLIST = f"""You are a QA Lead and SDET.
Your objective is to design a comprehensive Quality Assurance plan detailing test levels (unit, integration, E2E), specific cases, and CI/CD configurations.
{THOUGHT_PROCESS_DIRECTIVE}
"""

SYSTEM_PROMPT_DEPLOYMENT_PLAN = f"""You are a Lead DevOps and SRE Engineer.
Your objective is to compile a Production Deployment and Monitoring plan, specifying containers, CI/CD pipeline steps, environment config, and SLA alerting.
{THOUGHT_PROCESS_DIRECTIVE}
"""


# =====================================================================
# USER PROMPTS (Instructions sent to prompt builder)
# =====================================================================

# 1. Core Requirements Prompt
REQUIREMENTS_PROMPT = """
Analyze the following user software idea and output a comprehensive Core Requirements document in clean Markdown.

User Project Idea:
"{idea}"

Target Architecture Style:
"{architecture}"

Your Core Requirements document MUST include:
1. Executive Summary & Project Scope (Business objectives, vision, and core value proposition)
2. Target Audience & Stakeholders (Persona list, user roles, system administrators, third-party consumers)
3. Core Functional Features (Fully detailed and structured by domain category, with description)
4. Integration Requirements (Authentication systems, payment processors, external APIs, and dependencies)
5. Out of Scope Features (Explicitly listing excluded items to prevent scope creep, with justifications)
6. Business Rules & Validation Constraints (Workflow validations, system states, boundaries)
7. Core Success Metrics & Performance KPIs (Key markers to evaluate project success)
"""

# 2. PRD Prompt
PRD_PROMPT = """
Generate a comprehensive Product Requirements Document (PRD) for the project based on the Core Requirements.

Core Requirements Document:
{context_doc}

Your PRD MUST include:
1. Document Control & Executive Summary
2. User Personas & Roles (Detailed personas with technical proficiency, objectives, frustrations)
3. Detailed Product Features list (Grouped by module, with priority levels: High, Medium, Low, technical complexity rating, and descriptions)
4. User Flow & Screen-by-Screen Outline (Step-by-step navigation flows, required input/output forms)
5. Success Metrics & Key Performance Indicators (KPIs)
6. Technical Assumptions, System Constraints, and Risk Analysis (with mitigation plan)
"""

# 3. User Stories Prompt
USER_STORIES_PROMPT = """
Write detailed, action-oriented User Stories based on the following Product Requirements Document.

Product Requirements Document (PRD):
{context_doc}

Your document MUST include:
- A logical Epic breakdown of the system.
- Standard format for each story:
  * **ID**: US-XX
  * **Title**: Short descriptive title
  * **Story**: "As a [User Role], I want to [Perform Action], so that [Business Value]"
  * **Acceptance Criteria**: Detailed bulleted checklist in Given-When-Then format covering normal flows, edge cases, and validation rules.
  * **Story Point Estimate & Complexity**: Logical estimation (e.g., Fibonacci)
"""

# 4. Functional Requirements Prompt
FUNCTIONAL_PROMPT = """
Translate the User Stories and PRD into formal, system-level Functional Requirements.

Product Scope Context:
{context_doc}

Your document MUST include a complete matrix of:
1. User Management & Authentication (FR-AUTH-01...)
2. Core Business Workflows & Data CRUD Management (FR-CORE-01...)
3. Internal & External API Interactions (FR-API-01...)
4. Background Tasking & Job Scheduling (FR-JOB-01...)
5. UI & View Layer States (FR-UI-01...)

For each requirement, specify:
- Requirement ID & Title
- Description of the system response
- Input data parameters & validation checks
- Output response/result & target state
- Alternative flows / error paths
"""

# 5. Non-Functional Requirements Prompt
NON_FUNCTIONAL_PROMPT = """
Define the Non-Functional Requirements (NFR) for this project based on the prior scope.

System Context:
{context_doc}

Your document MUST contain detailed specifications for:
1. Performance & Latency Requirements (API response times, page load limits under load, database query SLA)
2. Scalability & Availability Targets (Concurrent user support, horizontal auto-scaling triggers, SLA uptime target)
3. Reliability & Fault Tolerance (Disaster Recovery RPO/RTO targets, backup schedules, failover mechanisms)
4. Security & Compliance Controls (Data encryption at rest/in transit, regulatory compliance like GDPR/HIPAA/SOC2, CORS policies)
5. Localization, Accessibility (WCAG 2.1 AA standards), and Browser Compatibility matrix
"""

# 6. Architecture Design Prompt
ARCHITECTURE_PROMPT = """
Design a production-grade software architecture blueprint for this application.

System Requirements Context:
{context_doc}

Your blueprint MUST contain:
1. System Architecture Pattern Overview (Clean architecture, MVC, Microservices, or Event-Driven details)
2. Component Breakdown & Layered Boundaries (Controller, Service, Repository, entity relationships, logical separation)
3. Production Tech Stack Recommendations (Detailed languages, frameworks, database types, message brokers, caching strategies)
4. Design Patterns & Architectural Best Practices (Singleton, Dependency Injection, Repository pattern, CQRS, etc.)
5. Data Flow Diagram Representation (Represented in clear Mermaid.js syntax)
"""

# 7. Database Design Prompt
DATABASE_PROMPT = """
Design the logical database schema layout for this project.

System Architecture Context:
{context_doc}

Your Database Design document MUST contain:
1. Relational Entity-Relationship Diagram (using valid Mermaid.js syntax)
2. Detailed Table Schemas (For every table, define field names, data types, keys (PK/FK), default values, constraints, and field descriptions in markdown tables)
3. Indexing & Optimization Strategy (Primary and composite indexing recommendations for performance tuning)
4. Data Integrity, Archival, and Migration Strategy (Soft delete conventions, history auditing, database migration plan)
"""

# 8. API Design Prompt
API_PROMPT = """
Plan and document the complete API interface design.

System Context:
{context_doc}

Your API Design document MUST contain:
1. API Standards & Security Protocol (RESTful/GraphQL rules, Bearer token OAuth2 auth flow, JSON formatting standards)
2. Route Definitions Table (Markdown table listing: Method, Path, Auth Required, Request Parameters, Response Code, Description)
3. Complete Request/Response JSON Payloads for the top 5 critical system endpoints
4. Rate Limiting, Error Codes, and Standardized Error Response schema
"""

# 9. Codebase Folder Structure Prompt
FOLDER_STRUCTURE_PROMPT = """
Generate a modular, production-ready codebase directory tree structure.

Tech Stack & Scope Context:
{context_doc}

Your document MUST contain:
1. Complete Directory Tree Layout (In a text code block representation, outlining controllers, models, config, tests, and assets)
2. Detailed folder-by-folder explanation and module structure
3. Configuration, environment variables (.env.example template) setup guidelines
4. App module compilation, entry points, and deployment-ready file paths
"""

# 10. Development Roadmap Prompt
ROADMAP_PROMPT = """
Create an agile, step-by-step Development Roadmap.

Scope and Requirements Context:
{context_doc}

Your Development Roadmap MUST contain:
1. Phase Breakdown & Project Milestones (MVP Setup, Beta Phase, Production Launch milestones)
2. Agile Sprint Schedule (Detailing sprint goals, user story allocation, estimated story points, and role assignments)
3. Task Dependency Matrix (Showing critical path sequences)
4. Engineering Risks, Critical Path Analysis, and Mitigation Strategies
"""

# 11. Security Checklist Prompt
SECURITY_PROMPT = """
Generate a comprehensive Security Checklist based on OWASP Top 10 guidelines.

Scope Context:
{context_doc}

Your Security Checklist MUST contain:
1. Authentication & Session Management (Hashing algorithms, session timeouts, token rotation policies, RBAC roles matrix)
2. Data Privacy & Transport Protections (HTTPS config, secure cookie policies, CORS parameters, data masking)
3. Input Validation & Injection Prevention (SQL injection, XSS escaping, CSRF tokens configuration)
4. Audit Logging, Compliance Monitoring, and Intrusion Alerts checklist
"""

# 12. Testing Checklist Prompt
TESTING_PROMPT = """
Generate a comprehensive Testing Checklist and Quality Assurance Plan.

Scope Context:
{context_doc}

Your Testing Checklist MUST contain:
1. QA Strategy Overview (Target code coverage percentage, split between unit, integration, and E2E testing)
2. Unit Test Checklist (Core modules, validations, boundary conditions, mock objects setup)
3. Integration & API Test Plan (Status assertions, query params permutations, error payload test cases)
4. End-to-End User Flow Tests (Simulating complete signup, core workflow, data export pathways)
5. CI/CD automated test pipeline setup and test reporting configurations
"""

# 13. Deployment Plan Prompt
DEPLOYMENT_PROMPT = """
Create a detailed Production Deployment Plan.

System Scope Context:
{context_doc}

Your Production Deployment Plan MUST contain:
1. Host Infrastructure Requirements (Virtual server specs, containerization definitions, scaling rules)
2. CI/CD Pipeline Schema (Source control integration, build steps, test runs, zero-downtime rolling deployment stages)
3. Production Settings, Environment Configs, and Secret Manager configuration
4. Application Monitoring, Log Aggregation, Performance Tracing, and Alerting SLA policies
"""
