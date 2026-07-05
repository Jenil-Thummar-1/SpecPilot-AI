import logging
from django.utils import timezone
from apps.planner.models import ProjectPlan, PlanStep
from config.constants import (
    PLAN_STEP_CHOICES, STEP_STATUS_PENDING, STEP_STATUS_COMPLETED, STEP_STATUS_RUNNING, STEP_STATUS_FAILED,
    STEP_IDEA, STEP_REQUIREMENTS, STEP_PRD, STEP_USER_STORIES, STEP_FUNCTIONAL, STEP_NON_FUNCTIONAL,
    STEP_ARCHITECTURE, STEP_DATABASE, STEP_API, STEP_FOLDER_STRUCTURE, STEP_ROADMAP, STEP_SECURITY,
    STEP_TESTING, STEP_DEPLOYMENT
)

logger = logging.getLogger('specpilot.ai')

class PlannerService:
    """
    Manages the 14-phase software project planning lifecycle and state machine transition.
    """

    @staticmethod
    def initialize_plan(project):
        """
        Creates a ProjectPlan and populates it with the 14 default lifecycle steps.
        """
        plan, created = ProjectPlan.objects.get_or_create(project=project)
        if created:
            logger.info(f"Initialized plan for project '{project.title}'")
            
            # 14 distinct lifecycle stages
            stages = [
                (STEP_IDEA, "Project Idea", "Initial software project concept overview."),
                (STEP_REQUIREMENTS, "Core Requirements", "Scope boundaries, integrations, features."),
                (STEP_PRD, "Product Requirements Document (PRD)", "Value propositions, features list, priorities, release criteria."),
                (STEP_USER_STORIES, "User Stories", "User workflows and Gherkin scenario parameters."),
                (STEP_FUNCTIONAL, "Functional Requirements", "Formal system actions list."),
                (STEP_NON_FUNCTIONAL, "Non-Functional Requirements", "Speed, load limits, SLA availability, compliance controls."),
                (STEP_ARCHITECTURE, "System Architecture Design", "Design patterns, layout style, components, data flow logic."),
                (STEP_DATABASE, "Database Design", "Relational models layout, keys, field schemas, indexing planning."),
                (STEP_API, "API Interface Design", "Endpoint paths, params schemas, HTTP actions, response samples."),
                (STEP_FOLDER_STRUCTURE, "Codebase Folder Structure", "Source directories, configs, settings tree files."),
                (STEP_ROADMAP, "Development Roadmap", "Task sprints configuration, risk evaluations, agile timeline."),
                (STEP_SECURITY, "Security Checklist", "Access rules, transport privacy rules, injection protections."),
                (STEP_TESTING, "Testing Checklist", "Unit testing, integration testing, E2E checks framework."),
                (STEP_DEPLOYMENT, "Deployment Plan", "Infrastructure setup, Docker environments, CI/CD pipeline runs."),
            ]
            
            steps = []
            for idx, (step_type, title, desc) in enumerate(stages):
                steps.append(PlanStep(
                    project_plan=plan,
                    step_type=step_type,
                    title=title,
                    description=desc,
                    order=idx + 1,
                    status=STEP_STATUS_PENDING
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
        step.save()
        logger.info(f"Step '{step.title}' (Plan {step.project_plan.id}) started execution.")

    @staticmethod
    def complete_step(step):
        """
        Marks a step as completed and updates overall progress metrics.
        """
        step.status = STEP_STATUS_COMPLETED
        step.completed_at = timezone.now()
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
        logger.info(f"Step '{step.title}' completed. Project overall progress: {plan.overall_progress_pct}%")

    @staticmethod
    def fail_step(step):
        """
        Marks a step as failed.
        """
        step.status = STEP_STATUS_FAILED
        step.completed_at = timezone.now()
        step.save()
        logger.warning(f"Step '{step.title}' failed execution.")
