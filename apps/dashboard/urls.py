from django.urls import path
from apps.dashboard.views import dashboard_view, PromptLibraryView

urlpatterns = [
    path('', dashboard_view, name='dashboard'),
    path('prompts/', PromptLibraryView.as_view(), name='prompt_library'),
]
