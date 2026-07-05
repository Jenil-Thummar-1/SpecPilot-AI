from django.contrib import admin
from apps.projects.models import Project

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'target_architecture', 'status', 'created_at')
    list_filter = ('status', 'target_architecture')
    search_fields = ('title', 'description')
