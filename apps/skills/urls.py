from django.urls import path
from apps.skills.views import SkillListView, SkillCreateView, SkillUpdateView

urlpatterns = [
    path('', SkillListView.as_view(), name='skill_list'),
    path('create/', SkillCreateView.as_view(), name='skill_create'),
    path('<int:skill_id>/edit/', SkillUpdateView.as_view(), name='skill_edit'),
]
