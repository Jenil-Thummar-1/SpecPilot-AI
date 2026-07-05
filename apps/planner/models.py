from django.db import models
from apps.core.models import TimeStampedModel
from config.constants import PLAN_STEP_CHOICES, STEP_STATUS_CHOICES, STEP_STATUS_PENDING

class ProjectPlan(TimeStampedModel):
    """
    Orchestrator plan linking a project workspace with its step execution stages.
    """
    project = models.OneToOneField('projects.Project', on_delete=models.CASCADE, related_name='plan')
    current_step_index = models.IntegerField(default=0, help_text="Tracks active index inside PlanSteps.")
    overall_progress_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)

    def __str__(self):
        return f"Plan for {self.project.title} - Progress: {self.overall_progress_pct}%"

class PlanStep(TimeStampedModel):
    """
    A single phase within the 14-step project planning lifecycle.
    """
    project_plan = models.ForeignKey(ProjectPlan, on_delete=models.CASCADE, related_name='steps')
    step_type = models.CharField(max_length=30, choices=PLAN_STEP_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    order = models.IntegerField()
    status = models.CharField(max_length=20, choices=STEP_STATUS_CHOICES, default=STEP_STATUS_PENDING)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Step {self.order}: {self.title} ({self.status}) for Plan {self.project_plan.id}"
