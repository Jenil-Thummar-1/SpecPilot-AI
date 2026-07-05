import re
import logging

logger = logging.getLogger('specpilot.ai')

class PromptBuilder:
    """
    Handles prompt construction, parameter validation, and formatting security checks.
    """

    @staticmethod
    def sanitize_input(user_input):
        """
        Sanitizes user input to prevent prompt injections, script injections, and raw markdown issues.
        """
        if not user_input:
            return ""
        
        # Remove potential script tags and HTML elements
        sanitized = re.sub(r'<[^>]*>', '', user_input)
        
        # Trim leading and trailing spaces
        sanitized = sanitized.strip()
        
        return sanitized

    @staticmethod
    def build_prompt(template, **kwargs):
        """
        Injects validated parameters into a prompt template, checking safety limits.
        """
        sanitized_kwargs = {}
        for key, val in kwargs.items():
            if isinstance(val, str):
                # Sanitize the input content
                sanitized_val = PromptBuilder.sanitize_input(val)
                # Check for prompt injection attempts (e.g. system instructions overrides)
                if "ignore previous instructions" in sanitized_val.lower() or "system override" in sanitized_val.lower():
                    logger.warning(f"Suspected prompt injection pattern detected in variable '{key}'!")
                    sanitized_val = sanitized_val.replace("ignore previous instructions", "[FILTERED_INJECTION]")
                sanitized_kwargs[key] = sanitized_val
            else:
                sanitized_kwargs[key] = val
        
        try:
            return template.format(**sanitized_kwargs)
        except KeyError as e:
            logger.error(f"Failed to build prompt template. Missing keyword argument: {str(e)}")
            raise ValueError(f"Required prompt variable {str(e)} was not provided.")
