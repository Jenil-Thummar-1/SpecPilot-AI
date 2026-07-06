import logging
import time
from django.utils import timezone
from django.db import transaction

from apps.agents.models import Agent, AgentExecution
from apps.planner.models import PlanStep
from apps.generator.models import GeneratedArtifact

# Services
from apps.memory.services.memory_service import MemoryService
from apps.core.services.prompt_builder import PromptBuilder
from apps.evaluation.services.evaluation_service import EvaluationService
from apps.planner.services.planner_service import PlannerService
from apps.core.services.gemini_service import GeminiService

# Prompts & Constants
import config.prompts as prompts_library
from config.constants import (
    AGENT_ROLE_ARCHITECT, AGENT_ROLE_PLANNER, AGENT_ROLE_QA, AGENT_ROLE_WRITER,
    MEMORY_SHORT_TERM,
    STEP_IDEA, STEP_REQUIREMENTS, STEP_PRD, STEP_USER_STORIES, STEP_FUNCTIONAL, STEP_NON_FUNCTIONAL,
    STEP_ARCHITECTURE, STEP_DATABASE, STEP_API, STEP_FOLDER_STRUCTURE, STEP_ROADMAP, STEP_SECURITY,
    STEP_TESTING, STEP_DEPLOYMENT, STEP_EXPORT_PREP
)

logger = logging.getLogger('specpilot.ai')

class AgentOrchestratorService:
    """
    Coordinates planning pipeline sequences: loading memory context, formatting templates, 
    matching tool skills, validating outputs, calling Gemini with retries, and logging execution metrics.
    """

    @staticmethod
    @transaction.atomic
    def execute_pipeline(step_id, user):
        """
        Executes the FSM pipeline for a specific lifecycle phase.
        Sets up the execution context, templates, and runs Gemini generation.
        """
        step = PlanStep.objects.get(id=step_id)
        project = step.project_plan.project
        start_time = time.time()
        
        logger.info(f"Agent Orchestrator Pipeline initiated for step '{step.title}' on project '{project.title}'")

        # 1. Start Planner FSM step state (Sets status to RUNNING)
        PlannerService.start_step(step)

        # 2. Map stage types to templates and roles
        prompt_templates = {
            STEP_REQUIREMENTS: (prompts_library.REQUIREMENTS_PROMPT, AGENT_ROLE_ARCHITECT),
            STEP_PRD: (prompts_library.PRD_PROMPT, AGENT_ROLE_WRITER),
            STEP_USER_STORIES: (prompts_library.USER_STORIES_PROMPT, AGENT_ROLE_PLANNER),
            STEP_FUNCTIONAL: (prompts_library.FUNCTIONAL_PROMPT, AGENT_ROLE_ARCHITECT),
            STEP_NON_FUNCTIONAL: (prompts_library.NON_FUNCTIONAL_PROMPT, AGENT_ROLE_ARCHITECT),
            STEP_ARCHITECTURE: (prompts_library.ARCHITECTURE_PROMPT, AGENT_ROLE_ARCHITECT),
            STEP_DATABASE: (prompts_library.DATABASE_PROMPT, AGENT_ROLE_ARCHITECT),
            STEP_API: (prompts_library.API_PROMPT, AGENT_ROLE_ARCHITECT),
            STEP_FOLDER_STRUCTURE: (prompts_library.FOLDER_STRUCTURE_PROMPT, AGENT_ROLE_ARCHITECT),
            STEP_ROADMAP: (prompts_library.ROADMAP_PROMPT, AGENT_ROLE_PLANNER),
            STEP_SECURITY: (prompts_library.SECURITY_PROMPT, AGENT_ROLE_ARCHITECT),
            STEP_TESTING: (prompts_library.TESTING_PROMPT, AGENT_ROLE_QA),
            STEP_DEPLOYMENT: (prompts_library.DEPLOYMENT_PROMPT, AGENT_ROLE_QA),
        }

        # Step 15 Fallback (Export Preparation)
        if step.step_type == STEP_EXPORT_PREP:
            mock_content = f"# Export Compilation Package\nProject: {project.title}\nStatus: Ready for download."
            
            latest_art = GeneratedArtifact.objects.filter(project=project, step=step).order_by('-version').first()
            next_ver = (latest_art.version + 1) if latest_art else 1

            artifact = GeneratedArtifact.objects.create(
                project=project,
                step=step,
                artifact_type='TEXT',
                title=step.title,
                content=mock_content,
                version=next_ver,
                is_approved=True  # Export prep compiles directly and is auto-approved
            )
            PlannerService.complete_step(step, notes="Export preparation compiled successfully.")
            return {
                "success": True,
                "text": mock_content,
                "notes": "Export compilation prepared."
            }

        if step.step_type not in prompt_templates:
            error_msg = f"No prompt template mapped for stage slug: '{step.step_type}'"
            PlannerService.fail_step(step, error_message=error_msg)
            raise ValueError(error_msg)

        template, agent_role = prompt_templates[step.step_type]

        # 3. Retrieve or spawn active Agent config
        agent = Agent.objects.filter(role=agent_role, is_active=True).first()
        if not agent:
            agent = Agent.objects.create(
                name=f"Default {agent_role.title()} Agent",
                role=agent_role,
                description="Auto-spawned agent role module.",
                system_prompt="Standard architectural planning instruction directive."
            )

        # 4. Initialize Execution Audit Record
        execution = AgentExecution.objects.create(
            agent=agent,
            project=project,
            status='RUNNING'
        )

        try:
            # 5. Load memory logs context
            memory_context = MemoryService.load_context(project)

            # 6. Format prompt template values
            if step.step_type == STEP_REQUIREMENTS:
                prompt = PromptBuilder.build_prompt(
                    template,
                    idea=project.description,
                    architecture=project.get_target_architecture_display()
                )
            else:
                prompt = PromptBuilder.build_prompt(
                    template,
                    context_doc=memory_context
                )

            # 7. Collect skills assigned to the agent
            skills = agent.skills.all()
            skills_list = [skill.code_identifier for skill in skills]

            # 8. Assemble execution request metadata (AI-ready configuration)
            system_prompt_attr = f"SYSTEM_PROMPT_{step.step_type}"
            system_prompt = getattr(prompts_library, system_prompt_attr, agent.system_prompt)

            execution_request = {
                "agent_name": agent.name,
                "role": agent.role,
                "system_prompt": system_prompt,
                "prompt": prompt,
                "temperature": agent.temperature,
                "max_tokens": agent.max_tokens,
                "skills_allocated": skills_list,
                "config_settings": agent.config_settings
            }

            # 9. Instantiate Gemini Client & Run with Retries
            api_key = None
            if hasattr(user, 'profile') and user.profile.api_key_override:
                api_key = user.profile.api_key_override

            from config.ai import ADVANCED_MODEL_NAME
            ai_service = GeminiService(
                api_key=api_key,
                model_name=ADVANCED_MODEL_NAME
            )

            max_retries = 3
            response = None
            for attempt in range(max_retries):
                try:
                    response = ai_service.generate_text(
                        prompt=prompt,
                        system_instruction=system_prompt,
                        temperature=agent.temperature
                    )
                    if response.get("success", False):
                        break
                    else:
                        logger.warning(f"Gemini API attempt {attempt + 1} failed: {response.get('error')}")
                        if attempt == max_retries - 1:
                            raise Exception(response.get("error", "API request failed after retries."))
                        time.sleep(1.5)
                except Exception as retry_ex:
                    if attempt == max_retries - 1:
                        raise retry_ex
                    time.sleep(1.5)

            generated_text = response["text"]
            elapsed_time_ms = response.get("elapsed_time_ms", int((time.time() - start_time) * 1000))

            # 10. Versioning control on new artifact creations
            latest_art = GeneratedArtifact.objects.filter(project=project, step=step).order_by('-version').first()
            next_ver = (latest_art.version + 1) if latest_art else 1

            # Save generated artifact (is_approved defaults to False, prompting user review workflow)
            artifact = GeneratedArtifact.objects.create(
                project=project,
                step=step,
                artifact_type='MARKDOWN',
                title=step.title,
                content=generated_text,
                version=next_ver,
                is_approved=False
            )

            # Save output back into Short-Term memory logs
            MemoryService.save_memory(
                project=project,
                role="AGENT",
                content=f"Generated Output for Phase {step.title}:\n{generated_text}",
                memory_type=MEMORY_SHORT_TERM
            )

            # Perform quality check audits
            EvaluationService.evaluate_artifact(execution, generated_text, step.title)

            # Conclude execution metrics
            execution.input_tokens = response.get("input_tokens", len(prompt) // 4)
            execution.output_tokens = response.get("output_tokens", len(generated_text) // 4)
            execution.execution_time_ms = elapsed_time_ms
            execution.status = 'SUCCEEDED'
            execution.save()

            # Note: We do NOT set the step as COMPLETED yet. It remains in RUNNING status 
            # until approved by the user, locking the FSM sequence as desired.
            step.notes = f"Generation completed. Pending architect approval (v{next_ver})."
            step.save()

            return {
                "success": True,
                "text": generated_text,
                "execution_id": execution.id,
                "request_payload": execution_request,
                "artifact_id": artifact.id
            }

        except Exception as e:
            elapsed_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Execution failed in pipeline step '{step.title}': {str(e)}")
            
            execution.status = 'FAILED'
            execution.error_message = str(e)
            execution.execution_time_ms = elapsed_time_ms
            execution.save()

            PlannerService.fail_step(step, error_message=str(e))
            raise e
