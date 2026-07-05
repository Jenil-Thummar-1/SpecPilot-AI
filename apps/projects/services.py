import json
import logging
from django.db import transaction
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
        plan = project.plan
        steps_list = []
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
            "plan_current_step_index": plan.current_step_index,
            "plan_overall_progress_pct": float(plan.overall_progress_pct),
            "steps": steps_list
        }

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
