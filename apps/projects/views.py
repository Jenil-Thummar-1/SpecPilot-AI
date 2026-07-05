import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse

from apps.projects.models import Project
from apps.planner.models import ProjectPlan, PlanStep
from apps.agents.models import Agent, AgentExecution
from apps.generator.models import GeneratedArtifact
from apps.exports.models import ExportJob

# Import Services
from apps.core.services.gemini_service import GeminiService
from apps.core.services.prompt_builder import PromptBuilder
from apps.planner.services.planner_service import PlannerService
from apps.memory.services.memory_service import MemoryService
from apps.evaluation.services.evaluation_service import EvaluationService
from apps.exports.services.export_service import ExportService

# Import prompts & constants
import config.prompts as prompts_library
from config.constants import (
    PROJECT_STATUS_PLANNING, PROJECT_STATUS_COMPLETE,
    STEP_STATUS_PENDING, STEP_STATUS_COMPLETED,
    AGENT_ROLE_ARCHITECT, AGENT_ROLE_PLANNER, AGENT_ROLE_QA, AGENT_ROLE_WRITER,
    MEMORY_SHORT_TERM, MEMORY_LONG_TERM,
    STEP_IDEA, STEP_REQUIREMENTS, STEP_PRD, STEP_USER_STORIES, STEP_FUNCTIONAL, STEP_NON_FUNCTIONAL,
    STEP_ARCHITECTURE, STEP_DATABASE, STEP_API, STEP_FOLDER_STRUCTURE, STEP_ROADMAP, STEP_SECURITY,
    STEP_TESTING, STEP_DEPLOYMENT
)

logger = logging.getLogger('specpilot.ai')

@login_required
def project_list_view(request):
    """
    Lists all workspace projects owned by the user.
    """
    projects = Project.objects.filter(user=request.user).order_by('-updated_at')
    return render(request, 'projects/list.html', {'projects': projects})

@login_required
def project_create_view(request):
    """
    Processes new project workspace creations and initializes the 14-step planner.
    """
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        architecture = request.POST.get('architecture', 'MONOLITH')
        
        if not title or not description:
            messages.error(request, "Project title and idea description are required.")
            return render(request, 'projects/create.html')
            
        try:
            # 1. Create project
            project = Project.objects.create(
                user=request.user,
                title=title,
                description=description,
                target_architecture=architecture,
                status=PROJECT_STATUS_PLANNING
            )
            
            # 2. Initialize the 14-step planning schema
            plan = PlannerService.initialize_plan(project)
            
            # 3. Create the initial "Project Idea" memory record
            MemoryService.save_memory(
                project=project,
                role="USER",
                content=f"Initial Project Idea: {description}\nTarget Architecture: {architecture}",
                memory_type=MEMORY_SHORT_TERM
            )
            
            # 4. Create the initial Step 1 GeneratedArtifact holding the core idea
            idea_step = plan.steps.filter(step_type=STEP_IDEA).first()
            if idea_step:
                GeneratedArtifact.objects.create(
                    project=project,
                    step=idea_step,
                    artifact_type='TEXT',
                    title="Original Project Idea",
                    content=description
                )
                PlannerService.complete_step(idea_step)
                
            messages.success(request, f"Project '{title}' initialized! Ready for AI Agent planning.")
            return redirect('project_detail', project_id=project.id)
            
        except Exception as e:
            logger.error(f"Failed to create project workspace: {str(e)}")
            messages.error(request, "Failed to initialize workspace.")
            
    return render(request, 'projects/create.html')

@login_required
def project_detail_view(request, project_id):
    """
    Visualizes steps progression, generated files, export options, and validation details.
    """
    project = get_object_or_404(Project, id=project_id, user=request.user)
    plan = getattr(project, 'plan', None)
    
    if not plan:
        # Graceful fallback initialization if plan got corrupted/missing
        plan = PlannerService.initialize_plan(project)
        
    steps = plan.steps.all().order_by('order')
    artifacts = project.artifacts.all().order_by('step__order')
    export_jobs = project.exports.all().order_by('-created_at')
    
    # Check if all planning lifecycle tasks are completed
    all_completed = not steps.exclude(status=STEP_STATUS_COMPLETED).exists()
    if all_completed and project.status != PROJECT_STATUS_COMPLETE:
        project.status = PROJECT_STATUS_COMPLETE
        project.save()
        
    context = {
        'project': project,
        'plan': plan,
        'steps': steps,
        'artifacts': artifacts,
        'export_jobs': export_jobs,
        'all_completed': all_completed
    }
    return render(request, 'projects/detail.html', context)

@login_required
def run_plan_step_view(request, project_id, step_id):
    """
    Orchestrates the AI Agent execution logic for a single planning lifecycle step.
    Loads memory context, formats prompt templates, queries Gemini, validates formatting, and saves artifacts.
    """
    project = get_object_or_404(Project, id=project_id, user=request.user)
    step = get_object_or_404(PlanStep, id=step_id, project_plan__project=project)
    
    # Safety Check: Prevent running if step is already executing
    if step.status == 'RUNNING':
        messages.warning(request, "This planning stage is already being processed by the AI Agent.")
        return redirect('project_detail', project_id=project.id)
        
    # Mark step state running
    PlannerService.start_step(step)
    
    # 1. Map step types to prompts templates & agent roles
    prompt_templates = {
        STEP_REQUIREMENTS: (prompts_library.REQUIREMENTS_PROMPT, AGENT_ROLE_ARCHITECT),
        STEP_PRD: (prompts_library.PRD_PROMPT, AGENT_ROLE_WRITER),
        STEP_USER_STORIES: (prompts_library.USER_STORIES_PROMPT, AGENT_ROLE_PLANNER),
        STEP_FUNCTIONAL: (prompts_library.FUNCTIONAL_PROMPT, AGENT_ROLE_ARCHITECT),
        STEP_NON_FUNCTIONAL: (prompts_library.NON_FUNCTIONAL_PROMPT, AGENT_ROLE_ARCHITECT),
        STEP_ARCHITECTURE: (prompts_library.ARCHITECTURE_PROMPT, AGENT_ROLE_ARCHITECT),
        STEP_DATABASE: (prompts_library.DATABASE_PROMPT, AGENT_ROLE_ARCHITECT),
        STEP_API: (prompts_library.API_PROMPT, AGENT_ROLE_ARCHITECT),
        STEP_FOLDER_STRUCTURE: (prompts_library.FOLDER_STRUCTURE_PROMPT, AGENT_ROLE_ARCHITECT),
        STEP_ROADMAP: (prompts_library.ROADMAP_PROMPT, AGENT_ROLE_PLANNER),
        STEP_SECURITY: (prompts_library.SECURITY_PROMPT, AGENT_ROLE_ARCHITECT),
        STEP_TESTING: (prompts_library.TESTING_PROMPT, AGENT_ROLE_QA),
        STEP_DEPLOYMENT: (prompts_library.DEPLOYMENT_PROMPT, AGENT_ROLE_QA),
    }
    
    if step.step_type not in prompt_templates:
        PlannerService.fail_step(step)
        messages.error(request, "Unrecognized planning phase. Operation aborted.")
        return redirect('project_detail', project_id=project.id)
        
    template, agent_role = prompt_templates[step.step_type]
    
    # 2. Resolve target Agent config (fallback to active agent in db)
    agent = Agent.objects.filter(role=agent_role, is_active=True).first()
    if not agent:
        # Fallback dynamic mock agent configuration if database is unseeded
        agent = Agent.objects.create(
            name=f"Standard {agent_role.title()}",
            role=agent_role,
            description="Dynamically spawned system agent.",
            system_prompt="Execute specialized coding workspace tasks."
        )

    # 3. Create execution log context
    execution = AgentExecution.objects.create(
        agent=agent,
        project=project,
        status='RUNNING'
    )
    
    try:
        # 4. Load memory context
        memory_context = MemoryService.load_context(project)
        
        # 5. Formulate final formatted prompt
        if step.step_type == STEP_REQUIREMENTS:
            prompt = PromptBuilder.build_prompt(
                template,
                idea=project.description,
                architecture=project.get_target_architecture_display()
            )
        else:
            # For subsequent steps, supply the aggregated memory history context
            prompt = PromptBuilder.build_prompt(
                template,
                context_doc=memory_context
            )
            
        # 6. Query the Gemini Service client wrapper
        ai_service = GeminiService(
            api_key=request.user.profile.api_key_override or None,
            model_name="gemini-1.5-flash"
        )
        
        response = ai_service.generate_text(
            prompt=prompt,
            system_instruction=agent.system_prompt,
            temperature=agent.temperature
        )
        
        # 7. Update metrics logs
        execution.input_tokens = response.get("input_tokens", 0)
        execution.output_tokens = response.get("output_tokens", 0)
        execution.execution_time_ms = response.get("elapsed_time_ms", 0)
        
        if not response.get("success", False):
            raise Exception(response.get("error", "AI generation request failed."))
            
        generated_text = response["text"]
        
        # 8. Create & link GeneratedArtifact output
        artifact = GeneratedArtifact.objects.create(
            project=project,
            step=step,
            artifact_type='MARKDOWN',
            title=step.title,
            content=generated_text
        )
        
        # 9. Trigger evaluation validation scoring
        EvaluationService.evaluate_artifact(execution, generated_text, step.title)
        
        # 10. Write output back into project context memory
        MemoryService.save_memory(
            project=project,
            role="AGENT",
            content=f"Generated Output for Phase {step.title}:\n{generated_text}",
            memory_type=MEMORY_SHORT_TERM
        )
        
        execution.status = 'SUCCEEDED'
        execution.save()
        
        # Mark plan step stage complete
        PlannerService.complete_step(step)
        messages.success(request, f"Phase '{step.title}' successfully completed by {agent.name}!")
        
    except Exception as ex:
        logger.error(f"Error during execution run of step '{step.title}': {str(ex)}")
        execution.status = 'FAILED'
        execution.error_message = str(ex)
        execution.save()
        
        PlannerService.fail_step(step)
        messages.error(request, f"Agent failed to plan phase: {str(ex)}")
        
    return redirect('project_detail', project_id=project.id)

@login_required
def export_project_view(request, project_id):
    """
    Handles POST triggers to generate download files.
    """
    project = get_object_or_404(Project, id=project_id, user=request.user)
    
    if request.method == 'POST':
        export_format = request.POST.get('format', 'MARKDOWN')
        
        if export_format not in ['MARKDOWN', 'PDF', 'JSON']:
            messages.error(request, "Unsupported export format.")
            return redirect('project_detail', project_id=project.id)
            
        job = ExportService.run_export_job(project, export_format)
        if job.status == 'SUCCEEDED':
            messages.success(request, f"Compiled blueprint exported successfully in {export_format} format!")
        else:
            messages.error(request, f"Export compilation failed: {job.error_message}")
            
    return redirect('project_detail', project_id=project.id)
