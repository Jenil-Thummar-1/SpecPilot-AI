from django.db import models
from apps.core.models import TimeStampedModel
from config.constants import ARTIFACT_TYPE_CHOICES, ARTIFACT_MARKDOWN

class GeneratedArtifact(TimeStampedModel):
    """
    Holds documentation documents, JSON schemas, SQL scripts, and roadmap matrices.
    """
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='artifacts')
    step = models.ForeignKey('planner.PlanStep', on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_artifacts')
    artifact_type = models.CharField(max_length=20, choices=ARTIFACT_TYPE_CHOICES, default=ARTIFACT_MARKDOWN)
    title = models.CharField(max_length=255)
    content = models.TextField(help_text="Raw output string (Markdown, JSON, SQL, or YAML text).")
    file_path = models.CharField(max_length=500, blank=True, null=True, help_text="Path to file storage location if exported.")
    version = models.IntegerField(default=1)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title} (v{self.version}) - {self.get_artifact_type_display()} [Approved: {self.is_approved}]"

