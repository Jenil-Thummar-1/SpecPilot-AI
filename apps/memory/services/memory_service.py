import logging
import re
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
    def index_document_sections(step, artifact_content):
        """
        Splits the markdown artifact into sections by headers and classifies
        them into categories for future semantic phase filtering.
        """
        if not artifact_content:
            return []

        sections = []
        current_title = "Introduction"
        current_lines = []
        
        for line in artifact_content.split('\n'):
            header_match = re.match(r'^#+\s+(.*)', line)
            if header_match:
                if current_lines:
                    sections.append({
                        "title": current_title,
                        "content": "\n".join(current_lines).strip()
                    })
                current_title = header_match.group(1).strip()
                current_lines = []
            else:
                current_lines.append(line)
        if current_lines:
            sections.append({
                "title": current_title,
                "content": "\n".join(current_lines).strip()
            })

        indexed_sections = []
        for sec in sections:
            content_lower = sec["content"].lower()
            category = "GENERAL"
            if any(k in content_lower for k in ["auth", "login", "user", "role", "permissions"]):
                category = "AUTH"
            elif any(k in content_lower for k in ["database", "sql", "schema", "table", "pk", "fk"]):
                category = "DATABASE"
            elif any(k in content_lower for k in ["api", "endpoint", "route", "http", "json"]):
                category = "API"
            elif any(k in content_lower for k in ["security", "encryption", "owasp", "cors", "token"]):
                category = "SECURITY"
            elif any(k in content_lower for k in ["deploy", "docker", "ci/cd", "server", "host"]):
                category = "DEPLOYMENT"
            elif any(k in content_lower for k in ["feature", "workflow", "screen", "epic"]):
                category = "FEATURES"
            elif any(k in content_lower for k in ["arch", "pattern", "layer", "mermaid"]):
                category = "ARCH"

            indexed_sections.append({
                "title": sec["title"],
                "category": category,
                "content": sec["content"]
            })

        if not isinstance(step.metadata, dict):
            step.metadata = {}
        step.metadata["indexed_sections"] = indexed_sections
        step.save()
        logger.info(f"Successfully categorized & indexed {len(indexed_sections)} sections for Step '{step.title}'")
        return indexed_sections

    @staticmethod
    def extract_and_update_knowledge_store(project, step, artifact_content):
        """
        Extracts structured facts/decisions from the approved artifact and merges them into the project knowledge store.
        Uses gemini-2.5-flash for lightweight extraction.
        """
        if not artifact_content:
            return

        if not isinstance(project.metadata, dict):
            project.metadata = {}
        if 'knowledge_store' not in project.metadata:
            project.metadata['knowledge_store'] = {
                "facts": [], "decisions": [], "constraints": [], "business_rules": [],
                "entities": [], "glossary": {}, "architecture_decisions": [],
                "assumptions": [], "tech_stack": {}, "user_roles": [],
                "apis": [], "database_entities": [], "project_metadata": {}
            }

        existing_store = project.metadata['knowledge_store']

        # If dummy key, simulate basic extraction
        api_key = None
        if project.user and hasattr(project.user, 'profile') and project.user.profile.api_key_override:
            api_key = project.user.profile.api_key_override
            
        if not api_key or api_key == "dummy-api-key-for-now":
            # Seed basic mock facts
            existing_store["facts"].append(f"Completed Phase {step.order}: {step.title}")
            project.metadata['knowledge_store'] = existing_store
            project.save()
            return

        from apps.core.services.gemini_service import GeminiService
        from config.ai import DEFAULT_MODEL_NAME
        import json

        ai_service = GeminiService(api_key=api_key, model_name=DEFAULT_MODEL_NAME)
        extraction_prompt = (
            f"Analyze the following approved specification artifact for '{step.title}'. "
            f"Extract any new facts, decisions, constraints, business rules, entities, glossary terms, "
            f"architecture decisions, assumptions, tech stack details, user roles, APIs, and database entities. "
            f"Format the output as a valid raw JSON dictionary ONLY, with keys matching the existing store keys. "
            f"Do not include any markdown headers, tags or chat filler:\n\n"
            f"Existing Store:\n{json.dumps(existing_store)}\n\n"
            f"Artifact Content:\n{artifact_content}"
        )
        
        try:
            res = ai_service.generate_text(
                prompt=extraction_prompt,
                system_instruction="You are an AI data extractor. You only return raw, minified JSON dictionaries.",
                temperature=0.1
            )
            extracted_json = res.get("text", "").strip()
            # Clean markdown formatting if present
            if extracted_json.startswith("```"):
                extracted_json = extracted_json.split("```")[1]
                if extracted_json.startswith("json"):
                    extracted_json = extracted_json[4:]
            extracted_json = extracted_json.strip()

            new_data = json.loads(extracted_json)
            # Merge list keys
            for k in ["facts", "decisions", "constraints", "business_rules", "entities", "architecture_decisions", "assumptions", "user_roles", "apis", "database_entities"]:
                if k in new_data and isinstance(new_data[k], list):
                    for item in new_data[k]:
                        if item not in existing_store[k]:
                            existing_store[k].append(item)
            # Merge dict keys
            for k in ["glossary", "tech_stack", "project_metadata"]:
                if k in new_data and isinstance(new_data[k], dict):
                    existing_store[k].update(new_data[k])

            project.metadata['knowledge_store'] = existing_store
            project.save()
            logger.info(f"Successfully updated Project Knowledge Store after approving step '{step.title}'")
        except Exception as e:
            logger.error(f"Failed to extract knowledge store update: {e}")

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
        Loads a list of structured context document dictionaries.
        Resolves the Prompt Dependency Graph using step.dependencies_str to filter items,
        combines with Project Knowledge Store, and ranks by priority.
        """
        from apps.generator.models import GeneratedArtifact

        context_list = []

        # 1. Load the Structured Project Knowledge Store (Priority 8)
        if not isinstance(project.metadata, dict):
            project.metadata = {}
        
        knowledge_store = project.metadata.get('knowledge_store', {})
        if knowledge_store:
            store_parts = []
            for category, items in knowledge_store.items():
                if items:
                    if isinstance(items, list):
                        store_parts.append(f"### {category.replace('_', ' ').title()}:\n" + "\n".join(f"- {x}" for x in items[:8]))
                    elif isinstance(items, dict):
                        store_parts.append(f"### {category.replace('_', ' ').title()}:\n" + "\n".join(f"- {k}: {v}" for k, v in list(items.items())[:8]))
            if store_parts:
                context_list.append({
                    "title": "Project Knowledge Store",
                    "content": "\n\n".join(store_parts),
                    "priority": 8,
                    "reason": "Structured project decisions and definitions"
                })

        # 2. Resolve Prompt Dependency Graph using step.dependencies_str
        deps_orders = []
        if current_step and current_step.dependencies_str:
            try:
                deps_orders = [int(x.strip()) for x in current_step.dependencies_str.split(',') if x.strip()]
            except ValueError:
                pass

        approved_arts = GeneratedArtifact.objects.filter(
            project=project,
            is_approved=True
        ).order_by('step__order')

        # Map current step type to relevant section category indexing
        target_section_category = "GENERAL"
        if current_step:
            step_slug = current_step.step_type
            if "database" in step_slug.lower() or "db" in step_slug.lower():
                target_section_category = "DATABASE"
            elif "api" in step_slug.lower() or "endpoint" in step_slug.lower():
                target_section_category = "API"
            elif "security" in step_slug.lower():
                target_section_category = "SECURITY"
            elif "deploy" in step_slug.lower():
                target_section_category = "DEPLOYMENT"
            elif "story" in step_slug.lower() or "prd" in step_slug.lower():
                target_section_category = "FEATURES"
            elif "arch" in step_slug.lower():
                target_section_category = "ARCH"

        # Load dependency artifacts
        for art in approved_arts:
            step = art.step
            if not step:
                continue

            is_direct_dependency = step.order in deps_orders
            
            # Rank priority: Direct dependencies = 10, Indirect = 4
            priority = 10 if is_direct_dependency else 4
            reason = f"Direct Dependency (Phase {step.order})" if is_direct_dependency else f"Indirect Phase {step.order} context"

            # Check if we have indexed sections matching the target category (Priority booster +3)
            if not isinstance(step.metadata, dict):
                step.metadata = {}
            
            indexed_sections = step.metadata.get("indexed_sections", [])
            relevant_section_content = ""
            if indexed_sections and target_section_category != "GENERAL":
                matching_sections = [s for s in indexed_sections if s["category"] == target_section_category]
                if matching_sections:
                    relevant_section_content = "\n\n".join(f"### {s['title']}\n{s['content']}" for s in matching_sections)
                    priority += 3  # Boost priority for highly relevant sections!
                    reason += f" (Indexed {target_section_category} relevance boost)"

            # Get summary of artifact
            summary_text = step.metadata.get("summary", "")
            if not summary_text:
                summary_text = MemoryService.generate_artifact_summary(step, art.content)
            
            if not summary_text:
                summary_text = art.content[:800]

            # Compile content: if we have highly relevant indexed sections, append them to the summary
            final_content = summary_text
            if relevant_section_content:
                final_content = f"{summary_text}\n\n[RELEVANT {target_section_category} DETAILS]:\n{relevant_section_content}"

            context_list.append({
                "title": f"Phase {step.order}: {step.title}",
                "content": final_content,
                "priority": priority,
                "reason": reason
            })

        # 3. Load recent short-term conversation logs (Priority 3)
        session = MemoryService.get_or_create_active_session(project)
        short_term_entries = MemoryEntry.objects.filter(
            session=session,
            memory_type=MEMORY_SHORT_TERM
        ).order_by('created_at')[:limit]

        st_content_parts = []
        for entry in short_term_entries:
            role_display = "User" if entry.role == "USER" else "Agent"
            st_content_parts.append(f"{role_display}: {entry.content}")

        if st_content_parts:
            context_list.append({
                "title": "Recent Chat History",
                "content": "\n".join(st_content_parts),
                "priority": 3,
                "reason": "Recent Sprint Interaction Memory"
            })

        return context_list

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
