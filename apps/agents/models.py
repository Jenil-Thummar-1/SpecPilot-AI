from django.db import models
from apps.core.models import TimeStampedModel
from config.constants import AGENT_ROLE_CHOICES, AGENT_STATUS_CHOICES, AGENT_STATUS_IDLE, EXEC_STATUS_CHOICES, EXEC_STATUS_RUNNING

class Agent(TimeStampedModel):
    """
    Represents an AI agent with specialized parameters, system instruction scope, and tools.
    """
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=30, choices=AGENT_ROLE_CHOICES)
    description = models.TextField()
    system_prompt = models.TextField(help_text="The core instruction directive guiding the agent's logic.")
    temperature = models.FloatField(default=0.2, help_text="AI creativity control (0.0 for deterministic, 1.0 for creative).")
    skills = models.ManyToManyField('skills.Skill', related_name='agents', blank=True)
    version = models.CharField(max_length=20, default='1.0.0')
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=AGENT_STATUS_CHOICES, default=AGENT_STATUS_IDLE)
    
    # Advanced Enterprise properties
    max_tokens = models.IntegerField(default=4096, help_text="Maximum output bounds permitted for generation.")
    supported_project_types = models.TextField(
        blank=True, 
        default="CRM,HRMS,ERP,ECOMMERCE,AI_AGENT,SAAS,PORTFOLIO,BLOG,HOSPITAL,CUSTOM",
        help_text="Comma-separated templates this agent is allowed to plan."
    )
    config_settings = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="Advanced configuration settings like safety threshold levels, model versions, etc."
    )

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"

class AgentExecution(TimeStampedModel):
    """
    Audit log of agent execution queries, performance metrics, and LLM usage.
    """
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='executions')
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='agent_executions')
    status = models.CharField(max_length=20, choices=EXEC_STATUS_CHOICES, default=EXEC_STATUS_RUNNING)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    execution_time_ms = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Execution {self.id} - {self.agent.name} for Project {self.project.title}"
