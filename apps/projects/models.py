from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel
from config.constants import PROJECT_STATUS_CHOICES, PROJECT_STATUS_DRAFT, ARCH_CHOICES, ARCH_MONOLITH

class Project(TimeStampedModel):
    """
    Represents a software idea being planned and architected by SpecPilot AI.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='projects')
    title = models.CharField(max_length=255)
    description = models.TextField(help_text="Provide details about the software idea, target features, and workflows.")
    target_architecture = models.CharField(
        max_length=30, 
        choices=ARCH_CHOICES, 
        default=ARCH_MONOLITH,
        help_text="Target system architectural style."
    )
    status = models.CharField(
        max_length=20, 
        choices=PROJECT_STATUS_CHOICES, 
        default=PROJECT_STATUS_DRAFT
    )
    metadata = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="Custom key-value parameters like tech stack selections, deployment environments, etc."
    )

    def __str__(self):
        return self.title
