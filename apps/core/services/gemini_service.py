"""
Backward-compatible AI service facade.

Business workflows historically imported GeminiService directly. The class now
delegates every generation request to AIProviderRouter so provider selection is
centralized and invisible to users.
"""
import logging

from django.conf import settings

from apps.core.services.router import AIProviderRouter

logger = logging.getLogger("specpilot.ai")


class GeminiService:
    def __init__(self, api_key=None, model_name=None):
        self.api_key = api_key
        self.model_name = model_name or getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")

    def generate_text(self, prompt, system_instruction=None, temperature=0.2, step_id=999):
        max_request_tokens = getattr(settings, "GEMINI_MAX_REQUEST_TOKENS", 30000)
        estimated_tokens = (len(prompt or "") + len(system_instruction or "")) // 4
        if estimated_tokens > max_request_tokens:
            return {
                "text": "",
                "error": f"Request token estimate ({estimated_tokens}) exceeds configured maximum ({max_request_tokens}).",
                "input_tokens": estimated_tokens,
                "output_tokens": 0,
                "elapsed_time_ms": 0,
                "retry_count": 0,
                "quota_status": "EXCEEDED",
                "success": False,
                "cache_hit": False,
                "provider": "Router",
                "model": self.model_name,
            }

        return AIProviderRouter.route_request(
            system_instruction=system_instruction or "",
            prompt=prompt or "",
            temperature=temperature,
            api_key=self.api_key,
            model_name=self.model_name,
        )
