from django.contrib import admin
from apps.generator.models import GeneratedArtifact

@admin.register(GeneratedArtifact)
class GeneratedArtifactAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'step', 'artifact_type', 'version', 'created_at')
    list_filter = ('artifact_type',)
    search_fields = ('title', 'content')
