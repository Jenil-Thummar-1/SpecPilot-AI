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

    @classmethod
    def execute_sequential_generation(cls, step, context_doc, system_prompt, temperature, ai_service):
        """
        Sequentially generates large documents in multiple phases to fit constraints.
        """
        logger.info(f"Running sequential generation for large step: {step.title}")
        
        aggregated_text = ""
        total_input_tokens = 0
        total_output_tokens = 0
        total_time_ms = 0
        total_retries = 0
        final_quota_status = "OK"
        
        if step.step_type == STEP_USER_STORIES:
            # 1. Generate Story Index
            index_prompt = (
                f"Analyze the following PRD and context. Generate a logical Epic breakdown and a list of all "
                f"User Stories for this project. Specify ONLY the Epic names, User Story IDs (e.g. US-01, US-02), "
                f"Titles, Story statements (As a... I want to... so that...), and story point estimates. "
                f"DO NOT write the Gherkin acceptance criteria yet. Keep it structured:\n\n"
                f"Context:\n{context_doc}"
            )
            res = ai_service.generate_text(prompt=index_prompt, system_instruction=system_prompt, temperature=temperature)
            if not res.get("success"):
                raise Exception(res.get("error", "Failed to generate User Stories index."))
                
            story_index = res["text"]
            total_input_tokens += res["input_tokens"]
            total_output_tokens += res["output_tokens"]
            total_time_ms += res["elapsed_time_ms"]
            total_retries += res.get("retry_count", 0)
            
            # 2. Generate detailed Gherkin acceptance criteria in chunks
            details_prompt = (
                f"Based on the PRD context, write the complete, detailed User Stories (including full Given-When-Then "
                f"acceptance criteria, Normal/Alternative flows, and validation rules) for the stories listed below. "
                f"Use this index to guide the generation:\n\n"
                f"Story Index:\n{story_index}\n\n"
                f"Context:\n{context_doc}\n\n"
                f"Task: Generate detailed criteria for the FIRST HALF of the stories (e.g., US-01 through US-05)."
            )
            res2 = ai_service.generate_text(prompt=details_prompt, system_instruction=system_prompt, temperature=temperature)
            if not res2.get("success"):
                raise Exception(res2.get("error", "Failed to generate detailed User Stories part 1."))
                
            details_part1 = res2["text"]
            total_input_tokens += res2["input_tokens"]
            total_output_tokens += res2["output_tokens"]
            total_time_ms += res2["elapsed_time_ms"]
            total_retries += res2.get("retry_count", 0)
            
            details_prompt2 = (
                f"Based on the PRD context, write the complete, detailed User Stories (including full Given-When-Then "
                f"acceptance criteria, Normal/Alternative flows, and validation rules) for the stories listed below. "
                f"Use this index to guide the generation:\n\n"
                f"Story Index:\n{story_index}\n\n"
                f"Context:\n{context_doc}\n\n"
                f"Task: Generate detailed criteria for the SECOND HALF of the stories (e.g., US-06 and onwards)."
            )
            res3 = ai_service.generate_text(prompt=details_prompt2, system_instruction=system_prompt, temperature=temperature)
            if not res3.get("success"):
                raise Exception(res3.get("error", "Failed to generate detailed User Stories part 2."))
                
            details_part2 = res3["text"]
            total_input_tokens += res3["input_tokens"]
            total_output_tokens += res3["output_tokens"]
            total_time_ms += res3["elapsed_time_ms"]
            total_retries += res3.get("retry_count", 0)
            
            # Merge
            aggregated_text = (
                f"# Epic & Story Outline\n\n{story_index}\n\n"
                f"# User Stories Details - Part 1\n\n{details_part1}\n\n"
                f"# User Stories Details - Part 2\n\n{details_part2}"
            )
            
        elif step.step_type == STEP_FUNCTIONAL:
            # 1. Generate Requirements index
            index_prompt = (
                f"Analyze the User Stories and PRD. Generate a complete index of all Functional Requirements "
                f"for this system (categorized into User Management/Auth, Core Data CRUD, APIs, Background Tasks, and UI). "
                f"List only the Requirement IDs (e.g. FR-AUTH-01, FR-CORE-01) and Titles. "
                f"DO NOT write the detailed descriptions or parameters yet:\n\n"
                f"Context:\n{context_doc}"
            )
            res = ai_service.generate_text(prompt=index_prompt, system_instruction=system_prompt, temperature=temperature)
            if not res.get("success"):
                raise Exception(res.get("error", "Failed to generate Functional Requirements index."))
                
            req_index = res["text"]
            total_input_tokens += res["input_tokens"]
            total_output_tokens += res["output_tokens"]
            total_time_ms += res["elapsed_time_ms"]
            total_retries += res.get("retry_count", 0)
            
            # 2. Generate details in chunks
            details_prompt = (
                f"Based on the index and context, write the complete, detailed specification for the FIRST HALF "
                f"of the Functional Requirements (such as FR-AUTH and FR-CORE). Specify Requirement ID, Title, Description "
                f"of system response, inputs, outputs, validation constraints, and error flows:\n\n"
                f"Requirements Index:\n{req_index}\n\n"
                f"Context:\n{context_doc}"
            )
            res2 = ai_service.generate_text(prompt=details_prompt, system_instruction=system_prompt, temperature=temperature)
            if not res2.get("success"):
                raise Exception(res2.get("error", "Failed to generate detailed Functional Requirements part 1."))
                
            details_part1 = res2["text"]
            total_input_tokens += res2["input_tokens"]
            total_output_tokens += res2["output_tokens"]
            total_time_ms += res2["elapsed_time_ms"]
            total_retries += res2.get("retry_count", 0)
            
            details_prompt2 = (
                f"Based on the index and context, write the complete, detailed specification for the SECOND HALF "
                f"of the Functional Requirements (such as FR-API, FR-JOB, FR-UI). Specify Requirement ID, Title, Description "
                f"of system response, inputs, outputs, validation constraints, and error flows:\n\n"
                f"Requirements Index:\n{req_index}\n\n"
                f"Context:\n{context_doc}"
            )
            res3 = ai_service.generate_text(prompt=details_prompt2, system_instruction=system_prompt, temperature=temperature)
            if not res3.get("success"):
                raise Exception(res3.get("error", "Failed to generate detailed Functional Requirements part 2."))
                
            details_part2 = res3["text"]
            total_input_tokens += res3["input_tokens"]
            total_output_tokens += res3["output_tokens"]
            total_time_ms += res3["elapsed_time_ms"]
            total_retries += res3.get("retry_count", 0)
            
            aggregated_text = (
                f"# Functional Requirements Index\n\n{req_index}\n\n"
                f"# Functional Requirements Specifications - Part 1\n\n{details_part1}\n\n"
                f"# Functional Requirements Specifications - Part 2\n\n{details_part2}"
            )
            
        elif step.step_type == STEP_API:
            # 1. Generate API Standards & Route Definitions table
            index_prompt = (
                f"Analyze the system context and design a complete RESTful/GraphQL API. "
                f"Generate a standards overview and a complete Route Definitions Table (Method, Path, Auth Required, Description). "
                f"DO NOT include the full JSON payloads yet:\n\n"
                f"Context:\n{context_doc}"
            )
            res = ai_service.generate_text(prompt=index_prompt, system_instruction=system_prompt, temperature=temperature)
            if not res.get("success"):
                raise Exception(res.get("error", "Failed to generate API Route table."))
                
            route_table = res["text"]
            total_input_tokens += res["input_tokens"]
            total_output_tokens += res["output_tokens"]
            total_time_ms += res["elapsed_time_ms"]
            total_retries += res.get("retry_count", 0)
            
            # 2. Generate payloads in chunks
            details_prompt = (
                f"Based on the route table and system context, write the complete request/response JSON payloads "
                f"and error codes for the top 3 critical API endpoints:\n\n"
                f"Route Table:\n{route_table}\n\n"
                f"Context:\n{context_doc}"
            )
            res2 = ai_service.generate_text(prompt=details_prompt, system_instruction=system_prompt, temperature=temperature)
            if not res2.get("success"):
                raise Exception(res2.get("error", "Failed to generate API payloads part 1."))
                
            payloads_part1 = res2["text"]
            total_input_tokens += res2["input_tokens"]
            total_output_tokens += res2["output_tokens"]
            total_time_ms += res2["elapsed_time_ms"]
            total_retries += res2.get("retry_count", 0)
            
            details_prompt2 = (
                f"Based on the route table and system context, write the complete request/response JSON payloads, "
                f"rate limiting limits, error codes, and standardized error response schema for the remaining critical API endpoints:\n\n"
                f"Route Table:\n{route_table}\n\n"
                f"Context:\n{context_doc}"
            )
            res3 = ai_service.generate_text(prompt=details_prompt2, system_instruction=system_prompt, temperature=temperature)
            if not res3.get("success"):
                raise Exception(res3.get("error", "Failed to generate API payloads part 2."))
                
            payloads_part2 = res3["text"]
            total_input_tokens += res3["input_tokens"]
            total_output_tokens += res3["output_tokens"]
            total_time_ms += res3["elapsed_time_ms"]
            total_retries += res3.get("retry_count", 0)
            
            aggregated_text = (
                f"# API Standards & Routes\n\n{route_table}\n\n"
                f"# API Endpoint Details - Part 1\n\n{payloads_part1}\n\n"
                f"# API Endpoint Details - Part 2\n\n{payloads_part2}"
            )
            
        else:
            # Fallback
            res = ai_service.generate_text(prompt=context_doc, system_instruction=system_prompt, temperature=temperature)
            return res

        return {
            "text": aggregated_text,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "elapsed_time_ms": total_time_ms,
            "retry_count": total_retries,
            "quota_status": final_quota_status,
            "success": True
        }

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
            # 5. Load memory logs context (passing current step reference!)
            memory_context = MemoryService.load_context(project, current_step=step)

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

            # 9. Instantiate Gemini Client
            api_key = None
            if hasattr(user, 'profile') and user.profile.api_key_override:
                api_key = user.profile.api_key_override

            from config.ai import ADVANCED_MODEL_NAME
            ai_service = GeminiService(
                api_key=api_key,
                model_name=ADVANCED_MODEL_NAME
            )

            is_large_step = step.step_type in [STEP_USER_STORIES, STEP_FUNCTIONAL, STEP_API]
            is_mock_mode = not api_key or api_key == "dummy-api-key-for-now"

            if is_large_step and not is_mock_mode:
                response = AgentOrchestratorService.execute_sequential_generation(
                    step=step,
                    context_doc=memory_context,
                    system_prompt=system_prompt,
                    temperature=agent.temperature,
                    ai_service=ai_service
                )
            else:
                response = ai_service.generate_text(
                    prompt=prompt,
                    system_instruction=system_prompt,
                    temperature=agent.temperature
                )

            if not response.get("success", False):
                raise Exception(response.get("error", "API request failed."))

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
            execution.retry_count = response.get("retry_count", 0)
            execution.quota_status = response.get("quota_status", "OK")
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
            execution.retry_count = response.get("retry_count", 0) if (locals().get("response") and isinstance(response, dict)) else 0
            execution.quota_status = response.get("quota_status", "ERROR") if (locals().get("response") and isinstance(response, dict)) else "ERROR"
            execution.save()

            PlannerService.fail_step(step, error_message=str(e))
            raise e
