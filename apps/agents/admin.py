from django.contrib import admin
from apps.agents.models import Agent, AgentExecution

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'version', 'status', 'is_active')
    list_filter = ('role', 'status', 'is_active')
    search_fields = ('name', 'description')

@admin.register(AgentExecution)
class AgentExecutionAdmin(admin.ModelAdmin):
    list_display = ('agent', 'project', 'status', 'input_tokens', 'output_tokens', 'execution_time_ms', 'created_at')
    list_filter = ('status',)
    search_fields = ('project__title', 'agent__name')
