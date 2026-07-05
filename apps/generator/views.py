import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, UpdateView, View
from django.contrib import messages
from django.urls import reverse

from apps.generator.models import GeneratedArtifact
from apps.planner.models import PlanStep
from apps.projects.models import ActivityLog
from apps.planner.services.planner_service import PlannerService

logger = logging.getLogger('specpilot.ai')

class ArtifactDetailView(LoginRequiredMixin, DetailView):
    """
    Renders detailed text of a generated planning artifact.
    """
    model = GeneratedArtifact
    template_name = 'generator/detail.html'
    pk_url_kwarg = 'artifact_id'
    context_object_name = 'artifact'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        art = self.get_object()
        # Find all versions of this planning phase artifact
        context['versions'] = GeneratedArtifact.objects.filter(
            project=art.project, 
            step=art.step
        ).order_by('-version')
        return context

class ArtifactEditView(LoginRequiredMixin, UpdateView):
    """
    Allows manually updating draft specifications content.
    """
    model = GeneratedArtifact
    fields = ['content']
    template_name = 'generator/edit.html'
    pk_url_kwarg = 'artifact_id'

    def get_success_url(self):
        return reverse('project_detail', kwargs={'project_id': self.object.project.id})

    def form_valid(self, form):
        art = self.get_object()
        
        # Save edit as a new version
        new_content = form.cleaned_data['content']
        latest_version = GeneratedArtifact.objects.filter(
            project=art.project, 
            step=art.step
        ).order_by('-version').first()
        
        next_ver = (latest_version.version + 1) if latest_version else 1

        self.object = GeneratedArtifact.objects.create(
            project=art.project,
            step=art.step,
            artifact_type=art.artifact_type,
            title=art.title,
            content=new_content,
            version=next_ver,
            is_approved=art.is_approved
        )

        ActivityLog.objects.create(
            project=art.project,
            action_type="EDITED",
            description=f"Manually edited planning specs for '{art.step.title}' (Created v{next_ver}).",
            user=self.request.user
        )

        messages.success(self.request, f"Saved manual updates to new version v{next_ver}!")
        return redirect(self.get_success_url())

class ArtifactApproveView(LoginRequiredMixin, View):
    """
    Approves the planning stage artifact and unlocks subsequent phases.
    """
    def post(self, request, artifact_id):
        art = get_object_or_404(GeneratedArtifact, id=artifact_id, project__user=request.user)
        art.is_approved = True
        art.save()

        # Update step status to COMPLETED
        if art.step:
            PlannerService.complete_step(art.step, notes="Spec document approved by project architect.")
        
        ActivityLog.objects.create(
            project=art.project,
            action_type="STAGE_UPDATED",
            description=f"Approved specifications document: {art.title}.",
            user=request.user
        )

        messages.success(request, f"Specification '{art.title}' approved. Next planning stage unlocked!")
        return redirect('project_detail', project_id=art.project.id)

class ArtifactRejectView(LoginRequiredMixin, View):
    """
    Rejects the artifact, marking the stage as failed to permit regeneration.
    """
    def post(self, request, artifact_id):
        art = get_object_or_404(GeneratedArtifact, id=artifact_id, project__user=request.user)
        art.is_approved = False
        art.save()

        # Update step status to FAILED
        if art.step:
            PlannerService.fail_step(art.step, error_message="Review rejected by workspace architect.")
        
        ActivityLog.objects.create(
            project=art.project,
            action_type="STAGE_UPDATED",
            description=f"Rejected specifications document: {art.title}.",
            user=request.user
        )

        messages.warning(request, f"Specification '{art.title}' rejected. Click 'Run Planning Step' to retry generation.")
        return redirect('project_detail', project_id=art.project.id)

class ArtifactCompareView(LoginRequiredMixin, View):
    """
    Compares two versions of the document side-by-side.
    """
    def get(self, request, artifact_id, compare_id):
        art1 = get_object_or_404(GeneratedArtifact, id=artifact_id, project__user=request.user)
        art2 = get_object_or_404(GeneratedArtifact, id=compare_id, project__user=request.user)

        context = {
            'artifact': art1,
            'compare_artifact': art2,
            'project': art1.project
        }
        return render(request, 'generator/compare.html', context)
