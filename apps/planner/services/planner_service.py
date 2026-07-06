import logging
from django.utils import timezone
from apps.planner.models import ProjectPlan, PlanStep
from apps.projects.models import ActivityLog
from config.constants import (
    STEP_STATUS_PENDING, STEP_STATUS_COMPLETED, STEP_STATUS_RUNNING, STEP_STATUS_FAILED,
    STEP_STATUS_NEEDS_REVISION,
    STEP_IDEA, STEP_REQUIREMENTS, STEP_PRD, STEP_USER_STORIES, STEP_FUNCTIONAL, STEP_NON_FUNCTIONAL,
    STEP_ARCHITECTURE, STEP_DATABASE, STEP_API, STEP_FOLDER_STRUCTURE, STEP_ROADMAP, STEP_SECURITY,
    STEP_TESTING, STEP_DEPLOYMENT, STEP_EXPORT_PREP
)

logger = logging.getLogger('specpilot.ai')

class PlannerService:
    """
    Manages the 15-phase software project planning lifecycle and state machine transition.
    """

    @staticmethod
    def initialize_plan(project):
        """
        Creates a ProjectPlan and populates it with the 15 default planning workflow steps.
        Includes estimated durations and logical step dependency structures.
        """
        plan, created = ProjectPlan.objects.get_or_create(project=project)
        if created:
            logger.info(f"Initializing 15-step plan for project '{project.title}'")
            
            # (Step Slug, Title, Description, Est Duration (min), Dependencies)
            stages = [
                (STEP_IDEA, "Project Idea", "Initial software project concept overview.", 5, ""),
                (STEP_REQUIREMENTS, "Core Requirements", "Scope boundaries, integrations, features.", 10, "1"),
                (STEP_PRD, "Product Requirements Document (PRD)", "Value propositions, features list, priorities, release criteria.", 20, "2"),
                (STEP_USER_STORIES, "User Stories", "User workflows and Gherkin scenario parameters.", 15, "3"),
                (STEP_FUNCTIONAL, "Functional Requirements", "Formal system actions list.", 15, "4"),
                (STEP_NON_FUNCTIONAL, "Non-Functional Requirements", "Speed, load limits, SLA availability, compliance controls.", 10, "3"),
                (STEP_ARCHITECTURE, "System Architecture Design", "Design patterns, layout style, components, data flow logic.", 25, "5,6"),
                (STEP_DATABASE, "Database Design", "Relational models layout, keys, field schemas, indexing planning.", 20, "7"),
                (STEP_API, "API Interface Design", "Endpoint paths, params schemas, HTTP actions, response samples.", 20, "7,8"),
                (STEP_FOLDER_STRUCTURE, "Codebase Folder Structure", "Source directories, configs, settings tree files.", 10, "7"),
                (STEP_ROADMAP, "Development Roadmap", "Task sprints configuration, risk evaluations, agile timeline.", 15, "3,4,7"),
                (STEP_SECURITY, "Security Checklist", "Access rules, transport privacy rules, injection protections.", 15, "6,7"),
                (STEP_TESTING, "Testing Checklist", "Unit testing, integration testing, E2E checks framework.", 15, "4,5,9"),
                (STEP_DEPLOYMENT, "Deployment Plan", "Infrastructure setup, Docker environments, CI/CD pipeline runs.", 15, "6,10"),
                (STEP_EXPORT_PREP, "Export Preparation", "Compiling documents, schemas, and packaging layouts.", 10, "1,2,3,4,5,6,7,8,9,10,11,12,13,14"),
            ]
            
            steps = []
            for idx, (step_type, title, desc, duration, deps) in enumerate(stages):
                steps.append(PlanStep(
                    project_plan=plan,
                    step_type=step_type,
                    title=title,
                    description=desc,
                    order=idx + 1,
                    status=STEP_STATUS_PENDING,
                    estimated_duration_minutes=duration,
                    dependencies_str=deps
                ))
            
            PlanStep.objects.bulk_create(steps)
            logger.info(f"Created {len(stages)} steps for plan {plan.id}")
            
        return plan

    @staticmethod
    def start_step(step):
        """
        Marks a plan step as running.
        """
        step.status = STEP_STATUS_RUNNING
        step.started_at = timezone.now()
        step.progress_pct = 20.0
        step.save()

        # Log active transition
        ActivityLog.objects.create(
            project=step.project_plan.project,
            action_type="STAGE_UPDATED",
            description=f"AI Agents initiated work on planning stage: {step.title}.",
        )
        logger.info(f"Step '{step.title}' (Plan {step.project_plan.id}) started execution.")

    @staticmethod
    def complete_step(step, notes="", metadata=None):
        """
        Marks a step as completed, stores notes, updates progress metrics and logs events.
        """
        step.status = STEP_STATUS_COMPLETED
        step.completed_at = timezone.now()
        step.progress_pct = 100.0
        if notes:
            step.notes = notes
        if metadata:
            step.metadata = metadata
        step.save()
        
        # Recalculate progress
        plan = step.project_plan
        total_steps = plan.steps.count()
        completed_steps = plan.steps.filter(status=STEP_STATUS_COMPLETED).count()
        
        if total_steps > 0:
            plan.overall_progress_pct = (completed_steps / total_steps) * 100
        else:
            plan.overall_progress_pct = 0.0
        plan.save()

        # Log completion event
        ActivityLog.objects.create(
            project=plan.project,
            action_type="STAGE_UPDATED",
            description=f"Planning stage '{step.title}' successfully completed.",
            metadata={"step_order": step.order, "progress_pct": float(plan.overall_progress_pct)}
        )
        logger.info(f"Step '{step.title}' completed. Project overall progress: {plan.overall_progress_pct}%")

    @staticmethod
    def fail_step(step, error_message=""):
        """
        Marks a step as needs revision (replaces the dead-end FAILED state).
        Delegates to needs_revision_step for consistent behaviour.
        """
        PlannerService.needs_revision_step(step, reason=error_message)

    @staticmethod
    def needs_revision_step(step, reason=""):
        """
        Marks a step as NEEDS_REVISION, allowing the user to edit or regenerate.
        This replaces the permanent FAILED dead-end state.
        """
        step.status = STEP_STATUS_NEEDS_REVISION
        step.progress_pct = 50.0  # Halfway — content exists but not approved
        if reason:
            step.notes = f"Revision required: {reason}"
        step.save()

        ActivityLog.objects.create(
            project=step.project_plan.project,
            action_type="STAGE_UPDATED",
            description=f"Planning stage '{step.title}' marked for revision: {reason}",
        )
        logger.info(f"Step '{step.title}' marked as NEEDS_REVISION.")

    @staticmethod
    def calculate_health(project):
        """
        Computes project health indicators:
        - Overall Progress (overall_progress_pct)
        - Workflow Completion (completed steps / total steps)
        - Estimated Remaining Work (sum of estimated durations for remaining steps)
        - Current Active Stage
        """
        plan = getattr(project, 'plan', None)
        if not plan:
            return {
                "overall_progress": 0.0,
                "workflow_completion": "0/15",
                "estimated_remaining_minutes": 0,
                "active_stage": "Not Started"
            }

        steps = plan.steps.all()
        total_count = steps.count()
        completed_count = steps.filter(status=STEP_STATUS_COMPLETED).count()
        
        # Active step is first pending/needs_revision/failed/running step
        active_step = steps.exclude(status=STEP_STATUS_COMPLETED).first()
        active_stage_title = active_step.title if active_step else "Fully Planned"

        # Remaining work: sum estimated minutes of non-completed steps
        remaining_minutes = sum(step.estimated_duration_minutes for step in steps.exclude(status=STEP_STATUS_COMPLETED))

        return {
            "overall_progress": float(plan.overall_progress_pct),
            "workflow_completion": f"{completed_count}/{total_count}",
            "estimated_remaining_minutes": remaining_minutes,
            "active_stage": active_stage_title
        }

    @staticmethod
    def update_plan_progress(plan):
        """
        Recalculates plan's overall progress percentage and updates the record.
        """
        total_steps = plan.steps.count()
        completed_steps = plan.steps.filter(status='COMPLETED').count()
        
        if total_steps > 0:
            plan.overall_progress_pct = (completed_steps / total_steps) * 100
        else:
            plan.overall_progress_pct = 0.0
        plan.save()
        logger.info(f"Plan progress recalculated: {plan.overall_progress_pct}%")

