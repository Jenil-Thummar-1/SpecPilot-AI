from django.contrib import admin
from apps.planner.models import ProjectPlan, PlanStep

@admin.register(ProjectPlan)
class ProjectPlanAdmin(admin.ModelAdmin):
    list_display = ('project', 'current_step_index', 'overall_progress_pct', 'created_at')

@admin.register(PlanStep)
class PlanStepAdmin(admin.ModelAdmin):
    list_display = ('project_plan', 'step_type', 'title', 'order', 'status', 'started_at', 'completed_at')
    list_filter = ('step_type', 'status')
    search_fields = ('title', 'description')
