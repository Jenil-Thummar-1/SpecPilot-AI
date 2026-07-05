import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
import config.prompts as prompts_library
from apps.projects.models import Project
from apps.agents.models import Agent, AgentExecution
from apps.skills.models import Skill, SkillExecution
from apps.memory.models import MemoryEntry
from apps.exports.models import ExportJob
from apps.generator.models import GeneratedArtifact
from config.constants import AGENT_STATUS_IDLE, AGENT_ROLE_ARCHITECT, AGENT_ROLE_PLANNER, AGENT_ROLE_WRITER, AGENT_ROLE_QA

logger = logging.getLogger('specpilot.ai')

def landing_view(request):
    """
    Renders the SpecPilot AI premium landing page.
    """
    return render(request, 'landing.html')

@login_required
def dashboard_view(request):
    """
    Aggregates metrics and states to drive the Material Glassmorphism dashboard panel.
    """
    user = request.user
    logger.info(f"Dashboard loaded for user: {user.username}")

    # Ensure default agents exist so the dashboard has active AI Agent cards to show
    if not Agent.objects.exists():
        logger.info("Initializing default agent records...")
        Agent.objects.create(
            name="Alpha Architect",
            role=AGENT_ROLE_ARCHITECT,
            description="Designs system architectures, component hierarchies, and database entity models.",
            system_prompt="You are a senior system architect designing scalable application patterns.",
            status=AGENT_STATUS_IDLE
        )
        Agent.objects.create(
            name="Beta Planner",
            role=AGENT_ROLE_PLANNER,
            description="Breaks requirements down into development milestones and sprints.",
            system_prompt="You are an agile software planner scheduling stories and roadmaps.",
            status=AGENT_STATUS_IDLE
        )
        Agent.objects.create(
            name="Gamma QA",
            role=AGENT_ROLE_QA,
            description="Validates schemas and generates test scripts and integration suites.",
            system_prompt="You are a QA specialist planning unit, API, and verification checkpoints.",
            status=AGENT_STATUS_IDLE
        )
        
    # Ensure default skills exist
    if not Skill.objects.exists():
        logger.info("Initializing default skill records...")
        Skill.objects.create(
            name="SQL Database Schema Planning",
            code_identifier="generate_db_schema",
            description="Outputs relational schemas, constraints, keys, and optimizations."
        )
        Skill.objects.create(
            name="RESTful API Definition",
            code_identifier="generate_api_spec",
            description="Generates standard REST routes schemas and payload formats."
        )

    # Core aggregates
    recent_projects = Project.objects.filter(user=user).order_by('-updated_at')[:5]
    agents = Agent.objects.filter(is_active=True)
    skills = Skill.objects.all()
    
    # Execution history count
    executions_count = AgentExecution.objects.filter(project__user=user).count()
    
    # Generated blueprints count
    artifacts_count = GeneratedArtifact.objects.filter(project__user=user).count()
    
    # Short/Long term memory count
    memory_count = MemoryEntry.objects.filter(session__conversation__project__user=user).count()
    
    # Recent exports
    exports = ExportJob.objects.filter(project__user=user).order_by('-created_at')[:5]

    # Advanced Enterprise Analytics Calculations
    from django.db.models import Sum, Avg
    token_stats = AgentExecution.objects.filter(project__user=user).aggregate(
        total_input=Sum('input_tokens'),
        total_output=Sum('output_tokens'),
        avg_latency=Avg('execution_time_ms')
    )
    total_input = token_stats.get('total_input') or 0
    total_output = token_stats.get('total_output') or 0
    avg_latency = token_stats.get('avg_latency') or 0

    succeeded_execs = AgentExecution.objects.filter(project__user=user, status='SUCCEEDED').count()
    success_rate = (succeeded_execs / executions_count * 100) if executions_count > 0 else 100

    from apps.evaluation.models import QualityScore
    avg_quality = QualityScore.objects.filter(
        evaluation__agent_execution__project__user=user,
        metric_name='OVERALL_CONFIDENCE'
    ).aggregate(avg_score=Avg('score'))['avg_score'] or 0

    # Skills utilization count
    from apps.skills.models import SkillExecution
    skills_utilized = SkillExecution.objects.filter(agent_execution__project__user=user).count()

    analytics = {
        'total_input_tokens': total_input,
        'total_output_tokens': total_output,
        'total_tokens': total_input + total_output,
        'avg_latency_ms': int(avg_latency),
        'success_rate': round(success_rate, 1),
        'avg_quality_score': round(avg_quality, 1),
        'skills_utilized': skills_utilized,
        'total_projects': Project.objects.filter(user=user).count()
    }

    context = {
        'recent_projects': recent_projects,
        'agents': agents,
        'skills': skills,
        'executions_count': executions_count,
        'artifacts_count': artifacts_count,
        'memory_count': memory_count,
        'exports': exports,
        'analytics': analytics,
    }
    
    return render(request, 'dashboard/index.html', context)

class PromptLibraryView(LoginRequiredMixin, TemplateView):
    """
    Exposes reusable system prompt templates catalog.
    """
    template_name = 'dashboard/prompts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pull prompt template strings
        context['prompts'] = {
            'Requirements Analysis': prompts_library.REQUIREMENTS_PROMPT,
            'PRD Generation': prompts_library.PRD_PROMPT,
            'User Stories': prompts_library.USER_STORIES_PROMPT,
            'Functional Requirements': prompts_library.FUNCTIONAL_PROMPT,
            'Non-Functional Requirements': prompts_library.NON_FUNCTIONAL_PROMPT,
            'Architecture Design': prompts_library.ARCHITECTURE_PROMPT,
            'Database Design': prompts_library.DATABASE_PROMPT,
            'API Interface Planning': prompts_library.API_PROMPT,
            'Folder Structure Layout': prompts_library.FOLDER_STRUCTURE_PROMPT,
            'Development Roadmap': prompts_library.ROADMAP_PROMPT,
            'Security Checklist': prompts_library.SECURITY_PROMPT,
            'Testing Checklist': prompts_library.TESTING_PROMPT,
            'Deployment Planning': prompts_library.DEPLOYMENT_PROMPT,
        }
        return context
