from django.urls import path
from apps.agents.views import (
    AgentListView, AgentCreateView, AgentUpdateView, AgentToggleView, ExecutionHistoryView
)

urlpatterns = [
    path('', AgentListView.as_view(), name='agent_list'),
    path('create/', AgentCreateView.as_view(), name='agent_create'),
    path('<int:agent_id>/edit/', AgentUpdateView.as_view(), name='agent_edit'),
    path('<int:agent_id>/toggle/', AgentToggleView.as_view(), name='agent_toggle'),
    path('executions/', ExecutionHistoryView.as_view(), name='execution_history'),
]
