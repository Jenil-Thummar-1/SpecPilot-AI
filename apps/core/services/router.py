import hashlib
import logging
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings
from django.core.cache import cache
try:
    from google import generativeai as genai
except Exception:
    genai = None

from config.ai import DEFAULT_GENERATION_CONFIG, SAFETY_SETTINGS

logger = logging.getLogger("specpilot.ai")


@dataclass
class AIProviderResult:
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    elapsed_time_ms: int
    retry_count: int = 0
    quota_status: str = "OK"
    success: bool = True


class AIProvider:
    name = "base"

    def __init__(self, model: str):
        self.model = model

    def health_check(self) -> Dict[str, Any]:
        raise NotImplementedError

    def generate(self, system_instruction: str, prompt: str, temperature: float = 0.2, timeout: int = 180) -> AIProviderResult:
        raise NotImplementedError

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return max(1, len(text or "") // 4)


class OllamaProvider(AIProvider):
    name = "Ollama"
    _last_health: Dict[str, Any] = {}
    _last_health_at = 0.0

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        super().__init__(model or getattr(settings, "OLLAMA_MODEL", "llama3"))
        self.base_url = (base_url or getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")

    def health_check(self) -> Dict[str, Any]:
        now = time.time()
        if self._last_health and now - self._last_health_at < 10:
            return self._last_health
        start = time.time()
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=0.5)
            response.raise_for_status()
            models = response.json().get("models", [])
            model_names = {m.get("name") for m in models}
            model_roots = {str(m.get("name", "")).split(":")[0] for m in models}
            exists = self.model in model_names or self.model.split(":")[0] in model_roots
            result = {
                "available": exists,
                "provider": self.name,
                "model": self.model,
                "base_url": self.base_url,
                "elapsed_time_ms": int((time.time() - start) * 1000),
                "error": "" if exists else f"Configured Ollama model '{self.model}' was not found.",
            }
            self.__class__._last_health = result
            self.__class__._last_health_at = now
            return result
        except Exception as exc:
            result = {
                "available": False,
                "provider": self.name,
                "model": self.model,
                "base_url": self.base_url,
                "elapsed_time_ms": int((time.time() - start) * 1000),
                "error": str(exc),
            }
            self.__class__._last_health = result
            self.__class__._last_health_at = now
            return result

    def generate(self, system_instruction: str, prompt: str, temperature: float = 0.2, timeout: int = 180) -> AIProviderResult:
        start = time.time()
        payload = {
            "model": self.model,
            "system": system_instruction or "",
            "prompt": prompt,
            "options": {"temperature": temperature},
            "stream": False,
        }
        response = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=timeout)
        response.raise_for_status()
        text = response.json().get("response", "")
        if not text:
            raise RuntimeError("Ollama returned an empty response.")
        return AIProviderResult(
            text=text,
            provider=self.name,
            model=self.model,
            input_tokens=self.estimate_tokens((system_instruction or "") + prompt),
            output_tokens=self.estimate_tokens(text),
            elapsed_time_ms=int((time.time() - start) * 1000),
        )


class GeminiProvider(AIProvider):
    name = "Gemini"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        super().__init__(model or getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash"))
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", "")

    def health_check(self) -> Dict[str, Any]:
        if genai is None:
            return {
                "available": False,
                "provider": self.name,
                "model": self.model,
                "error": "google-generativeai package is not installed.",
            }
        return {
            "available": bool(self.api_key and self.api_key != "dummy-api-key-for-now"),
            "provider": self.name,
            "model": self.model,
            "error": "" if self.api_key else "GEMINI_API_KEY is not configured.",
        }

    def generate(self, system_instruction: str, prompt: str, temperature: float = 0.2, timeout: int = 180) -> AIProviderResult:
        if genai is None:
            raise RuntimeError("google-generativeai package is not installed.")
        if not self.api_key or self.api_key == "dummy-api-key-for-now":
            raise RuntimeError("Gemini API key is not configured.")

        start = time.time()
        genai.configure(api_key=self.api_key)
        config = DEFAULT_GENERATION_CONFIG.copy()
        config["temperature"] = temperature
        model = genai.GenerativeModel(
            model_name=self.model,
            generation_config=config,
            safety_settings=SAFETY_SETTINGS,
            system_instruction=system_instruction,
        )
        response = model.generate_content(prompt, request_options={"timeout": timeout})
        text = getattr(response, "text", "") or ""
        if not text:
            raise RuntimeError("Gemini returned an empty response.")

        try:
            input_tokens = model.count_tokens(prompt).total_tokens
            output_tokens = model.count_tokens(text).total_tokens
        except Exception:
            input_tokens = self.estimate_tokens((system_instruction or "") + prompt)
            output_tokens = self.estimate_tokens(text)

        return AIProviderResult(
            text=text,
            provider=self.name,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            elapsed_time_ms=int((time.time() - start) * 1000),
        )


class DevelopmentFallbackProvider(AIProvider):
    name = "DevelopmentFallback"

    def __init__(self):
        super().__init__("offline-deterministic")

    def health_check(self) -> Dict[str, Any]:
        return {"available": True, "provider": self.name, "model": self.model, "error": ""}

    def generate(self, system_instruction: str, prompt: str, temperature: float = 0.2, timeout: int = 180) -> AIProviderResult:
        start = time.time()
        title = "Generated Planning Artifact"
        for line in prompt.splitlines():
            if "document MUST contain" in line or "Your objective" in line:
                title = line.strip()[:90]
                break
        text = (
            f"# {title}\n\n"
            "## Overview\n"
            "This demonstration artifact was generated by the offline deterministic provider because no live AI provider is configured.\n\n"
            "## Functional Scope\n"
            "- Capture project goals, users, workflows, validation rules, and operational constraints.\n"
            "- Preserve approval, versioning, diagnostics, memory, export, and evaluation workflows.\n\n"
            "## Security and Testing\n"
            "- Include authentication, authorization, HTTPS, input validation, audit logging, and recovery checks.\n"
            "- Include unit test, integration test, API test, and end-to-end test coverage expectations.\n\n"
            "## Implementation Readiness\n"
            "The generated structure is intentionally stable for local automated validation and can be replaced by Ollama or Gemini output without changing downstream workflows.\n"
        )
        return AIProviderResult(
            text=text,
            provider=self.name,
            model=self.model,
            input_tokens=self.estimate_tokens((system_instruction or "") + prompt),
            output_tokens=self.estimate_tokens(text),
            elapsed_time_ms=int((time.time() - start) * 1000),
        )


class AIProviderRouter:
    _startup_checked = False
    _ollama_health: Dict[str, Any] = {}
    _gemini_health: Dict[str, Any] = {}
    _failover_history: List[Dict[str, Any]] = []
    _active_provider = "Unknown"
    _active_model = ""
    _last_latency_ms = 0
    _cache_hits = 0
    _cache_misses = 0

    @classmethod
    def startup_check(cls, force: bool = False) -> Dict[str, Any]:
        if cls._startup_checked and not force:
            return cls.get_status()

        ollama = OllamaProvider()
        gemini = GeminiProvider()
        cls._ollama_health = ollama.health_check()
        cls._gemini_health = gemini.health_check()
        cls._startup_checked = True

        if cls._ollama_health.get("available"):
            cls._active_provider = "Ollama"
            cls._active_model = ollama.model
        elif cls._gemini_health.get("available"):
            cls._active_provider = "Gemini"
            cls._active_model = gemini.model
        else:
            cls._active_provider = "DevelopmentFallback" if getattr(settings, "DEBUG", False) else "Unavailable"
            cls._active_model = "offline-deterministic" if getattr(settings, "DEBUG", False) else ""

        logger.info("AI provider startup check: %s", cls.get_status())
        return cls.get_status()

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        return {
            "mode": getattr(settings, "AI_PROVIDER", "auto"),
            "active_provider": cls._active_provider,
            "active_model": cls._active_model,
            "ollama": cls._ollama_health,
            "gemini": cls._gemini_health,
            "failover_events": cls._failover_history[-10:],
            "last_latency_ms": cls._last_latency_ms,
            "cache": {
                "hits": cls._cache_hits,
                "misses": cls._cache_misses,
            },
        }

    @classmethod
    def _provider_chain(cls, api_key: Optional[str] = None, model_name: Optional[str] = None) -> List[AIProvider]:
        cls.startup_check()
        mode = getattr(settings, "AI_PROVIDER", "auto").lower()
        ollama = OllamaProvider()
        gemini = GeminiProvider(api_key=api_key, model=model_name or getattr(settings, "GEMINI_MODEL", None))

        if mode == "gemini":
            chain: List[AIProvider] = [gemini]
        elif mode == "ollama":
            chain = [ollama, gemini]
        else:
            chain = [ollama, gemini]

        if getattr(settings, "DEBUG", False) or "test" in sys.argv:
            chain.append(DevelopmentFallbackProvider())
        return chain

    @classmethod
    def _cache_key(cls, system_instruction: str, prompt: str, temperature: float) -> str:
        raw = f"{getattr(settings, 'AI_PROVIDER', 'auto')}:{getattr(settings, 'OLLAMA_MODEL', '')}:{getattr(settings, 'GEMINI_MODEL', '')}:{temperature}:{system_instruction or ''}:{prompt}"
        return "ai_response_" + hashlib.md5(raw.encode("utf-8")).hexdigest()

    @classmethod
    def route_request(
        cls,
        system_instruction: str,
        prompt: str,
        temperature: float = 0.2,
        target_user=None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        use_cache: bool = True,
        timeout: int = 180,
    ) -> Dict[str, Any]:
        start = time.time()
        prompt_fingerprint = hashlib.md5(f"{system_instruction or ''}:{prompt}".encode("utf-8")).hexdigest()
        cache_key = cls._cache_key(system_instruction or "", prompt, temperature)

        cached = cache.get(cache_key) if use_cache else None
        if cached:
            cls._cache_hits += 1
            cached["cache_hit"] = True
            cached["elapsed_time_ms"] = int((time.time() - start) * 1000)
            return cached
        cls._cache_misses += 1

        user_key = None
        if target_user and hasattr(target_user, "profile") and getattr(target_user.profile, "api_key_override", ""):
            user_key = target_user.profile.api_key_override

        last_error = None
        retry_count = 0
        for provider in cls._provider_chain(api_key=user_key or api_key, model_name=model_name):
            if provider.name == "Ollama":
                health = provider.health_check()
                cls._ollama_health = health
                if not health.get("available"):
                    last_error = RuntimeError(health.get("error", "Ollama is unavailable."))
                    cls._record_failover(provider.name, provider.model, last_error)
                    continue
            elif provider.name == "Gemini":
                health = provider.health_check()
                cls._gemini_health = health
                if not health.get("available"):
                    last_error = RuntimeError(health.get("error", "Gemini is unavailable."))
                    cls._record_failover(provider.name, provider.model, last_error)
                    continue

            for attempt in range(2):
                try:
                    result = provider.generate(system_instruction or "", prompt, temperature, timeout=timeout)
                    result.retry_count = retry_count
                    cls._active_provider = result.provider
                    cls._active_model = result.model
                    cls._last_latency_ms = result.elapsed_time_ms

                    data = {
                        "text": result.text,
                        "provider": result.provider,
                        "model": result.model,
                        "success": True,
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                        "elapsed_time_ms": int((time.time() - start) * 1000),
                        "retry_count": result.retry_count,
                        "quota_status": result.quota_status,
                        "cache_hit": False,
                        "fingerprint": prompt_fingerprint,
                    }
                    if use_cache:
                        cache.set(cache_key, data, 86400)
                    return data
                except Exception as exc:
                    last_error = exc
                    retry_count += 1
                    cls._record_failover(provider.name, provider.model, exc)
                    if attempt == 0 and cls._is_retryable(exc):
                        time.sleep(0.25)
                        continue
                    break

        return {
            "text": "",
            "provider": cls._active_provider,
            "model": cls._active_model,
            "success": False,
            "error": f"All configured AI providers failed. Last error: {last_error}",
            "input_tokens": AIProvider.estimate_tokens((system_instruction or "") + prompt),
            "output_tokens": 0,
            "elapsed_time_ms": int((time.time() - start) * 1000),
            "retry_count": retry_count,
            "quota_status": "ERROR",
            "cache_hit": False,
            "fingerprint": prompt_fingerprint,
        }

    @classmethod
    def _record_failover(cls, provider: str, model: str, exc: Exception):
        cls._failover_history.append({
            "timestamp": time.time(),
            "provider": provider,
            "model": model,
            "error": str(exc)[:240],
        })
        logger.warning("AI provider failure: %s/%s: %s", provider, model, exc)

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(token in msg for token in ["timeout", "temporarily", "connection", "429", "500", "502", "503", "quota"])
