from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel
from config.constants import (
    PROJECT_STATUS_CHOICES, PROJECT_STATUS_PLANNING, 
    ARCH_CHOICES, ARCH_MONOLITH,
    TEMPLATE_CHOICES, TEMPLATE_CUSTOM
)

class Project(TimeStampedModel):
    """
    Represents a software project idea being planned and architected by SpecPilot AI.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='projects')
    title = models.CharField(max_length=255)
    short_description = models.CharField(max_length=500, blank=True, help_text="A brief outline of the project's purpose.")
    description = models.TextField(help_text="Detailed description of the software idea, target features, and workflows.")
    category = models.CharField(
        max_length=50, 
        choices=TEMPLATE_CHOICES, 
        default=TEMPLATE_CUSTOM,
        help_text="Predefined project template category."
    )
    target_users = models.TextField(
        blank=True, 
        help_text="Describe the primary personas and target audiences for this software."
    )
    tech_stack = models.TextField(
        blank=True, 
        help_text="Identify the primary languages, frameworks, databases, and third-party tools to use."
    )
    target_architecture = models.CharField(
        max_length=30, 
        choices=ARCH_CHOICES, 
        default=ARCH_MONOLITH,
        help_text="Target system architectural style."
    )
    deployment_preference = models.CharField(
        max_length=100, 
        default='Docker / VPS',
        help_text="E.g., Docker container, Heroku, AWS serverless, bare-metal VPS."
    )
    status = models.CharField(
        max_length=20, 
        choices=PROJECT_STATUS_CHOICES, 
        default=PROJECT_STATUS_PLANNING
    )
    current_version = models.IntegerField(default=1, help_text="Increments on every saved update to support rollbacks.")
    metadata = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="Custom key-value parameters like tech stack configurations, deployment environments, etc."
    )

    def __str__(self):
        return f"{self.title} (v{self.current_version})"

class ProjectVersion(TimeStampedModel):
    """
    Holds serialized snapshots of the project for configuration history and future rollback options.
    """
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField()
    title = models.CharField(max_length=255)
    short_description = models.CharField(max_length=500, blank=True)
    description = models.TextField()
    snapshot_data = models.JSONField(help_text="Serialized state of the project configuration, details, and planning steps.")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-version_number']
        unique_together = ('project', 'version_number')

    def __str__(self):
        return f"Version {self.version_number} of {self.project.title}"

class ActivityLog(models.Model):
    """
    Automatically tracks user and AI actions performed on the project workspace.
    """
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='activities')
    action_type = models.CharField(max_length=50, help_text="E.g., CREATED, EDITED, STAGE_UPDATED, DUPLICATED, ARCHIVED, RESTORED")
    description = models.TextField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.action_type}] on {self.project.title} by {self.user.username if self.user else 'System'}"
