import logging
import time
from django.conf import settings
from config.ai import SAFETY_SETTINGS, DEFAULT_GENERATION_CONFIG, DEFAULT_MODEL_NAME, ADVANCED_MODEL_NAME
from google import generativeai as genai

logger = logging.getLogger('specpilot.ai')

class GeminiService:
    """
    Service layer client wrapper for the Google Gemini API.
    Handles configuration, validation, metrics tracking, and API calls.
    """

    def __init__(self, api_key=None, model_name=None):
        self.api_key = api_key or getattr(settings, 'GEMINI_API_KEY', '')
        self.model_name = model_name or DEFAULT_MODEL_NAME
        
        if self.api_key:
            genai.configure(api_key=self.api_key)
        else:
            logger.warning("GeminiService initialized without a valid GEMINI_API_KEY. Using fallback mockup mode.")

    def generate_text(self, prompt, system_instruction=None, temperature=0.2):
        """
        Sends a generation request to the Gemini API.
        Tracks execution latency and token metrics.
        """
        start_time = time.time()
        logger.info(f"Initiating Gemini request using model: {self.model_name}")

        if not self.api_key or self.api_key == "dummy-api-key-for-now":
            logger.info("Gemini API Key is dummy/empty. Simulating API response for development.")
            elapsed_time_ms = int((time.time() - start_time) * 1000)
            mock_text = f"**[MOCK AI ARCHITECT RESPONSE]**\nThis is a mock response from the Gemini API.\nPrompt received length: {len(prompt)} characters."
            return {
                "text": mock_text,
                "input_tokens": len(prompt) // 4,
                "output_tokens": len(mock_text) // 4,
                "elapsed_time_ms": elapsed_time_ms,
                "success": True
            }

        try:
            # Prepare configuration overrides
            config = DEFAULT_GENERATION_CONFIG.copy()
            config["temperature"] = temperature

            # Initialize model
            model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=config,
                safety_settings=SAFETY_SETTINGS,
                system_instruction=system_instruction
            )

            # Call API
            response = model.generate_content(prompt)
            
            elapsed_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Gemini request completed in {elapsed_time_ms}ms")

            # Extract token details if available
            input_tokens = 0
            output_tokens = 0
            try:
                # API exposes token count methods
                input_tokens = model.count_tokens(prompt).total_tokens
                output_tokens = model.count_tokens(response.text).total_tokens
            except Exception as token_err:
                logger.debug(f"Could not calculate token counts: {str(token_err)}")
                # Quick fallback estimate
                input_tokens = len(prompt) // 4
                output_tokens = len(response.text) // 4

            return {
                "text": response.text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "elapsed_time_ms": elapsed_time_ms,
                "success": True
            }

        except Exception as e:
            # Fallback to gemini-1.5-flash if the primary model fails (e.g. 404 models/gemini-1.5-pro is not found)
            if self.model_name != "gemini-1.5-flash":
                logger.warning(f"Primary model {self.model_name} failed: {str(e)}. Falling back to gemini-1.5-flash.")
                try:
                    config = DEFAULT_GENERATION_CONFIG.copy()
                    config["temperature"] = temperature
                    fallback_model = genai.GenerativeModel(
                        model_name="gemini-1.5-flash",
                        generation_config=config,
                        safety_settings=SAFETY_SETTINGS,
                        system_instruction=system_instruction
                    )
                    response = fallback_model.generate_content(prompt)
                    elapsed_time_ms = int((time.time() - start_time) * 1000)
                    logger.info(f"Fallback Gemini request completed in {elapsed_time_ms}ms")
                    
                    try:
                        input_tokens = fallback_model.count_tokens(prompt).total_tokens
                        output_tokens = fallback_model.count_tokens(response.text).total_tokens
                    except Exception:
                        input_tokens = len(prompt) // 4
                        output_tokens = len(response.text) // 4

                    return {
                        "text": response.text,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "elapsed_time_ms": elapsed_time_ms,
                        "success": True
                    }
                except Exception as fallback_err:
                    logger.error(f"Fallback model gemini-1.5-flash also failed: {str(fallback_err)}")
                    e = fallback_err

            elapsed_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Gemini API request failed: {str(e)}")
            return {
                "text": "",
                "error": str(e),
                "input_tokens": 0,
                "output_tokens": 0,
                "elapsed_time_ms": elapsed_time_ms,
                "success": False
            }
