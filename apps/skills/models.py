from django.db import models
from apps.core.models import TimeStampedModel

class Skill(TimeStampedModel):
    """
    Represents a discrete AI capability or utility (e.g. SQL Schema generation, API modeling).
    Compatible with Model Context Protocol (MCP) tooling.
    """
    name = models.CharField(max_length=100)
    code_identifier = models.CharField(max_length=100, unique=True, help_text="Unique programmatic slug e.g. 'generate_prd'")
    description = models.TextField()
    parameters_schema = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="JSON Schema definition of the input parameters required by this tool."
    )
    
    # Advanced Enterprise properties
    category = models.CharField(
        max_length=50, 
        default='General', 
        help_text="Category groupings e.g. 'Database', 'API', 'Requirements'."
    )
    execution_order = models.IntegerField(
        default=1, 
        help_text="Execution sequence order within agent pipeline logic."
    )
    dependencies_str = models.CharField(
        max_length=200, 
        blank=True, 
        help_text="Comma-separated skill slugs required prior to executing this skill."
    )

    def __str__(self):
        return self.name

class SkillVersion(TimeStampedModel):
    """
    Tracks prompt updates and template modifications version history.
    """
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='versions')
    version = models.CharField(max_length=20, default='1.0.0')
    prompt_template = models.TextField(help_text="Prompt instructions containing variables to render.")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.skill.name} - Version {self.version}"

class SkillExecution(TimeStampedModel):
    """
    Execution record auditing inputs, outputs, and status logs of skill calls.
    """
    STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('FAILURE', 'Failure'),
    ]

    skill_version = models.ForeignKey(SkillVersion, on_delete=models.CASCADE, related_name='executions')
    agent_execution = models.ForeignKey(
        'agents.AgentExecution', 
        on_delete=models.CASCADE, 
        related_name='skill_executions',
        null=True,
        blank=True
    )
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='SUCCESS')
    execution_log = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"SkillExec {self.id} ({self.skill_version.skill.name}) - {self.status}"
