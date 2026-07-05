import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView
from django.contrib import messages
from django.urls import reverse_lazy

from apps.skills.models import Skill, SkillVersion
from apps.skills.services import SkillOrchestratorService

logger = logging.getLogger('specpilot.ai')

class SkillListView(LoginRequiredMixin, ListView):
    """
    Renders listing of Seeded AI Capabilities.
    """
    model = Skill
    template_name = 'skills/list.html'
    context_object_name = 'skills'
    ordering = ['category', 'execution_order']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stats'] = {
            'total': Skill.objects.count(),
            'db': Skill.objects.filter(category__icontains='Database').count() or Skill.objects.filter(category__icontains='DB').count(),
            'api': Skill.objects.filter(category__icontains='API').count(),
            'general': Skill.objects.filter(category='General').count()
        }
        return context

class SkillCreateView(LoginRequiredMixin, CreateView):
    """
    Creates reusable skills and sets parameter JSON schemas.
    """
    model = Skill
    fields = [
        'name', 'code_identifier', 'description', 'category', 
        'execution_order', 'dependencies_str', 'parameters_schema'
    ]
    template_name = 'skills/create.html'
    success_url = reverse_lazy('skill_list')

    def form_valid(self, form):
        try:
            self.object = SkillOrchestratorService.register_skill(
                name=form.cleaned_data['name'],
                code_identifier=form.cleaned_data['code_identifier'],
                description=form.cleaned_data['description'],
                category=form.cleaned_data['category'],
                execution_order=form.cleaned_data['execution_order'],
                dependencies_str=form.cleaned_data['dependencies_str'],
                parameters_schema=form.cleaned_data['parameters_schema']
            )
            
            # Automatically create a Version 1 record
            SkillVersion.objects.create(
                skill=self.object,
                version='1.0.0',
                prompt_template=f"Instruction block for skill: {self.object.name}",
                is_active=True
            )
            
            messages.success(self.request, f"Skill '{self.object.name}' registered successfully!")
            return redirect(self.get_success_url())
        except Exception as e:
            logger.error(f"Error creating skill: {str(e)}")
            messages.error(self.request, "Failed to register skill.")
            return self.form_invalid(form)

class SkillUpdateView(LoginRequiredMixin, UpdateView):
    """
    Modifies skill details.
    """
    model = Skill
    fields = [
        'name', 'code_identifier', 'description', 'category', 
        'execution_order', 'dependencies_str', 'parameters_schema'
    ]
    template_name = 'skills/edit.html'
    pk_url_kwarg = 'skill_id'
    success_url = reverse_lazy('skill_list')

    def form_valid(self, form):
        messages.success(self.request, f"Skill '{form.cleaned_data['name']}' configs updated!")
        return super().form_valid(form)
