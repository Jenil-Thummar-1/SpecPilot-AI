import logging
from apps.skills.models import Skill, SkillVersion, SkillExecution

logger = logging.getLogger('specpilot.ai')

class SkillOrchestratorService:
    """
    Service Layer wrapper registering skills, matching inputs, and executing stubs.
    """

    @staticmethod
    def register_skill(name, code_identifier, description, category='General', execution_order=1, dependencies_str='', parameters_schema=None):
        """
        Saves or updates a skill configuration capability.
        """
        skill, created = Skill.objects.update_or_create(
            code_identifier=code_identifier,
            defaults={
                'name': name,
                'description': description,
                'category': category,
                'execution_order': execution_order,
                'dependencies_str': dependencies_str,
                'parameters_schema': parameters_schema or {}
            }
        )
        logger.info(f"Skill '{name}' registered successfully. Created: {created}")
        return skill

    @staticmethod
    def execute_skill(skill_identifier, agent_execution, input_data):
        """
        Simulates executing tool logic (e.g. database schema checks, API mappings).
        Saves execution history and returns stubs.
        """
        try:
            skill = Skill.objects.get(code_identifier=skill_identifier)
        except Skill.DoesNotExist:
            logger.error(f"Skill '{skill_identifier}' is not registered in system.")
            raise ValueError(f"Skill '{skill_identifier}' not found.")

        active_version = skill.versions.filter(is_active=True).first()
        if not active_version:
            active_version = SkillVersion.objects.create(
                skill=skill,
                version='1.0.0',
                prompt_template="Mock prompt template",
                is_active=True
            )

        logger.info(f"Executing skill '{skill.name}' (version: {active_version.version})")
        
        # Mock execution logs & results
        output_data = {
            "result": f"Executed skill '{skill.name}' successfully.",
            "inputs_processed": input_data,
            "status": "SUCCESS",
            "mcp_status": "Ready for model contexts protocol integration"
        }

        execution = SkillExecution.objects.create(
            skill_version=active_version,
            agent_execution=agent_execution,
            input_data=input_data,
            output_data=output_data,
            status='SUCCESS',
            execution_log="[MOCK LOGS] Initialized skill session. Inputs checked. Output generated."
        )

        return execution
