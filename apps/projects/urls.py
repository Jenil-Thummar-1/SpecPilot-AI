from django.urls import path
from apps.projects.views import project_list_view, project_create_view, project_detail_view, run_plan_step_view, export_project_view

urlpatterns = [
    path('', project_list_view, name='project_list'),
    path('create/', project_create_view, name='project_create'),
    path('<int:project_id>/', project_detail_view, name='project_detail'),
    path('<int:project_id>/step/<int:step_id>/run/', run_plan_step_view, name='run_plan_step'),
    path('<int:project_id>/export/', export_project_view, name='export_project'),
]
