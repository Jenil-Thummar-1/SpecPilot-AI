import uuid
from django.db import models
from apps.core.models import TimeStampedModel
from config.constants import MEMORY_TYPE_CHOICES, ROLE_CHOICES, MEMORY_SHORT_TERM, ROLE_USER

class Conversation(TimeStampedModel):
    """
    Represents an ongoing interaction context linking a user workspace project to memory stores.
    """
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='conversations')
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    def __str__(self):
        return f"Conversation context for Project {self.project.title}"

class Session(TimeStampedModel):
    """
    Groups interaction blocks inside a single project planning run.
    """
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='sessions')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Session {self.id} (Active: {self.is_active}) for Conversation {self.conversation.id}"

class MemoryEntry(TimeStampedModel):
    """
    An entry of user instructions, agent thoughts, tool outputs, or summarized contexts.
    """
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='memories')
    memory_type = models.CharField(max_length=20, choices=MEMORY_TYPE_CHOICES, default=MEMORY_SHORT_TERM)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_USER)
    content = models.TextField()
    importance_score = models.FloatField(default=0.5, help_text="Priority level of this memory block (0.0 to 1.0).")
    
    # Placeholder to store float embeddings as text/JSON in development without requiring custom vector databases
    embedding_placeholder = models.JSONField(default=list, blank=True, help_text="Embeddings representation array.")

    def __str__(self):
        return f"[{self.get_memory_type_display()}] {self.role}: {self.content[:40]}..."
