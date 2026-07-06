import time
import logging
import requests
import json
from django.conf import settings
from google import generativeai as genai

logger = logging.getLogger('specpilot.router')

class GeminiKeyRotator:
    """
    Manages multiple Google Gemini API Keys with round-robin rotation, 
    independent cooldown timers, RPM/TPM stats, and health monitoring.
    """
    _keys_metadata = {}

    @classmethod
    def _initialize_keys(cls):
        # Retrieve system-wide keys from settings (can be comma-separated list)
        keys_str = getattr(settings, 'GEMINI_API_KEY', '')
        if not keys_str:
            return []
            
        keys = [k.strip() for k in keys_str.split(',') if k.strip()]
        for key in keys:
            if key not in cls._keys_metadata:
                cls._keys_metadata[key] = {
                    "rpm_history": [],
                    "tpm_history": [],
                    "cooldown_until": 0.0,
                    "success_count": 0,
                    "fail_count": 0
                }
        return keys

    @classmethod
    def get_healthiest_key(cls, estimated_tokens=0):
        keys = cls._initialize_keys()
        if not keys:
            return None

        now = time.time()
        available_keys = []

        for key in keys:
            meta = cls._keys_metadata[key]
            
            # Clean up old window history (last 60s)
            meta["rpm_history"] = [t for t in meta["rpm_history"] if now - t < 60]
            meta["tpm_history"] = [t for t in meta["tpm_history"] if now - t.get("time", 0) < 60]
            
            # Check cooldown status
            if now < meta["cooldown_until"]:
                continue
                
            available_keys.append((key, meta))

        if not available_keys:
            logger.warning("All Gemini keys are currently cooling down.")
            return None

        # Choose the key with the lowest RPM or TPM in the current minute window
        selected_key, selected_meta = min(
            available_keys, 
            key=lambda x: (len(x[1]["rpm_history"]), sum(t["tokens"] for t in x[1]["tpm_history"]))
        )

        return selected_key

    @classmethod
    def report_success(cls, key, tokens=0):
        if key in cls._keys_metadata:
            meta = cls._keys_metadata[key]
            meta["rpm_history"].append(time.time())
            meta["tpm_history"].append({"time": time.time(), "tokens": tokens})
            meta["success_count"] += 1
            meta["cooldown_until"] = 0.0 # reset cooldown

    @classmethod
    def report_failure(cls, key, is_quota_error=True):
        if key in cls._keys_metadata:
            meta = cls._keys_metadata[key]
            meta["fail_count"] += 1
            if is_quota_error:
                # Put key on a 60s cooldown if quota/rate limited
                meta["cooldown_until"] = time.time() + 60.0
                logger.warning(f"Gemini Key ...{key[-6:] if len(key) > 6 else 'key'} marked with cooldown for 60s.")


class BaseProvider:
    def generate(self, system_instruction, prompt, temperature=0.2, timeout=60):
        raise NotImplementedError()


class GeminiProvider(BaseProvider):
    def __init__(self, api_key):
        self.api_key = api_key

    def generate(self, system_instruction, prompt, temperature=0.2, timeout=60):
        genai.configure(api_key=self.api_key)
        config = {
            "temperature": temperature,
            "max_output_tokens": 8192
        }
        # Safely reuse models
        model = genai.GenerativeModel(
            model_name="gemini-2.5-pro",
            generation_config=config,
            system_instruction=system_instruction
        )
        response = model.generate_content(prompt)
        return response.text


class OpenAIProvider(BaseProvider):
    def __init__(self, api_key):
        self.api_key = api_key

    def generate(self, system_instruction, prompt, temperature=0.2, timeout=60):
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": system_instruction or "You are a helpful software engineering assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }
        res = requests.post(url, headers=headers, json=data, timeout=timeout)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]


class ClaudeProvider(BaseProvider):
    def __init__(self, api_key):
        self.api_key = api_key

    def generate(self, system_instruction, prompt, temperature=0.2, timeout=60):
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        data = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 4096,
            "system": system_instruction or "You are a helpful software engineering assistant.",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }
        res = requests.post(url, headers=headers, json=data, timeout=timeout)
        res.raise_for_status()
        return res.json()["content"][0]["text"]


class OpenRouterProvider(BaseProvider):
    def __init__(self, api_key):
        self.api_key = api_key

    def generate(self, system_instruction, prompt, temperature=0.2, timeout=60):
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "google/gemini-2.5-pro",
            "messages": [
                {"role": "system", "content": system_instruction or "You are a helpful software engineering assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }
        res = requests.post(url, headers=headers, json=data, timeout=timeout)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]


class GroqProvider(BaseProvider):
    def __init__(self, api_key):
        self.api_key = api_key

    def generate(self, system_instruction, prompt, temperature=0.2, timeout=60):
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "llama3-70b-8192",
            "messages": [
                {"role": "system", "content": system_instruction or "You are a helpful software engineering assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }
        res = requests.post(url, headers=headers, json=data, timeout=timeout)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]


class OllamaProvider(BaseProvider):
    def __init__(self, host="http://localhost:11434"):
        self.host = host

    def generate(self, system_instruction, prompt, temperature=0.2, timeout=60):
        url = f"{self.host}/api/generate"
        data = {
            "model": "llama3",
            "system": system_instruction or "You are a helpful software engineering assistant.",
            "prompt": prompt,
            "options": {"temperature": temperature},
            "stream": False
        }
        res = requests.post(url, json=data, timeout=timeout)
        res.raise_for_status()
        return res.json()["response"]


class AIProviderRouter:
    """
    Unified router resolving model fallback across Gemini (with multi-key rotation), 
    OpenAI, Claude, OpenRouter, Groq, and Ollama.
    """
    _failover_history = []
    _active_provider = "Gemini"
    _active_model = "gemini-2.5-pro"

    @classmethod
    def get_status(cls):
        return {
            "active_provider": cls._active_provider,
            "active_model": cls._active_model,
            "failover_events": cls._failover_history[-5:]
        }

    @classmethod
    def route_request(cls, system_instruction, prompt, temperature=0.2, target_user=None):
        start_time = time.time()
        
        # Determine fallback chain order based on keys set in environment
        providers_chain = [
            ("Gemini", "gemini-2.5-pro"),
            ("OpenAI", "gpt-4o"),
            ("Claude", "claude-3-5-sonnet"),
            ("OpenRouter", "gemini-2.5-pro"),
            ("Groq", "llama3-70b"),
            ("Ollama", "llama3")
        ]
        
        last_error = None
        
        for provider_name, model_name in providers_chain:
            try:
                # 1. Handle Gemini key rotation fallback
                if provider_name == "Gemini":
                    # If user has customized key override, check that first
                    api_key = None
                    if target_user and hasattr(target_user, 'profile') and target_user.profile.api_key_override:
                        api_key = target_user.profile.api_key_override
                        
                    if not api_key:
                        api_key = GeminiKeyRotator.get_healthiest_key(len(prompt) // 4)
                        
                    if not api_key or api_key == "dummy-api-key-for-now":
                        # Skip if no real keys
                        continue
                        
                    cls._active_provider = "Gemini"
                    cls._active_model = "gemini-2.5-pro"
                    
                    try:
                        provider = GeminiProvider(api_key)
                        output = provider.generate(system_instruction, prompt, temperature)
                        GeminiKeyRotator.report_success(api_key, len(prompt) // 4)
                        return {
                            "text": output,
                            "provider": provider_name,
                            "model": model_name,
                            "success": True
                        }
                    except Exception as gemini_err:
                        # Report fail and try next key (or next provider)
                        is_quota = "429" in str(gemini_err) or "quota" in str(gemini_err).lower()
                        GeminiKeyRotator.report_failure(api_key, is_quota_error=is_quota)
                        raise gemini_err

                # 2. OpenAI Fallback
                elif provider_name == "OpenAI":
                    api_key = getattr(settings, 'OPENAI_API_KEY', '')
                    if not api_key:
                        continue
                    cls._active_provider = "OpenAI"
                    cls._active_model = "gpt-4o"
                    provider = OpenAIProvider(api_key)
                    
                # 3. Claude Fallback
                elif provider_name == "Claude":
                    api_key = getattr(settings, 'CLAUDE_API_KEY', '')
                    if not api_key:
                        continue
                    cls._active_provider = "Claude"
                    cls._active_model = "claude-3-5-sonnet"
                    provider = ClaudeProvider(api_key)

                # 4. OpenRouter Fallback
                elif provider_name == "OpenRouter":
                    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
                    if not api_key:
                        continue
                    cls._active_provider = "OpenRouter"
                    cls._active_model = "gemini-2.5-pro"
                    provider = OpenRouterProvider(api_key)

                # 5. Groq Fallback
                elif provider_name == "Groq":
                    api_key = getattr(settings, 'GROQ_API_KEY', '')
                    if not api_key:
                        continue
                    cls._active_provider = "Groq"
                    cls._active_model = "llama3-70b"
                    provider = GroqProvider(api_key)

                # 6. Ollama Fallback (Ollama usually runs locally without keys)
                elif provider_name == "Ollama":
                    host = getattr(settings, 'OLLAMA_HOST', 'http://localhost:11434')
                    cls._active_provider = "Ollama"
                    cls._active_model = "llama3"
                    provider = OllamaProvider(host)

                # Execute provider request
                logger.info(f"Routing request to provider: {provider_name} ({model_name})")
                output = provider.generate(system_instruction, prompt, temperature)
                return {
                    "text": output,
                    "provider": provider_name,
                    "model": model_name,
                    "success": True
                }

            except Exception as provider_err:
                msg = f"Provider {provider_name} failed: {str(provider_err)}"
                logger.warning(msg)
                cls._failover_history.append({
                    "timestamp": time.time(),
                    "provider": provider_name,
                    "error": str(provider_err)
                })
                last_error = provider_err

        # If all fail, raise exception or fallback to mock simulation mode
        raise RuntimeError(f"All configured cloud providers failed. Last error: {last_error}")
