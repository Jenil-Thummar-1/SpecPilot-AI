from django.contrib import admin
from apps.exports.models import ExportJob

@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'export_format', 'status', 'created_at')
    list_filter = ('export_format', 'status')
