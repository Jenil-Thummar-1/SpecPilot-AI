import logging
import time
import os
import threading
import hashlib
import random
from django.conf import settings
from django.core.cache import cache
from config.ai import SAFETY_SETTINGS, DEFAULT_GENERATION_CONFIG, DEFAULT_MODEL_NAME, ADVANCED_MODEL_NAME
from google import generativeai as genai
from apps.core.services.profiler import PerformanceProfiler

logger = logging.getLogger('specpilot.ai')

class AIRequestQueue:
    """
    Guarantees thread-safe and process-safe multi-slot execution locks.
    Allows up to 4 concurrent Gemini API requests to execute in parallel.
    """
    _max_slots = 4
    _lock = threading.Semaphore(_max_slots)
    _local = threading.local()

    @classmethod
    def acquire(cls, timeout=180):
        start_time = time.time()
        cls._lock.acquire()
        
        log_dir = os.path.join(settings.BASE_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        while True:
            for slot in range(cls._max_slots):
                slot_file = os.path.join(log_dir, f'ai_request_{slot}.lock')
                
                # Clean stale lock
                if os.path.exists(slot_file):
                    mtime = os.path.getmtime(slot_file)
                    if time.time() - mtime > 180:
                        try:
                            os.remove(slot_file)
                        except Exception:
                            pass
                
                try:
                    fd = os.open(slot_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.write(fd, f"{time.time()}:{os.getpid()}".encode())
                    os.close(fd)
                    
                    cls._local.acquired_slot = slot
                    return True
                except FileExistsError:
                    continue
            
            if time.time() - start_time > timeout:
                cls._lock.release()
                raise TimeoutError("Timed out waiting for AI execution queue slot.")
            time.sleep(0.1)

    @classmethod
    def release(cls):
        slot = getattr(cls._local, 'acquired_slot', None)
        if slot is not None:
            log_dir = os.path.join(settings.BASE_DIR, 'logs')
            slot_file = os.path.join(log_dir, f'ai_request_{slot}.lock')
            try:
                if os.path.exists(slot_file):
                    os.remove(slot_file)
            except Exception:
                pass
            cls._local.acquired_slot = None
        cls._lock.release()


class AIRateLimiter:
    """
    Database/Execution-backed rate limiter that automatically slows down execution 
    whenever requests approach Google Gemini Free Tier limits.
    """
    @staticmethod
    def wait_if_needed(estimated_tokens=0):
        max_rpm = getattr(settings, 'GEMINI_MAX_RPM', 15)  # Free Tier max RPM is 15
        max_tpm = getattr(settings, 'GEMINI_MAX_TPM', 60000) # Increased budget for parallel demo mode
        
        from apps.agents.models import AgentExecution
        from django.utils import timezone
        import datetime
        
        now = timezone.now()
        one_minute_ago = now - datetime.timedelta(seconds=60)
        
        recent_execs = AgentExecution.objects.filter(
            created_at__gte=one_minute_ago
        ).order_by('created_at')
        
        # 1. RPM Check
        if recent_execs.count() >= max_rpm:
            oldest_exec = recent_execs.first()
            elapsed = (now - oldest_exec.created_at).total_seconds()
            wait_time = max(0.2, 60.0 - elapsed)
            if wait_time > 0:
                logger.warning(f"Rate Limiter: Approaching RPM limit ({recent_execs.count()}/{max_rpm}). Pausing for {wait_time:.2f}s...")
                time.sleep(wait_time)
                return AIRateLimiter.wait_if_needed(estimated_tokens)

        # 2. TPM Check
        total_recent_tokens = sum(e.input_tokens + e.output_tokens for e in recent_execs)
        if total_recent_tokens + estimated_tokens > max_tpm:
            oldest_exec = recent_execs.first()
            elapsed = (now - oldest_exec.created_at).total_seconds()
            wait_time = max(0.2, 60.0 - elapsed)
            if wait_time > 0:
                logger.warning(f"Rate Limiter: Approaching TPM limit ({total_recent_tokens + estimated_tokens} > {max_tpm}). Pausing for {wait_time:.2f}s...")
                time.sleep(wait_time)
                return AIRateLimiter.wait_if_needed(estimated_tokens)


def extract_retry_delay(exc):
    """
    Attempts to read structured retry details from the Google API client error.
    """
    details = getattr(exc, 'details', None)
    if details:
        for detail in getattr(details, 'value', []):
            if hasattr(detail, 'retry_delay'):
                return detail.retry_delay.seconds + detail.retry_delay.nanos / 1e9
    
    response = getattr(exc, 'response', None)
    if response and hasattr(response, 'headers'):
        retry_after = response.headers.get('Retry-After')
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
                
    import re
    msg = str(exc)
    match = re.search(r'(?:wait|retry after|limit exceeded for)\s*([\d\.]+)\s*(?:s|sec|seconds)', msg, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
            
    return None


def is_retryable_exception(exc):
    """
    Returns True if the exception corresponds to a retryable status code (429, 500, 502, 503) or timeout.
    """
    code = getattr(exc, 'code', None)
    if code in [429, 500, 502, 503]:
        return True
        
    import requests
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
        
    exc_name = exc.__class__.__name__
    if exc_name in ['ResourceExhausted', 'InternalServerError', 'ServiceUnavailable', 'DeadlineExceeded']:
        return True
        
    msg = str(exc).lower()
    if '429' in msg or '500' in msg or '502' in msg or '503' in msg or 'rate limit' in msg or 'quota' in msg or 'timeout' in msg or 'deadline' in msg:
        return True
        
    return False


class GeminiService:
    """
    Service layer client wrapper for the Google Gemini API.
    Handles configuration, validation, metrics tracking, caching, queueing, and retry loops.
    """
    _model_cache = {}

    def __init__(self, api_key=None, model_name=None):
        self.api_key = api_key or getattr(settings, 'GEMINI_API_KEY', '')
        self.model_name = model_name or DEFAULT_MODEL_NAME
        
        if self.api_key:
            genai.configure(api_key=self.api_key)
        else:
            logger.warning("GeminiService initialized without a valid GEMINI_API_KEY. Using fallback mockup mode.")

    def _get_model(self, system_instruction, temperature):
        """
        Reuses instantiated GenerativeModel configurations to save HTTP handshake overhead.
        """
        cache_key = f"{self.model_name}:{system_instruction or ''}:{temperature}"
        if cache_key not in self._model_cache:
            config = DEFAULT_GENERATION_CONFIG.copy()
            config["temperature"] = temperature
            self._model_cache[cache_key] = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=config,
                safety_settings=SAFETY_SETTINGS,
                system_instruction=system_instruction
            )
        return self._model_cache[cache_key]

    def generate_text(self, prompt, system_instruction=None, temperature=0.2, step_id=999):
        """
        Sends a generation request to the Gemini API with pre-flight budgeting,
        centralized locks, rate limiting, and response caching.
        """
        start_time = time.time()
        
        # 1. Pre-flight Token Budget Estimation
        estimated_tokens = (len(prompt) + len(system_instruction or "")) // 4
        max_request_tokens = getattr(settings, 'GEMINI_MAX_REQUEST_TOKENS', 30000)
        
        input_str = f"{self.model_name}:{system_instruction or ''}:{prompt}"
        prompt_fingerprint = hashlib.md5(input_str.encode('utf-8')).hexdigest()
        cache_key = f"gemini_response_{prompt_fingerprint}"
        
        if estimated_tokens > max_request_tokens:
            error_msg = f"Request token count estimation ({estimated_tokens}) exceeds the maximum allowed limit of {max_request_tokens} tokens. Please compress the input context."
            logger.error(error_msg)
            return {
                "text": "",
                "error": error_msg,
                "input_tokens": 0,
                "output_tokens": 0,
                "elapsed_time_ms": int((time.time() - start_time) * 1000),
                "retry_count": 0,
                "quota_status": "EXCEEDED",
                "success": False,
                "cache_hit": False,
                "fingerprint": prompt_fingerprint
            }

        # 2. Response Caching
        if self.api_key and self.api_key != "dummy-api-key-for-now":
            cached_val = cache.get(cache_key)
            if cached_val:
                logger.info("Cache hit for Gemini request. Returning cached response.")
                cached_val["elapsed_time_ms"] = int((time.time() - start_time) * 1000)
                cached_val["cache_hit"] = True
                cached_val["fingerprint"] = prompt_fingerprint
                return cached_val

        # Simulation Mode
        if not self.api_key or self.api_key == "dummy-api-key-for-now":
            logger.info("Gemini API Key is dummy/empty. Simulating API response for development.")
            elapsed_time_ms = int((time.time() - start_time) * 1000)
            mock_text = f"**[MOCK AI ARCHITECT RESPONSE]**\nThis is a mock response from the Gemini API.\nPrompt received length: {len(prompt)} characters."
            result = {
                "text": mock_text,
                "input_tokens": estimated_tokens,
                "output_tokens": len(mock_text) // 4,
                "elapsed_time_ms": elapsed_time_ms,
                "retry_count": 0,
                "quota_status": "OK",
                "success": True,
                "cache_hit": False,
                "fingerprint": prompt_fingerprint
            }
            return result

        # 3. Unified AI Routing fallbacks
        from apps.core.services.router import AIProviderRouter, GeminiKeyRotator
        keys = GeminiKeyRotator._initialize_keys()
        
        # Check if other providers are configured (OpenAI, Claude, etc.)
        other_configured = any(getattr(settings, f"{p}_API_KEY", "") for p in ["OPENAI", "CLAUDE", "OPENROUTER", "GROQ"])
        
        if (keys or other_configured) and self.api_key != "dummy-api-key-for-now":
            logger.info("Routing request through Enterprise AI Provider Router...")
            try:
                with PerformanceProfiler(step_id, "AI Provider Routing"):
                    res = AIProviderRouter.route_request(
                        system_instruction=system_instruction,
                        prompt=prompt,
                        temperature=temperature
                    )
                
                elapsed_time_ms = int((time.time() - start_time) * 1000)
                text_out = res["text"]
                
                response_data = {
                    "text": text_out,
                    "input_tokens": estimated_tokens,
                    "output_tokens": len(text_out) // 4,
                    "elapsed_time_ms": elapsed_time_ms,
                    "retry_count": 0,
                    "quota_status": "OK",
                    "success": True,
                    "cache_hit": False,
                    "fingerprint": prompt_fingerprint,
                    "provider": res["provider"],
                    "model": res["model"]
                }
                if cache_key:
                    cache.set(cache_key, response_data, 86400)
                return response_data
            except Exception as routing_err:
                logger.error(f"AI Provider Routing failed: {routing_err}. Attempting recovery in standard client...")

        # 4. Centralized Queue & Rate Limiter fallback block
        logger.info("Waiting for AI Request Queue lock...")
        with PerformanceProfiler(step_id, "Wait for Concurrency Lock"):
            AIRequestQueue.acquire()
        
        max_retries = getattr(settings, 'GEMINI_MAX_RETRIES', 5)
        retry_attempts = 0
        final_quota_status = "OK"
        response_data = None
        
        try:
            AIRateLimiter.wait_if_needed(estimated_tokens)
            
            # Start retry loop
            for attempt in range(max_retries + 1):
                try:
                    logger.info(f"Initiating Gemini request using model: {self.model_name} (Attempt {attempt + 1})")
                    
                    with PerformanceProfiler(step_id, "Gemini Generation"):
                        model = self._get_model(system_instruction, temperature)
                        response = model.generate_content(prompt)
                        extracted_text = response.text
                    
                    elapsed_time_ms = int((time.time() - start_time) * 1000)
                    logger.info(f"Gemini request completed in {elapsed_time_ms}ms")
 
                    # Calculate tokens
                    input_tokens = 0
                    output_tokens = 0
                    try:
                        input_tokens = model.count_tokens(prompt).total_tokens
                        output_tokens = model.count_tokens(extracted_text).total_tokens
                    except Exception:
                        input_tokens = estimated_tokens
                        output_tokens = len(extracted_text) // 4
 
                    response_data = {
                        "text": extracted_text,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "elapsed_time_ms": elapsed_time_ms,
                        "retry_count": retry_attempts,
                        "quota_status": final_quota_status,
                        "success": True,
                        "cache_hit": False,
                        "fingerprint": prompt_fingerprint,
                        "provider": "Gemini",
                        "model": self.model_name
                    }
                    
                    # Cache result
                    if cache_key:
                        cache.set(cache_key, response_data, 86400)
                        
                    break
 
                except Exception as e:
                    if is_retryable_exception(e) and attempt < max_retries:
                        retry_attempts += 1
                        final_quota_status = "RATE_LIMITED" if ("429" in str(e) or "quota" in str(e).lower()) else "ERROR"
                        
                        delay = extract_retry_delay(e)
                        if delay is None:
                            delay = 2.0 * (2.0 ** attempt) + random.uniform(0.1, 1.0)
                            
                        logger.warning(f"Gemini API attempt failed with retryable error: {str(e)}. Retrying in {delay:.2f}s...")
                        time.sleep(delay)
                    else:
                        final_quota_status = "EXCEEDED" if ("429" in str(e) or "quota" in str(e).lower()) else "ERROR"
                        raise e
        except Exception as primary_err:
            if self.model_name != DEFAULT_MODEL_NAME:
                logger.warning(f"Primary model {self.model_name} failed: {str(primary_err)}. Trying fallback {DEFAULT_MODEL_NAME}.")
                try:
                    with PerformanceProfiler(step_id, "Gemini Fallback Generation"):
                        fallback_model = genai.GenerativeModel(
                            model_name=DEFAULT_MODEL_NAME,
                            generation_config=DEFAULT_GENERATION_CONFIG,
                            safety_settings=SAFETY_SETTINGS,
                            system_instruction=system_instruction
                        )
                        response = fallback_model.generate_content(prompt)
                        elapsed_time_ms = int((time.time() - start_time) * 1000)
                    
                    try:
                        input_tokens = fallback_model.count_tokens(prompt).total_tokens
                        output_tokens = fallback_model.count_tokens(response.text).total_tokens
                    except Exception:
                        input_tokens = estimated_tokens
                        output_tokens = len(response.text) // 4

                    response_data = {
                        "text": response.text,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "elapsed_time_ms": elapsed_time_ms,
                        "retry_count": retry_attempts,
                        "quota_status": final_quota_status,
                        "success": True,
                        "cache_hit": False,
                        "fingerprint": prompt_fingerprint
                    }
                    if cache_key:
                        cache.set(cache_key, response_data, 86400)
                except Exception as fallback_err:
                    logger.error(f"Fallback model also failed: {str(fallback_err)}")
                    elapsed_time_ms = int((time.time() - start_time) * 1000)
                    response_data = {
                        "text": "",
                        "error": str(fallback_err),
                        "input_tokens": estimated_tokens,
                        "output_tokens": 0,
                        "elapsed_time_ms": elapsed_time_ms,
                        "retry_count": retry_attempts,
                        "quota_status": final_quota_status,
                        "success": False,
                        "cache_hit": False,
                        "fingerprint": prompt_fingerprint
                    }
            else:
                elapsed_time_ms = int((time.time() - start_time) * 1000)
                response_data = {
                    "text": "",
                    "error": str(primary_err),
                    "input_tokens": estimated_tokens,
                    "output_tokens": 0,
                    "elapsed_time_ms": elapsed_time_ms,
                    "retry_count": retry_attempts,
                    "quota_status": final_quota_status,
                    "success": False,
                    "cache_hit": False,
                    "fingerprint": prompt_fingerprint
                }

        finally:
            AIRequestQueue.release()

        return response_data
