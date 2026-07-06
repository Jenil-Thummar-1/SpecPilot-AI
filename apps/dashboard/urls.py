from django.urls import path
from apps.dashboard.views import (
    dashboard_view, PromptLibraryView,
    AboutView, FeaturesView, DocsView, PrivacyView, TermsView
)

urlpatterns = [
    path('', dashboard_view, name='dashboard'),
    path('prompts/', PromptLibraryView.as_view(), name='prompt_library'),
    path('about/', AboutView.as_view(), name='about'),
    path('features/', FeaturesView.as_view(), name='features'),
    path('docs/', DocsView.as_view(), name='docs'),
    path('privacy/', PrivacyView.as_view(), name='privacy'),
    path('terms/', TermsView.as_view(), name='terms'),
]
