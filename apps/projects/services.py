import json
import logging
from django.db import transaction
from django.utils import timezone
from apps.projects.models import Project, ProjectVersion, ActivityLog
from apps.planner.models import ProjectPlan, PlanStep
from apps.planner.services.planner_service import PlannerService
from config.constants import PROJECT_STATUS_PLANNING, PROJECT_STATUS_ARCHIVED

logger = logging.getLogger('specpilot.ai')

class ProjectService:
    """
    Service Layer governing all software project workspace CRUD, versioning, rollbacks, and log events.
    """

    @staticmethod
    @transaction.atomic
    def create_project(user, title, description, short_description="", category="CUSTOM", 
                       target_users="", tech_stack="", architecture_type="MONOLITH", 
                       deployment_preference="Docker / VPS"):
        """
        Creates a project, triggers planning stages initialization, logs activity, and saves Version 1 snapshot.
        """
        logger.info(f"Creating project '{title}' for user: {user.username}")
        
        # 1. Create project
        project = Project.objects.create(
            user=user,
            title=title,
            short_description=short_description,
            description=description,
            category=category,
            target_users=target_users,
            tech_stack=tech_stack,
            target_architecture=architecture_type,
            deployment_preference=deployment_preference,
            status=PROJECT_STATUS_PLANNING
        )

        # 2. Initialize the 15-step workflow
        PlannerService.initialize_plan(project)

        # 3. Create active workspace session memory logs if not present
        from apps.memory.services.memory_service import MemoryService
        MemoryService.save_memory(
            project=project,
            role="USER",
            content=f"Initial Scope Description: {description}",
            importance_score=0.9
        )

        # 4. Log creation activity
        ActivityLog.objects.create(
            project=project,
            action_type="CREATED",
            description=f"Project workspace initialized with template style '{category}'.",
            user=user
        )

        # 5. Take Version 1 snapshot
        ProjectService.create_snapshot(project, user)

        return project

    @staticmethod
    @transaction.atomic
    def update_project(project_id, user, **kwargs):
        """
        Updates project attributes, increments current_version, logs activity, and takes a snapshot.
        """
        project = Project.objects.get(id=project_id, user=user)
        logger.info(f"Updating project '{project.title}' (current version: {project.current_version})")
        
        # List of fields that can be directly updated
        updatable_fields = [
            'title', 'short_description', 'description', 'category', 
            'target_users', 'tech_stack', 'target_architecture', 
            'deployment_preference', 'status'
        ]

        for field in updatable_fields:
            if field in kwargs:
                setattr(project, field, kwargs[field])
        
        # Increment version number
        project.current_version += 1
        project.save()

        # Log edit activity
        ActivityLog.objects.create(
            project=project,
            action_type="EDITED",
            description=f"Project details updated to Version {project.current_version}.",
            user=user
        )

        # Take a snapshot of the new version state
        ProjectService.create_snapshot(project, user)
        
        return project

    @staticmethod
    @transaction.atomic
    def duplicate_project(project_id, user):
        """
        Copies all project fields and duplicates its entire 15-step planning state.
        """
        source_project = Project.objects.get(id=project_id, user=user)
        logger.info(f"Duplicating project: {source_project.title}")

        # 1. Create duplicated project
        new_project = Project.objects.create(
            user=user,
            title=f"Copy of {source_project.title}",
            short_description=source_project.short_description,
            description=source_project.description,
            category=source_project.category,
            target_users=source_project.target_users,
            tech_stack=source_project.tech_stack,
            target_architecture=source_project.target_architecture,
            deployment_preference=source_project.deployment_preference,
            status=PROJECT_STATUS_PLANNING,
            current_version=1
        )

        # 2. Duplicate planning steps state
        source_plan = source_project.plan
        new_plan = ProjectPlan.objects.create(
            project=new_project,
            current_step_index=source_plan.current_step_index,
            overall_progress_pct=source_plan.overall_progress_pct
        )

        new_steps = []
        for step in source_plan.steps.all():
            new_steps.append(PlanStep(
                project_plan=new_plan,
                step_type=step.step_type,
                title=step.title,
                description=step.description,
                order=step.order,
                status=step.status,
                progress_pct=step.progress_pct,
                started_at=step.started_at,
                completed_at=step.completed_at,
                estimated_duration_minutes=step.estimated_duration_minutes,
                notes=step.notes,
                dependencies_str=step.dependencies_str,
                metadata=step.metadata.copy() if step.metadata else {}
            ))
        PlanStep.objects.bulk_create(new_steps)

        # 3. Duplicate any generated artifacts (optional but clean for complete cloning!)
        from apps.generator.models import GeneratedArtifact
        for art in source_project.artifacts.all():
            corresponding_step = new_plan.steps.filter(step_type=art.step.step_type).first() if art.step else None
            GeneratedArtifact.objects.create(
                project=new_project,
                step=corresponding_step,
                artifact_type=art.artifact_type,
                title=art.title,
                content=art.content,
                version=art.version
            )

        # 4. Log duplicate activity
        ActivityLog.objects.create(
            project=new_project,
            action_type="DUPLICATED",
            description=f"Duplicated from source project '{source_project.title}' (ID: {source_project.id}).",
            user=user
        )

        # 5. Create version 1 snapshot for the copy
        ProjectService.create_snapshot(new_project, user)

        return new_project

    @staticmethod
    def archive_project(project_id, user):
        """
        Sets status to Archived.
        """
        project = Project.objects.get(id=project_id, user=user)
        project.status = PROJECT_STATUS_ARCHIVED
        project.save()

        ActivityLog.objects.create(
            project=project,
            action_type="ARCHIVED",
            description="Project archived and locked from editing.",
            user=user
        )
        logger.info(f"Project '{project.title}' has been archived.")
        return project

    @staticmethod
    def unarchive_project(project_id, user):
        """
        Restores an archived project back to PLANNING status.
        """
        project = Project.objects.get(id=project_id, user=user)
        project.status = PROJECT_STATUS_PLANNING
        project.save()

        ActivityLog.objects.create(
            project=project,
            action_type="EDITED",
            description="Project unarchived and restored to planning status.",
            user=user
        )
        logger.info(f"Project '{project.title}' has been unarchived.")
        return project

    @staticmethod
    def delete_project(project_id, user):
        """
        Deletes project.
        """
        project = Project.objects.get(id=project_id, user=user)
        logger.info(f"Deleting project: {project.title}")
        project.delete()

    @staticmethod
    @transaction.atomic
    def restore_version(project_id, version_number, user):
        """
        Loads a snapshot JSON, restores project fields and plan steps state, and registers it as a new version.
        """
        project = Project.objects.get(id=project_id, user=user)
        version = ProjectVersion.objects.get(project=project, version_number=version_number)
        logger.info(f"Restoring project '{project.title}' to version {version_number}")

        snapshot = version.snapshot_data
        
        # 1. Restore Project details
        project.title = snapshot.get("title", project.title)
        project.short_description = snapshot.get("short_description", project.short_description)
        project.description = snapshot.get("description", project.description)
        project.category = snapshot.get("category", project.category)
        project.target_users = snapshot.get("target_users", project.target_users)
        project.tech_stack = snapshot.get("tech_stack", project.tech_stack)
        project.target_architecture = snapshot.get("target_architecture", project.target_architecture)
        project.deployment_preference = snapshot.get("deployment_preference", project.deployment_preference)
        project.status = snapshot.get("status", project.status)
        
        # Increment active version counter
        project.current_version += 1
        project.save()

        # 2. Restore steps
        plan = project.plan
        plan.current_step_index = snapshot.get("plan_current_step_index", 0)
        plan.overall_progress_pct = snapshot.get("plan_overall_progress_pct", 0.0)
        plan.save()

        # Overwrite all plan step parameters
        steps_data = {step_slug["step_type"]: step_slug for step_slug in snapshot.get("steps", [])}
        for step in plan.steps.all():
            if step.step_type in steps_data:
                data = steps_data[step.step_type]
                step.status = data.get("status", "PENDING")
                step.progress_pct = data.get("progress_pct", 0.0)
                step.notes = data.get("notes", "")
                step.metadata = data.get("metadata", {})
                step.save()

        # 3. Log restore event
        ActivityLog.objects.create(
            project=project,
            action_type="RESTORED",
            description=f"Restored workspace state back to Version {version_number} snapshot.",
            user=user
        )

        # 4. Take a new snapshot of the restored state
        ProjectService.create_snapshot(project, user)
        return project

    @staticmethod
    def create_snapshot(project, user):
        """
        Helper that compiles and serializes all project and workflow states into a ProjectVersion snapshot record.
        """
        plan = getattr(project, 'plan', None)
        steps_list = []
        if plan:
            for step in plan.steps.all():
                steps_list.append({
                    "step_type": step.step_type,
                    "title": step.title,
                    "description": step.description,
                    "order": step.order,
                    "status": step.status,
                    "progress_pct": float(step.progress_pct),
                    "notes": step.notes or "",
                    "dependencies_str": step.dependencies_str,
                    "metadata": step.metadata or {}
                })

        snapshot_data = {
            "title": project.title,
            "short_description": project.short_description,
            "description": project.description,
            "category": project.category,
            "target_users": project.target_users,
            "tech_stack": project.tech_stack,
            "target_architecture": project.target_architecture,
            "deployment_preference": project.deployment_preference,
            "status": project.status,
            "plan_current_step_index": plan.current_step_index if plan else 0,
            "plan_overall_progress_pct": float(plan.overall_progress_pct) if plan else 0.0,
            "steps": steps_list
        }

        # Check if version already exists to avoid integrity errors
        existing_version = ProjectVersion.objects.filter(project=project, version_number=project.current_version).first()
        if existing_version:
            existing_version.title = project.title
            existing_version.short_description = project.short_description
            existing_version.description = project.description
            existing_version.snapshot_data = snapshot_data
            existing_version.save()
            logger.info(f"Version snapshot {project.current_version} updated for Project '{project.title}'")
            return existing_version

        version_record = ProjectVersion.objects.create(
            project=project,
            version_number=project.current_version,
            title=project.title,
            short_description=project.short_description,
            description=project.description,
            snapshot_data=snapshot_data,
            created_by=user
        )
        logger.info(f"Version snapshot {project.current_version} created for Project '{project.title}'")
        return version_record


    @classmethod
    @transaction.atomic
    def seed_demo_projects(cls, user):
        """
        Seeds three pre-completed projects workspaces: Hospital Management, HRMS, and E-Commerce.
        Populates FSM timeline stages, realistic markdown artifacts, activity logs, and quality check reports.
        """
        logger.info(f"Seeding demo workspace projects for user: {user.username}")
        
        demos_config = [
            {
                "title": "Hospital Management System (HMS)",
                "category": "HOSPITAL",
                "short_description": "Integrated clinical portal managing patient scheduling, digital billing, and medical records.",
                "description": "An enterprise clinical suite facilitating real-time doctor appointments, doctor allocations, secure HIPAA-compliant electronic medical records (EMR) archiving, prescription tracking, and billing invoicing. Built for large multi-department hospital units.",
                "target_users": "Doctors, Patient Relations Officers, Clinical Pharmacists, and Billing Administrators.",
                "tech_stack": "Python 3.12, Django 5, PostgreSQL, Redis, React 18, and Bootstrap 5.",
                "architecture_type": "MICROSERVICES",
                "deployment_preference": "Kubernetes / AWS EKS",
            },
            {
                "title": "AI HRMS Platform",
                "category": "HRMS",
                "short_description": "Smart human resource workspace automating payroll, sentiment audits, and onboarding.",
                "description": "A cognitive human resources workspace automating employee onboarding checklist tasks, real-time leaves tracking, biometric payroll integrations, employee feedback audits, and predictive attrition risk metrics. Focuses on automation and employee engagement.",
                "target_users": "HR Business Partners, Recruiting Specialists, Compensation Officers, and general employees.",
                "tech_stack": "Python 3.12, Django 5, SQLite, Celery, Vue 3, and Tailwind CSS.",
                "architecture_type": "MONOLITH",
                "deployment_preference": "Docker Compose / GCP Cloud Run",
            },
            {
                "title": "Enterprise E-Commerce Engine",
                "category": "ECOMMERCE",
                "short_description": "Multi-tenant digital storefront supporting cart checkouts, stripe payouts, and warehouses.",
                "description": "A high-performance digital commerce platform featuring elastic multi-tenant store creations, Stripe payment gateway hooks, real-time inventory adjustments with warehouse notifications, recommendation engines, and customer analytics panels.",
                "target_users": "Online Shoppers, Store Managers, Warehouse Logistics Operators, and Sales Analysts.",
                "tech_stack": "Go, Python 3.12, Django REST Framework, Elasticsearch, Redis, Next.js, and Stripe.",
                "architecture_type": "EVENT_DRIVEN",
                "deployment_preference": "Serverless / AWS Lambda",
            }
        ]

        from apps.agents.models import Agent, AgentExecution
        from apps.generator.models import GeneratedArtifact
        from apps.evaluation.services.evaluation_service import EvaluationService
        
        agent = Agent.objects.filter(role='ARCHITECT', is_active=True).first()
        if not agent:
            agent = Agent.objects.create(
                name="Archimedes (Architect)",
                role="ARCHITECT",
                description="System architect agent.",
                system_prompt="Execute specialized coding workspace tasks."
            )

        for cfg in demos_config:
            if Project.objects.filter(user=user, title=cfg["title"]).exists():
                logger.info(f"Demo project '{cfg['title']}' already seeded for user. Skipping.")
                continue

            # 1. Create Project
            project = cls.create_project(
                user=user,
                title=cfg["title"],
                description=cfg["description"],
                short_description=cfg["short_description"],
                category=cfg["category"],
                target_users=cfg["target_users"],
                tech_stack=cfg["tech_stack"],
                architecture_type=cfg["architecture_type"],
                deployment_preference=cfg["deployment_preference"]
            )

            # 2. Add realistic markdown content for the stages
            plan = project.plan
            steps = plan.steps.all().order_by('order')

            for step in steps:
                if step.step_type == "EXPORT_PREP":
                    continue  # Keep the final step pending so user can compile it

                # Seed realistic spec content based on stage type
                content = ""
                if step.step_type == "IDEA":
                    content = (
                        f"# Project Scope Concept: {project.title}\n\n"
                        f"## Elevator Pitch\n{project.short_description}\n\n"
                        f"## Detailed Project Scope\n{project.description}\n\n"
                        f"## Target Architecture Model\n- **Target Pattern:** {project.get_target_architecture_display()}\n"
                        f"- **Deployment Target:** {project.deployment_preference}\n"
                    )
                elif step.step_type == "REQUIREMENTS":
                    content = (
                        f"# Core Requirements Analysis\n\n"
                        f"## 1. Functional Requirements Scope\n"
                        f"- **User Authentication:** Role-based access control (RBAC) ensuring security.\n"
                        f"- **Workspace Management:** Complete CRUD capabilities for workspace entities.\n"
                        f"- **Notifications Hub:** Real-time web sockets alert dispatchers.\n\n"
                        f"## 2. Non-Functional Specifications\n"
                        f"- **Performance:** Low latencies under 200ms for read operations.\n"
                        f"- **Security:** Encrypted credentials at rest and secure SSL/TLS communication HTTPS protocols.\n"
                        f"- **Scalability:** Stateless session architecture models."
                    )
                elif step.step_type == "PRD":
                    content = (
                        f"# Product Requirements Document (PRD)\n\n"
                        f"## 1. Project Background & Context\n"
                        f"The objective is to establish an automated digital platform that simplifies operations.\n\n"
                        f"## 2. User Personas & Flows\n"
                        f"- **Developer Persona:** Onboards easily via detailed API guides and code schemas.\n"
                        f"- **Administrator Persona:** Manages credentials overrides and safety parameters.\n\n"
                        f"## 3. Product Deliverables & Release Plan\n"
                        f"- **Sprint 1:** Database schema structures and migrations.\n"
                        f"- **Sprint 2:** Core API CRUD and safety evaluations checks."
                    )
                elif step.step_type == "USER_STORIES":
                    content = (
                        f"# User Stories & Scenarios\n\n"
                        f"## 1. Authentication Flows\n"
                        f"- *As a developer*, I want to authenticate securely via tokens so that I can query APIs.\n\n"
                        f"## 2. Planning Milestones\n"
                        f"- *As a project manager*, I want to create custom templates (CRM, SaaS, HRMS) to bootstrap workspaces."
                    )
                elif step.step_type == "FUNCTIONAL_REQS":
                    content = (
                        f"# Functional Requirements Document\n\n"
                        f"## 1. User Interface Specifications\n"
                        f"- Responsive navigation sidebar with workspace bookmarks.\n"
                        f"- Glassmorphic dashboards widgets showing active token counts.\n\n"
                        f"## 2. Integration Features\n"
                        f"- Multi-format exporters (Markdown, JSON, PDF download files)."
                    )
                elif step.step_type == "NON_FUNCTIONAL_REQS":
                    content = (
                        f"# Non-Functional Requirements Document\n\n"
                        f"## 1. Reliability & Fault Tolerance\n"
                        f"- Automated retry mechanism (up to 3 attempts) for API failures.\n"
                        f"- Sentry monitoring integration logging warnings and errors.\n\n"
                        f"## 2. Security Compliance\n"
                        f"- Password hashing using PBKDF2 cryptography rules."
                    )
                elif step.step_type == "ARCHITECTURE":
                    content = (
                        f"# System Architecture Design\n\n"
                        f"## 1. Layers Diagram\n"
                        f"Clean architecture layers: Controller Views -> Business Service Layers -> Database Models.\n\n"
                        f"## 2. Data Flow\n"
                        f"Query request -> Django ORM -> SQLite/PostgreSQL Database -> JSON payload serialize response."
                    )
                elif step.step_type == "DATABASE_DESIGN":
                    content = (
                        f"# Database Schema Design\n\n"
                        f"## 1. Relational Entity Models\n"
                        f"```sql\n"
                        f"CREATE TABLE projects (\n"
                        f"    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
                        f"    title VARCHAR(100) NOT NULL,\n"
                        f"    status VARCHAR(20) DEFAULT 'PLANNING'\n"
                        f");\n"
                        f"```\n\n"
                        f"## 2. Index Optimization\n"
                        f"- Add index on `user_id` and `created_at` fields to speed up queries."
                    )
                elif step.step_type == "API_DESIGN":
                    content = (
                        f"# RESTful API Interface Specification\n\n"
                        f"## 1. Authentication Header\n"
                        f"`Authorization: Bearer <token_key>`\n\n"
                        f"## 2. Routes Registry\n"
                        f"- `GET /api/v1/projects/` -> Returns array of active workspace projects.\n"
                        f"- `POST /api/v1/projects/create/` -> Spawns new workspace config."
                    )
                elif step.step_type == "FOLDER_STRUCTURE":
                    content = (
                        f"# Codebase Folder Structure Layout\n\n"
                        f"```\n"
                        f"workspace_root/\n"
                        f"  config/\n"
                        f"    settings.py\n"
                        f"    urls.py\n"
                        f"  apps/\n"
                        f"    core/\n"
                        f"    projects/\n"
                        f"    planner/\n"
                        f"  static/\n"
                        f"    css/\n"
                        f"    js/\n"
                        f"```"
                    )
                elif step.step_type == "DEVELOPMENT_ROADMAP":
                    content = (
                        f"# Development Roadmap Milestones\n\n"
                        f"## Milestone 1: Local Setup & Schema (Week 1)\n"
                        f"- Initialize repo directories layout.\n"
                        f"- Apply standard database migrations.\n\n"
                        f"## Milestone 2: Core Platform Services (Week 2)\n"
                        f"- Build Service Classes following SOLID guidelines."
                    )
                elif step.step_type == "SECURITY_CHECKLIST":
                    content = (
                        f"# Security Compliance Checklist\n\n"
                        f"- [x] Force HTTPS communication ssl layers.\n"
                        f"- [x] Validate inputs against cross-site scripting (XSS).\n"
                        f"- [x] Store credentials encrypted."
                    )
                elif step.step_type == "TESTING_CHECKLIST":
                    content = (
                        f"# Testing & Quality Checklist\n\n"
                        f"## 1. Unit Tests (pytest)\n"
                        f"Write mock test cases to verify workspace validations.\n\n"
                        f"## 2. Integration Tests\n"
                        f"Validate end-to-end API payloads serializations."
                    )
                elif step.step_type == "DEPLOYMENT_PLAN":
                    content = (
                        f"# Deployment & DevOps Execution Strategy\n\n"
                        f"## 1. Docker Environment\n"
                        f"Utilize multi-stage Dockerfiles to minimize build footprints.\n\n"
                        f"## 2. CI/CD Pipeline\n"
                        f"Configure GitHub Actions to automate pytest runs and image pushes."
                    )

                # Save generated artifact
                artifact = GeneratedArtifact.objects.create(
                    project=project,
                    step=step,
                    artifact_type='MARKDOWN',
                    title=step.title,
                    content=content,
                    version=1,
                    is_approved=True
                )

                # Initialize mock run executions & evaluations
                execution = AgentExecution.objects.create(
                    agent=agent,
                    project=project,
                    status='SUCCEEDED',
                    input_tokens=150,
                    output_tokens=300,
                    execution_time_ms=850
                )
                
                # Perform quality evaluations
                EvaluationService.evaluate_artifact(execution, content, step.title)

                # Complete step status
                step.status = 'COMPLETED'
                step.progress_pct = 100.0
                step.completed_at = timezone.now()
                step.notes = "Demo workspace stage seeded successfully."
                step.save()

            # Initialize final step note
            last_step = steps.last()
            last_step.notes = "Ready to compile final export blueprint package."
            last_step.save()

            # Record final log event
            ActivityLog.objects.create(
                project=project,
                action_type="CREATED",
                description="Seeded completed demo workspace project specifications.",
                user=user
            )

            # Re-snapshot project state
            cls.create_snapshot(project, user)

            # Recalculate health stats
            from apps.planner.services.planner_service import PlannerService
            PlannerService.update_plan_progress(project.plan)

        logger.info(f"Demo workspaces seeding complete for user: {user.username}")

