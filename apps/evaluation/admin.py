from django.contrib import admin
from apps.evaluation.models import Evaluation, QualityScore, AgentFeedback

@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ('id', 'agent_execution', 'evaluator_name', 'status', 'created_at')
    list_filter = ('status',)

@admin.register(QualityScore)
class QualityScoreAdmin(admin.ModelAdmin):
    list_display = ('id', 'evaluation', 'metric_name', 'score', 'created_at')
    list_filter = ('metric_name',)

@admin.register(AgentFeedback)
class AgentFeedbackAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'artifact', 'rating', 'is_resolved', 'created_at')
    list_filter = ('rating', 'is_resolved')
