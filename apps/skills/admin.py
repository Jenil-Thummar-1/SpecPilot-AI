from django.contrib import admin
from apps.skills.models import Skill, SkillVersion, SkillExecution

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'code_identifier', 'created_at')
    search_fields = ('name', 'code_identifier')

@admin.register(SkillVersion)
class SkillVersionAdmin(admin.ModelAdmin):
    list_display = ('skill', 'version', 'is_active', 'created_at')
    list_filter = ('is_active',)

@admin.register(SkillExecution)
class SkillExecutionAdmin(admin.ModelAdmin):
    list_display = ('skill_version', 'agent_execution', 'status', 'created_at')
    list_filter = ('status',)
