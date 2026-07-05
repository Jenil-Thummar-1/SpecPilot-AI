from django.urls import path
from apps.memory.views import MemoryListView, MemoryDetailView

urlpatterns = [
    path('', MemoryListView.as_view(), name='memory_list'),
    path('project/<int:project_id>/', MemoryDetailView.as_view(), name='memory_detail'),
]
