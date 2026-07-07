from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'

    def ready(self):
        try:
            from apps.core.services.router import AIProviderRouter
            AIProviderRouter.startup_check()
        except Exception:
            # Startup diagnostics must never prevent Django management commands.
            pass
