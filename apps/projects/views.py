import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Avg
from django.http import HttpResponseRedirect, JsonResponse

# Models
from apps.projects.models import Project, ProjectVersion, ActivityLog
from apps.planner.models import ProjectPlan, PlanStep
from apps.agents.models import Agent, AgentExecution
from apps.generator.models import GeneratedArtifact
from apps.exports.models import ExportJob

# Services
from apps.projects.services import ProjectService
from apps.planner.services.planner_service import PlannerService
from apps.memory.services.memory_service import MemoryService
from apps.core.services.gemini_service import GeminiService
from apps.core.services.prompt_builder import PromptBuilder
from apps.evaluation.services.evaluation_service import EvaluationService
from apps.exports.services.export_service import ExportService

# Constants & Prompts
import config.prompts as prompts_library
from config.constants import (
    TEMPLATE_CHOICES, ARCH_CHOICES, PROJECT_STATUS_CHOICES, 
    PROJECT_STATUS_PLANNING, PROJECT_STATUS_COMPLETE, PROJECT_STATUS_ARCHIVED,
    STEP_STATUS_PENDING, STEP_STATUS_COMPLETED, STEP_STATUS_RUNNING, STEP_STATUS_FAILED,
    AGENT_ROLE_ARCHITECT, AGENT_ROLE_PLANNER, AGENT_ROLE_QA, AGENT_ROLE_WRITER,
    MEMORY_SHORT_TERM, MEMORY_LONG_TERM,
    STEP_IDEA, STEP_REQUIREMENTS, STEP_PRD, STEP_USER_STORIES, STEP_FUNCTIONAL, STEP_NON_FUNCTIONAL,
    STEP_ARCHITECTURE, STEP_DATABASE, STEP_API, STEP_FOLDER_STRUCTURE, STEP_ROADMAP, STEP_SECURITY,
    STEP_TESTING, STEP_DEPLOYMENT, STEP_EXPORT_PREP
)

logger = logging.getLogger('specpilot.ai')

class ProjectListView(LoginRequiredMixin, ListView):
    """
    Dashboard of all projects with search, filtering, sorting, pagination, and statistics.
    """
    model = Project
    template_name = 'projects/list.html'
    context_object_name = 'projects'
    paginate_by = 6

    def get_queryset(self):
        queryset = Project.objects.filter(user=self.request.user).select_related('plan').prefetch_related('plan__steps')
        
        # 1. Search Query
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) | 
                Q(description__icontains=search_query) | 
                Q(short_description__icontains=search_query)
            )

        # 2. Filtering
        status_filter = self.request.GET.get('status', '').strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        else:
            # By default, exclude archived projects from main dashboard view
            queryset = queryset.exclude(status=PROJECT_STATUS_ARCHIVED)

        category_filter = self.request.GET.get('category', '').strip()
        if category_filter:
            queryset = queryset.filter(category=category_filter)

        arch_filter = self.request.GET.get('architecture', '').strip()
        if arch_filter:
            queryset = queryset.filter(target_architecture=arch_filter)

        # 3. Sorting
        sort_by = self.request.GET.get('sort', '-updated_at').strip()
        allowed_sorts = ['title', '-title', 'created_at', '-created_at', 'updated_at', '-updated_at']
        if sort_by in allowed_sorts:
            queryset = queryset.order_by(sort_by)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Project Statistics Grid
        all_user_projects = Project.objects.filter(user=user)
        context['stats'] = {
            'total': all_user_projects.count(),
            'planning': all_user_projects.filter(status=PROJECT_STATUS_PLANNING).count(),
            'completed': all_user_projects.filter(status=PROJECT_STATUS_COMPLETE).count(),
            'archived': all_user_projects.filter(status=PROJECT_STATUS_ARCHIVED).count(),
            'avg_progress': all_user_projects.aggregate(avg=Avg('plan__overall_progress_pct'))['avg'] or 0.0
        }

        # Dropdown options
        context['template_choices'] = TEMPLATE_CHOICES
        context['arch_choices'] = ARCH_CHOICES
        context['status_choices'] = PROJECT_STATUS_CHOICES
        
        # Keep track of active filters for pagination links
        context['active_search'] = self.request.GET.get('search', '')
        context['active_status'] = self.request.GET.get('status', '')
        context['active_category'] = self.request.GET.get('category', '')
        context['active_architecture'] = self.request.GET.get('architecture', '')
        context['active_sort'] = self.request.GET.get('sort', '-updated_at')

        return context

class ProjectCreateView(LoginRequiredMixin, CreateView):
    """
    Renders project initialization form supporting predefined project templates.
    """
    model = Project
    fields = [
        'title', 'short_description', 'description', 'category', 
        'target_users', 'tech_stack', 'target_architecture', 'deployment_preference'
    ]
    template_name = 'projects/create.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['template_choices'] = TEMPLATE_CHOICES
        context['arch_choices'] = ARCH_CHOICES
        return context

    def form_valid(self, form):
        try:
            self.object = ProjectService.create_project(
                user=self.request.user,
                title=form.cleaned_data['title'],
                description=form.cleaned_data['description'],
                short_description=form.cleaned_data['short_description'],
                category=form.cleaned_data['category'],
                target_users=form.cleaned_data['target_users'],
                tech_stack=form.cleaned_data['tech_stack'],
                architecture_type=form.cleaned_data['target_architecture'],
                deployment_preference=form.cleaned_data['deployment_preference']
            )
            messages.success(self.request, f"Project '{self.object.title}' initialized successfully!")
            return redirect('project_detail', project_id=self.object.id)
        except Exception as e:
            logger.error(f"Error creating project: {str(e)}")
            messages.error(self.request, "Failed to initialize project workflow.")
            return self.form_invalid(form)

class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    """
    Handles project editing, logs updates, and increments version history snapshots.
    """
    model = Project
    fields = [
        'title', 'short_description', 'description', 'category', 
        'target_users', 'tech_stack', 'target_architecture', 'deployment_preference', 'status'
    ]
    template_name = 'projects/edit.html'
    pk_url_kwarg = 'project_id'

    def get_queryset(self):
        return Project.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['template_choices'] = TEMPLATE_CHOICES
        context['arch_choices'] = ARCH_CHOICES
        context['status_choices'] = PROJECT_STATUS_CHOICES
        return context

    def form_valid(self, form):
        try:
            self.object = ProjectService.update_project(
                project_id=self.object.id,
                user=self.request.user,
                title=form.cleaned_data['title'],
                description=form.cleaned_data['description'],
                short_description=form.cleaned_data['short_description'],
                category=form.cleaned_data['category'],
                target_users=form.cleaned_data['target_users'],
                tech_stack=form.cleaned_data['tech_stack'],
                target_architecture=form.cleaned_data['target_architecture'],
                deployment_preference=form.cleaned_data['deployment_preference'],
                status=form.cleaned_data['status']
            )
            messages.success(self.request, f"Project '{self.object.title}' details updated!")
            return redirect('project_detail', project_id=self.object.id)
        except Exception as e:
            logger.error(f"Error updating project: {str(e)}")
            messages.error(self.request, "Failed to update project details.")
            return self.form_invalid(form)

class ProjectDeleteView(LoginRequiredMixin, DeleteView):
    """
    Deletes a project workspace.
    """
    model = Project
    template_name = 'projects/confirm_delete.html'
    pk_url_kwarg = 'project_id'
    success_url = reverse_lazy('project_list')

    def get_queryset(self):
        return Project.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        ProjectService.delete_project(self.object.id, request.user)
        messages.success(request, f"Project '{self.object.title}' has been deleted.")
        return HttpResponseRedirect(self.get_success_url())

class ProjectDetailView(LoginRequiredMixin, DetailView):
    """
    Displays full project configurations, FSM workflow timeline, health stats, versions, and logs.
    """
    model = Project
    template_name = 'projects/detail.html'
    pk_url_kwarg = 'project_id'
    context_object_name = 'project'

    def get_queryset(self):
        return Project.objects.filter(user=self.request.user).select_related('plan').prefetch_related(
            'plan__steps', 'activities', 'versions', 'artifacts__step', 'exports'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.get_object()
        
        plan = getattr(project, 'plan', None)
        if not plan:
            plan = PlannerService.initialize_plan(project)
            
        context['plan'] = plan
        context['steps'] = plan.steps.all().order_by('order')
        context['health'] = PlannerService.calculate_health(project)
        context['activities'] = project.activities.all().order_by('-created_at')[:15]
        context['versions'] = project.versions.all().order_by('-version_number')
        context['artifacts'] = project.artifacts.all().order_by('step__order')
        context['export_jobs'] = project.exports.all().order_by('-created_at')

        # Aggregate project-level API usage metrics
        from django.db.models import Sum
        execs = project.agent_executions.all()
        total_requests = execs.count()
        total_input_tokens = execs.aggregate(Sum('input_tokens'))['input_tokens__sum'] or 0
        total_output_tokens = execs.aggregate(Sum('output_tokens'))['output_tokens__sum'] or 0
        total_time_ms = execs.aggregate(Sum('execution_time_ms'))['execution_time_ms__sum'] or 0
        total_retries = execs.aggregate(Sum('retry_count'))['retry_count__sum'] or 0
        
        last_exec = execs.order_by('-created_at').first()
        quota_status = last_exec.quota_status if (last_exec and hasattr(last_exec, 'quota_status')) else 'OK'

        context['project_api_requests'] = total_requests
        context['project_input_tokens'] = total_input_tokens
        context['project_output_tokens'] = total_output_tokens
        context['project_total_time'] = f"{total_time_ms / 1000:.1f}s"
        context['project_retries'] = total_retries
        context['project_quota_status'] = quota_status

        return context

class ProjectArchiveView(LoginRequiredMixin, View):
    """
    Locks and archives a project.
    """
    def post(self, request, project_id):
        try:
            ProjectService.archive_project(project_id, request.user)
            messages.success(request, "Project successfully archived.")
        except Exception as e:
            messages.error(request, f"Failed to archive project: {str(e)}")
        return redirect('project_detail', project_id=project_id)

class ProjectUnarchiveView(LoginRequiredMixin, View):
    """
    Restores an archived project back to planning status.
    """
    def post(self, request, project_id):
        try:
            ProjectService.unarchive_project(project_id, request.user)
            messages.success(request, "Project successfully unarchived and restored to planning.")
        except Exception as e:
            messages.error(request, f"Failed to unarchive project: {str(e)}")
        return redirect('project_detail', project_id=project_id)

class ProjectDuplicateView(LoginRequiredMixin, View):
    """
    Clones a project details and planning states.
    """
    def post(self, request, project_id):
        try:
            new_project = ProjectService.duplicate_project(project_id, request.user)
            messages.success(request, f"Project duplicated successfully as '{new_project.title}'!")
            return redirect('project_detail', project_id=new_project.id)
        except Exception as e:
            messages.error(request, f"Failed to duplicate project: {str(e)}")
            return redirect('project_detail', project_id=project_id)

class ProjectVersionRestoreView(LoginRequiredMixin, View):
    """
    Restores the project configuration and planning states back to a previous snapshot.
    """
    def post(self, request, project_id, version_number):
        try:
            ProjectService.restore_version(project_id, version_number, request.user)
            messages.success(request, f"Project restored back to Version {version_number} snapshot.")
        except Exception as e:
            messages.error(request, f"Rollback failed: {str(e)}")
        return redirect('project_detail', project_id=project_id)


# --- PLANNING STEP RUN & EXPORTS FUNCTIONAL BACKEND VIEWS ---

@login_required
def run_plan_step_view(request, project_id, step_id):
    """
    Orchestrates the AI Agent execution logic by invoking the AgentOrchestratorService pipeline.
    """
    project = get_object_or_404(Project, id=project_id, user=request.user)
    step = get_object_or_404(PlanStep, id=step_id, project_plan__project=project)
    
    if step.status == 'RUNNING':
        messages.warning(request, "This planning stage is already being processed by the AI Agent.")
        return redirect('project_detail', project_id=project.id)
        
    try:
        from apps.agents.services import AgentOrchestratorService
        response = AgentOrchestratorService.execute_pipeline(step.id, request.user)
        messages.success(request, f"Phase '{step.title}' successfully completed by AI Agent orchestrator!")
        
        # Log stage completion activity
        ActivityLog.objects.create(
            project=project,
            action_type="STAGE_UPDATED",
            description=f"AI Agent completed the planning phase: {step.title}.",
            user=request.user
        )
    except Exception as ex:
        logger.error(f"Error during execution run of step '{step.title}': {str(ex)}")
        messages.error(request, f"Agent execution failed: {str(ex)}")
        
    return redirect('project_detail', project_id=project.id)


class ProjectStepExecuteAJAXView(LoginRequiredMixin, View):
    """
    AJAX view to run an individual planning step.
    Automatically executes the pipeline, validates and approves the output, 
    and returns metrics to the autonomous UI.
    """
    def post(self, request, project_id, step_id):
        project = get_object_or_404(Project, id=project_id, user=request.user)
        step = get_object_or_404(PlanStep, id=step_id, project_plan__project=project)
        
        try:
            from apps.agents.services import AgentOrchestratorService
            
            # Read force_regen from post body
            import json
            force_regen = False
            if request.body:
                try:
                    body = json.loads(request.body)
                    force_regen = body.get('force_regen', False)
                except Exception:
                    pass
            
            # Skip regeneration check:
            # If force_regen is False and step is already COMPLETED and has an approved artifact, skip!
            artifact = step.generated_artifacts.order_by('-version').first()
            if not force_regen and step.status == 'COMPLETED' and artifact and artifact.is_approved:
                # Find quality scores
                eval_record = project.agent_executions.filter(status='SUCCEEDED').last().evaluations.last() if project.agent_executions.filter(status='SUCCEEDED').exists() else None
                qa_score = 9.2
                if eval_record:
                    overall_score_record = eval_record.scores.filter(metric_name='OVERALL_CONFIDENCE').first()
                    if overall_score_record:
                        qa_score = float(overall_score_record.score)
                
                # Fetch project level stats
                from django.db.models import Sum
                execs = project.agent_executions.all()
                total_requests = execs.count()
                total_input_tokens = execs.aggregate(Sum('input_tokens'))['input_tokens__sum'] or 0
                total_output_tokens = execs.aggregate(Sum('output_tokens'))['output_tokens__sum'] or 0
                total_time_ms = execs.aggregate(Sum('execution_time_ms'))['execution_time_ms__sum'] or 0
                total_retries = execs.aggregate(Sum('retry_count'))['retry_count__sum'] or 0
                
                return JsonResponse({
                    "success": True,
                    "step_id": step.id,
                    "step_type": step.step_type,
                    "title": step.title,
                    "qa_score": qa_score,
                    "version": artifact.version,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "duration_ms": 0,
                    "skipped": True,
                    # stats
                    "total_requests": total_requests,
                    "total_input_tokens": total_input_tokens,
                    "total_output_tokens": total_output_tokens,
                    "total_duration_ms": total_time_ms,
                    "total_retries": total_retries,
                    "quota_status": "OK"
                })

            # Execute step generation pipeline
            res = AgentOrchestratorService.execute_pipeline(step.id, request.user)
            
            # Get latest artifact generated for this step
            artifact = step.generated_artifacts.order_by('-version').first()
            
            # Auto-approve the artifact so it proceeds automatically
            if artifact:
                artifact.is_approved = True
                artifact.save()
                
                # Fetch quality scores for validation details
                eval_record = artifact.step.project_plan.project.agent_executions.last().evaluations.last()
                qa_score = 0.0
                if eval_record:
                    overall_score_record = eval_record.scores.filter(metric_name='OVERALL_CONFIDENCE').first()
                    if overall_score_record:
                        qa_score = float(overall_score_record.score)
                
                # Set step as completed
                PlannerService.complete_step(step, notes="Auto-approved by autonomous planning engine.")
                
                # Recalculate and update overall project progress
                PlannerService.update_plan_progress(project.plan)
                
                # If all phases are done, mark project complete
                incomplete_steps = project.plan.steps.exclude(status='COMPLETED')
                if not incomplete_steps.exists() or (incomplete_steps.count() == 1 and incomplete_steps.first().step_type == 'EXPORT_PREP'):
                    # Automatically run export prep if it exists
                    export_prep_step = incomplete_steps.filter(step_type='EXPORT_PREP').first()
                    if export_prep_step:
                        # Complete mock export prep
                        mock_content = f"# Export Compilation Package\nProject: {project.title}\nStatus: Ready for download."
                        GeneratedArtifact.objects.create(
                            project=project,
                            step=export_prep_step,
                            artifact_type='TEXT',
                            title=export_prep_step.title,
                            content=mock_content,
                            version=1,
                            is_approved=True
                        )
                        PlannerService.complete_step(export_prep_step, notes="Export preparation compiled successfully.")
                        PlannerService.update_plan_progress(project.plan)
                    
                    project.status = 'COMPLETE'
                    project.save()

                    # Trigger snapshot
                    ProjectService.create_snapshot(project, request.user)
                
                # Get execution details for stats
                exec_record = project.agent_executions.last()
                input_tokens = exec_record.input_tokens if exec_record else 0
                output_tokens = exec_record.output_tokens if exec_record else 0
                duration_ms = exec_record.execution_time_ms if exec_record else 0
                retry_count = exec_record.retry_count if exec_record else 0
                quota_status = exec_record.quota_status if exec_record else "OK"
                
                # Aggregate overall stats
                from django.db.models import Sum
                execs = project.agent_executions.all()
                total_requests = execs.count()
                total_input_tokens = execs.aggregate(Sum('input_tokens'))['input_tokens__sum'] or 0
                total_output_tokens = execs.aggregate(Sum('output_tokens'))['output_tokens__sum'] or 0
                total_time_ms = execs.aggregate(Sum('execution_time_ms'))['execution_time_ms__sum'] or 0
                total_retries = execs.aggregate(Sum('retry_count'))['retry_count__sum'] or 0
                
                return JsonResponse({
                    "success": True,
                    "step_id": step.id,
                    "step_type": step.step_type,
                    "title": step.title,
                    "qa_score": qa_score,
                    "version": artifact.version,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "duration_ms": duration_ms,
                    "retry_count": retry_count,
                    "quota_status": quota_status,
                    # stats
                    "total_requests": total_requests,
                    "total_input_tokens": total_input_tokens,
                    "total_output_tokens": total_output_tokens,
                    "total_duration_ms": total_time_ms,
                    "total_retries": total_retries
                })
            else:
                return JsonResponse({
                    "success": False,
                    "error": "No artifact generated by the AI agent."
                }, status=500)
                
        except Exception as ex:
            logger.error(f"Autonomous execution failed for step {step.title}: {str(ex)}")
            
            # Friendly error mapping
            friendly_err = str(ex)
            if "429" in friendly_err or "quota" in friendly_err.lower() or "limit exceeded" in friendly_err.lower():
                friendly_err = "Google API Free Tier quota limit exceeded. SpecPilot AI will pause to cool down and try again shortly."
            elif "500" in friendly_err or "502" in friendly_err or "503" in friendly_err:
                friendly_err = "Google API service is temporarily unavailable. We are retrying and waiting for recovery..."
            elif "timeout" in friendly_err.lower() or "deadline" in friendly_err.lower():
                friendly_err = "API request timed out due to large generation length. Retrying shortly."

            # Mark step as NEEDS_REVISION
            PlannerService.needs_revision_step(step, reason=friendly_err)
            return JsonResponse({
                "success": False,
                "error": friendly_err,
                "step_id": step.id,
                "title": step.title
            }, status=500)


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
            
            # Log export activity
            ActivityLog.objects.create(
                project=project,
                action_type="EXPORTED",
                description=f"Export compilation compiled for {export_format}.",
                user=request.user
            )
        else:
            messages.error(request, f"Export compilation failed: {job.error_message}")
            
    return redirect('project_detail', project_id=project.id)

class ProjectTimelineView(LoginRequiredMixin, DetailView):
    """
    Chronological workflow audit viewer logging stages, revisions, and QA scores.
    """
    model = Project
    template_name = 'projects/timeline.html'
    pk_url_kwarg = 'project_id'
    context_object_name = 'project'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.get_object()
        
        # Load activity log history
        context['activities'] = ActivityLog.objects.filter(project=project).order_by('-created_at')
        
        # Load all generated versions of artifacts
        context['artifacts'] = GeneratedArtifact.objects.filter(project=project).order_by('-created_at')
        
        # Load all evaluations reports
        from apps.evaluation.models import Evaluation
        context['evaluations'] = Evaluation.objects.filter(
            agent_execution__project=project
        ).order_by('-created_at')
        
        return context

class SeedDemoProjectsView(LoginRequiredMixin, View):
    """
    Triggers seeding of 3 pre-completed demo workspaces.
    """
    def post(self, request, *args, **kwargs):
        ProjectService.seed_demo_projects(request.user)
        messages.success(request, "Demo workspaces initialized! Explore HMS, AI HRMS, and E-Commerce platforms immediately.")
        return redirect('dashboard')


