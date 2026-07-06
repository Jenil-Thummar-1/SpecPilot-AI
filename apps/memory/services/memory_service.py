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
    def generate_artifact_summary(step, artifact_content):
        """
        Uses standard/low-cost model (gemini-2.5-flash) to generate a concise summary
        of the artifact content and stores it in the step's metadata['summary'].
        """
        if not artifact_content:
            return ""

        from apps.core.services.gemini_service import GeminiService
        from config.ai import DEFAULT_MODEL_NAME
        
        project = step.project_plan.project
        api_key = None
        if project.user and hasattr(project.user, 'profile') and project.user.profile.api_key_override:
            api_key = project.user.profile.api_key_override

        # Fast model for summarization to be quota friendly and cost effective
        ai_service = GeminiService(api_key=api_key, model_name=DEFAULT_MODEL_NAME)
        
        summary_prompt = (
            f"Generate a highly concise, structured summary (max 200 words) of the following "
            f"planning specification for '{step.title}'. Focus only on key stack choices, database schema highlights, "
            f"endpoints, or business rules that subsequent phases must know. Avoid placeholders, filler, or headers:\n\n"
            f"{artifact_content}"
        )
        
        try:
            res = ai_service.generate_text(
                prompt=summary_prompt,
                system_instruction="You are a senior technical program manager summarizing software specifications.",
                temperature=0.1
            )
            summary_text = res.get("text", "")
            if summary_text:
                if not isinstance(step.metadata, dict):
                    step.metadata = {}
                step.metadata["summary"] = summary_text
                step.save()
                logger.info(f"Saved generated summary for Phase {step.order}: {step.title}")
                return summary_text
        except Exception as e:
            logger.error(f"Failed to generate summary for step {step.title}: {e}")
            
        return ""

    @staticmethod
    def load_context(project, limit=10, current_step=None):
        """
        Assembles approved phase specifications, recent short-term memories,
        and summaries as a single contextual string. Uses dependencies of the current step
        and concise structured summaries to minimize prompt token count.
        """
        from apps.generator.models import GeneratedArtifact

        # 1. Parse dependencies if current_step is provided
        deps_orders = []
        if current_step and current_step.dependencies_str:
            try:
                deps_orders = [int(x.strip()) for x in current_step.dependencies_str.split(',') if x.strip()]
            except ValueError:
                pass

        # Load approved artifacts in order
        approved_arts = GeneratedArtifact.objects.filter(
            project=project,
            is_approved=True
        ).order_by('step__order')
        
        # If we have explicit dependencies, we only load those!
        # Otherwise, load all (fallback for global context)
        if deps_orders:
            approved_arts = approved_arts.filter(step__order__in=deps_orders)
        
        context_parts = []
        
        if approved_arts.exists():
            context_parts.append("--- APPROVED SPECIFICATIONS FROM PREVIOUS PHASES ---")
            for art in approved_arts:
                step = art.step
                summary_text = ""
                
                # Fetch summary from cache (metadata) or generate it
                if step:
                    if not isinstance(step.metadata, dict):
                        step.metadata = {}
                    summary_text = step.metadata.get("summary", "")
                    
                    if not summary_text:
                        summary_text = MemoryService.generate_artifact_summary(step, art.content)
                
                # Fallback to truncated content if no summary was cached or generated
                if not summary_text:
                    summary_text = art.content[:800] + "\n... (truncated)"
                    
                context_parts.append(
                    f"### Phase {art.step.order if art.step else 'X'}: {art.title}\n"
                    f"{summary_text}\n"
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
