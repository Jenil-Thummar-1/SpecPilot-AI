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
        Assembles approved phase specifications, recent short-term memories,
        and summaries as a single contextual string.
        """
        from apps.generator.models import GeneratedArtifact

        # 1. Load all approved artifacts in order
        approved_arts = GeneratedArtifact.objects.filter(
            project=project,
            is_approved=True
        ).order_by('step__order')
        
        context_parts = []
        
        if approved_arts.exists():
            context_parts.append("--- APPROVED SPECIFICATIONS FROM PREVIOUS PHASES ---")
            for art in approved_arts:
                context_parts.append(
                    f"### Phase {art.step.order if art.step else 'X'}: {art.title}\n"
                    f"{art.content}\n"
                )
            context_parts.append("--- END OF PREVIOUS APPROVED SPECIFICATIONS ---\n")

        # 2. Load summaries or long-term guidance
        long_term_entries = MemoryEntry.objects.filter(
            session__conversation__project=project,
            memory_type__in=[MEMORY_LONG_TERM, MEMORY_SUMMARY]
        ).order_by('-created_at')[:3]

        # 3. Load recent short-term conversation logs
        session = MemoryService.get_or_create_active_session(project)
        short_term_entries = MemoryEntry.objects.filter(
            session=session,
            memory_type=MEMORY_SHORT_TERM
        ).order_by('created_at')[:limit]
        
        if long_term_entries:
            context_parts.append("--- LONG-TERM PROJECT SUMMARIES & DIRECTIVES ---")
            for entry in reversed(long_term_entries):
                context_parts.append(f"Summary Context ({entry.created_at.strftime('%Y-%m-%d')}): {entry.content}")
        
        context_parts.append("--- RECENT INTERACTION HISTORY ---")
        for entry in short_term_entries:
            role_display = "User" if entry.role == "USER" else "Agent"
            context_parts.append(f"{role_display}: {entry.content}")

        return "\n".join(context_parts)

    @staticmethod
    def retrieve_relevant_context(project, query_text, limit=3):
        """
        Retrieves the most semantically relevant memory logs based on query keywords.
        Uses standard case-insensitive SQLite text matching as a vector DB placeholder.
        """
        logger.info(f"Retrieving memory context matching query: '{query_text}'")
        
        entries = MemoryEntry.objects.filter(
            session__conversation__project=project,
            content__icontains=query_text
        ).order_by('-importance_score')[:limit]

        if not entries:
            # Fallback: get recent summaries if keyword yields no matches
            entries = MemoryEntry.objects.filter(
                session__conversation__project=project,
                memory_type=MEMORY_SUMMARY
            ).order_by('-created_at')[:limit]

        return entries

    @staticmethod
    def save_conversation_summary(project, summary_text):
        """
        Concludes planning sprints by saving a SUMMARY memory block to decrease token count.
        """
        logger.info(f"Compiling conversation summary for project: {project.title}")
        return MemoryService.save_memory(
            project=project,
            role="SYSTEM",
            content=summary_text,
            memory_type=MEMORY_SUMMARY,
            importance_score=0.8
        )
