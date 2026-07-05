from django.db import models
from apps.core.models import TimeStampedModel
from config.constants import EXPORT_FORMAT_CHOICES, EXPORT_FORMAT_MARKDOWN

class ExportJob(TimeStampedModel):
    """
    Tracks compilation compilation jobs building PDF/Markdown/JSON exports.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('SUCCEEDED', 'Succeeded'),
        ('FAILED', 'Failed'),
    ]

    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='exports')
    export_format = models.CharField(max_length=20, choices=EXPORT_FORMAT_CHOICES, default=EXPORT_FORMAT_MARKDOWN)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    download_file = models.FileField(upload_to='exports/', blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Export Job {self.id} ({self.export_format}) - {self.status} for {self.project.title}"
