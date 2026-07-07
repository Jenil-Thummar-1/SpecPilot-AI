"""
Django settings for SpecPilot AI project.
Incorporates production-ready configurations, modular paths, and logging formats.
"""
import os
import environ
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize environment reading
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1']),
    LOG_LEVEL=(str, 'INFO')
)

# Load environment file
env_file = BASE_DIR / '.env'
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# Application definition
INSTALLED_APPS = [
    # Core django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # SpecPilot AI modular apps
    'apps.core',
    'apps.accounts',
    'apps.projects',
    'apps.agents',
    'apps.skills',
    'apps.memory',
    'apps.planner',
    'apps.generator',
    'apps.evaluation',
    'apps.exports',
    'apps.dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases
DATABASES = {
    'default': env.db('DATABASE_URL', default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Authentication Custom User Model Config
AUTH_USER_MODEL = 'accounts.User'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'landing'

# Language and timezone configurations
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media Files (User uploads and compile exports)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# AI Provider Configurations
AI_PROVIDER = env('AI_PROVIDER', default='auto')
OLLAMA_BASE_URL = env('OLLAMA_BASE_URL', default='http://localhost:11434')
OLLAMA_MODEL = env('OLLAMA_MODEL', default='llama3')
GEMINI_API_KEY = env('GEMINI_API_KEY', default='')
GEMINI_MODEL = env('GEMINI_MODEL', default='gemini-2.5-flash')
GEMINI_MAX_RETRIES = env.int('GEMINI_MAX_RETRIES', default=2)
GEMINI_MAX_REQUEST_TOKENS = env.int('GEMINI_MAX_REQUEST_TOKENS', default=30000)

# Security & Safety Layers
AI_SAFETY_BLOCKING = True

# Enterprise logging layout
# Creates logs folder if not present
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGS_FILE_PATH = LOGS_DIR / 'application.log'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} - {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': env('LOG_LEVEL'),
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_FILE_PATH),
            'maxBytes': 1024 * 1024 * 10,  # 10 MB rotating logs
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'specpilot.ai': {
            'handlers': ['console', 'file'],
            'level': env('LOG_LEVEL'),
            'propagate': False,
        },
    },
}
