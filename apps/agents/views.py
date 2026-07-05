import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, View
from django.contrib import messages
from django.urls import reverse_lazy

from apps.agents.models import Agent, AgentExecution
from apps.skills.models import Skill
from config.constants import AGENT_ROLE_CHOICES, AGENT_STATUS_CHOICES, AGENT_STATUS_IDLE

logger = logging.getLogger('specpilot.ai')

class AgentListView(LoginRequiredMixin, ListView):
    """
    Renders dashboard of seeded AI Agents.
    """
    model = Agent
    template_name = 'agents/list.html'
    context_object_name = 'agents'
    ordering = ['role']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Statistics
        context['stats'] = {
            'total': Agent.objects.count(),
            'active': Agent.objects.filter(is_active=True).count(),
            'idle': Agent.objects.filter(status='IDLE').count(),
            'busy': Agent.objects.filter(status__in=['THINKING', 'EXECUTING']).count()
        }
        return context

class AgentCreateView(LoginRequiredMixin, CreateView):
    """
    Creates specialized agents with custom temperatures, prompts, and permissions.
    """
    model = Agent
    fields = [
        'name', 'role', 'description', 'system_prompt', 
        'temperature', 'max_tokens', 'supported_project_types', 'config_settings', 'skills'
    ]
    template_name = 'agents/create.html'
    success_url = reverse_lazy('agent_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['role_choices'] = AGENT_ROLE_CHOICES
        context['skills_choices'] = Skill.objects.all()
        return context

    def form_valid(self, form):
        form.instance.status = AGENT_STATUS_IDLE
        messages.success(self.request, f"Agent '{form.cleaned_data['name']}' created successfully!")
        return super().form_valid(form)

class AgentUpdateView(LoginRequiredMixin, UpdateView):
    """
    Edits agent parameters.
    """
    model = Agent
    fields = [
        'name', 'role', 'description', 'system_prompt', 
        'temperature', 'max_tokens', 'supported_project_types', 'config_settings', 'skills', 'is_active'
    ]
    template_name = 'agents/edit.html'
    pk_url_kwarg = 'agent_id'
    success_url = reverse_lazy('agent_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['role_choices'] = AGENT_ROLE_CHOICES
        context['skills_choices'] = Skill.objects.all()
        return context

    def form_valid(self, form):
        messages.success(self.request, f"Agent '{form.cleaned_data['name']}' configurations updated!")
        return super().form_valid(form)

class AgentToggleView(LoginRequiredMixin, View):
    """
    Toggles is_active state.
    """
    def post(self, request, agent_id):
        agent = get_object_or_404(Agent, id=agent_id)
        agent.is_active = not agent.is_active
        agent.save()
        status_text = "activated" if agent.is_active else "deactivated"
        messages.success(request, f"Agent '{agent.name}' has been {status_text}.")
        return redirect('agent_list')

class ExecutionHistoryView(LoginRequiredMixin, ListView):
    """
    Audits token metrics, latency, and logs of LLM queries.
    """
    model = AgentExecution
    template_name = 'agents/executions.html'
    context_object_name = 'executions'
    paginate_by = 10
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        # Search by project title
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            queryset = queryset.filter(project__title__icontains=search_query)
        
        # Filter by status
        status_filter = self.request.GET.get('status', '').strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_search'] = self.request.GET.get('search', '')
        context['active_status'] = self.request.GET.get('status', '')
        return context
