"""
Gemini AI Engine settings & safety parameters configuration.
Provides safety filter settings, API model selections, and initialization parameters.
"""
import os
from google import generativeai as genai

# Read settings from environment variables, fallback to defaults
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DEFAULT_MODEL_NAME = "gemini-2.5-flash"  # Standard high-speed planning model
ADVANCED_MODEL_NAME = "gemini-2.5-pro"   # Standard high-reasoning architect model

# Default safety settings for generation
SAFETY_SETTINGS = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    }
]

# Standard Generation Configuration
DEFAULT_GENERATION_CONFIG = {
    "temperature": 0.2,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
}

def initialize_gemini():
    """
    Initializes the Google Generative AI API client with the loaded key.
    """
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    else:
        # Client initialization fails gracefully if key is missing during project setup.
        # This allows django manage commands to run without requiring a valid key immediately.
        pass
