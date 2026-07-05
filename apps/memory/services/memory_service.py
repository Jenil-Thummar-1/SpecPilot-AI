import logging
from apps.memory.models import Conversation, Session, MemoryEntry
from apps.projects.models import Project
from config.constants import MEMORY_SHORT_TERM, MEMORY_LONG_TERM, MEMORY_SUMMARY

logger = logging.getLogger('specpilot.ai')

class MemoryService:
    """
    Manages short-term and long-term AI context loading, conversation history, and summarization.
    """

    @staticmethod
    def get_or_create_active_session(project):
        """
        Retrieves or spawns an active conversation session for a project.
        """
        conversation, _ = Conversation.objects.get_or_create(project=project)
        session = conversation.sessions.filter(is_active=True).first()
        if not session:
            session = Session.objects.create(conversation=conversation, is_active=True)
            logger.info(f"Created new active memory session {session.id} for project '{project.title}'")
        return session

    @staticmethod
    def save_memory(project, role, content, memory_type=MEMORY_SHORT_TERM, importance_score=0.5):
        """
        Saves an interaction or summary item as a MemoryEntry.
        """
        session = MemoryService.get_or_create_active_session(project)
        entry = MemoryEntry.objects.create(
            session=session,
            memory_type=memory_type,
            role=role,
            content=content,
            importance_score=importance_score
        )
        logger.debug(f"Saved memory entry {entry.id} of type {memory_type} for project '{project.title}'")
        return entry

    @staticmethod
    def load_context(project, limit=10):
        """
        Assembles recent short-term memories and summaries as a single contextual string.
        """
        session = MemoryService.get_or_create_active_session(project)
        
        # Load summaries or long-term guidance
        long_term_entries = MemoryEntry.objects.filter(
            session__conversation__project=project,
            memory_type__in=[MEMORY_LONG_TERM, MEMORY_SUMMARY]
        ).order_by('-created_at')[:3]

        # Load recent short-term conversation logs
        short_term_entries = MemoryEntry.objects.filter(
            session=session,
            memory_type=MEMORY_SHORT_TERM
        ).order_by('created_at')[:limit]

        # Assemble string representation
        context_parts = []
        
        if long_term_entries:
            context_parts.append("--- LONG-TERM PROJECT SUMMARIES & DIRECTIVES ---")
            for entry in reversed(long_term_entries):
                context_parts.append(f"Summary Context ({entry.created_at.strftime('%Y-%m-%d')}): {entry.content}")
        
        context_parts.append("--- RECENT INTERACTION HISTORY ---")
        for entry in short_term_entries:
            role_display = "User" if entry.role == "USER" else "Agent"
            context_parts.append(f"{role_display}: {entry.content}")

        return "\n".join(context_parts)
