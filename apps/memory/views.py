import logging
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView
from apps.projects.models import Project
from apps.memory.models import Conversation, MemoryEntry
from apps.memory.services.memory_service import MemoryService

logger = logging.getLogger('specpilot.ai')

class MemoryListView(LoginRequiredMixin, ListView):
    """
    Lists workspace projects and details active memory counts.
    """
    model = Project
    template_name = 'memory/list.html'
    context_object_name = 'projects'

    def get_queryset(self):
        return Project.objects.filter(user=self.request.user).order_by('-updated_at')

class MemoryDetailView(LoginRequiredMixin, DetailView):
    """
    Visualizes short-term, summaries, and keyword context retrieval logs of the project.
    """
    model = Project
    template_name = 'memory/detail.html'
    pk_url_kwarg = 'project_id'
    context_object_name = 'project'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.get_object()

        # Load session details
        session = MemoryService.get_or_create_active_session(project)
        context['session'] = session
        
        # Load entries by categories
        context['short_term'] = MemoryEntry.objects.filter(session=session, memory_type='SHORT_TERM').order_by('created_at')
        context['long_term'] = MemoryEntry.objects.filter(session__conversation__project=project, memory_type='LONG_TERM').order_by('-created_at')
        context['summaries'] = MemoryEntry.objects.filter(session__conversation__project=project, memory_type='SUMMARY').order_by('-created_at')
        
        # Keyword Search Context Retrieval
        query = self.request.GET.get('query', '').strip()
        context['query'] = query
        if query:
            context['retrieved'] = MemoryService.retrieve_relevant_context(project, query)

        return context
