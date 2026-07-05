from django.db import models
from apps.core.models import TimeStampedModel
from config.constants import EVAL_STATUS_CHOICES, EVAL_STATUS_PASSED, METRIC_CHOICES, METRIC_COMPLETENESS

class Evaluation(TimeStampedModel):
    """
    Validation audit block analyzing an agent's execution output quality.
    """
    agent_execution = models.ForeignKey('agents.AgentExecution', on_delete=models.CASCADE, related_name='evaluations')
    evaluator_name = models.CharField(max_length=100, default='LLM-Compliance-Guard')
    status = models.CharField(max_length=20, choices=EVAL_STATUS_CHOICES, default=EVAL_STATUS_PASSED)

    def __str__(self):
        return f"Evaluation {self.id} (Status: {self.status}) for Exec {self.agent_execution.id}"

class QualityScore(TimeStampedModel):
    """
    Specific grade scores for compliance, feasibility, clarity, and completeness metrics.
    """
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='scores')
    metric_name = models.CharField(max_length=30, choices=METRIC_CHOICES, default=METRIC_COMPLETENESS)
    score = models.DecimalField(max_digits=4, decimal_places=2, help_text="Score rating from 0.00 to 10.00")
    rationalization = models.TextField(blank=True, null=True, help_text="AI's explanation for the assigned score.")

    def __str__(self):
        return f"{self.get_metric_name_display()}: {self.score}/10"

class AgentFeedback(TimeStampedModel):
    """
    Captures human user review ratings and corrections on specific generated artifacts.
    """
    RATING_CHOICES = [(i, f"{i} Stars") for i in range(1, 6)]

    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='feedbacks')
    artifact = models.ForeignKey('generator.GeneratedArtifact', on_delete=models.CASCADE, related_name='feedbacks')
    rating = models.IntegerField(choices=RATING_CHOICES, default=5)
    feedback_text = models.TextField(blank=True, null=True, help_text="User comments or specifications modifications requests.")
    is_resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"Feedback on {self.artifact.title} - {self.rating} Stars"
