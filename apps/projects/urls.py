from django.urls import path
from apps.projects.views import (
    ProjectListView, ProjectCreateView, ProjectDetailView, 
    ProjectUpdateView, ProjectDeleteView, ProjectArchiveView, ProjectUnarchiveView,
    ProjectDuplicateView, ProjectVersionRestoreView, ProjectTimelineView,
    run_plan_step_view, export_project_view, SeedDemoProjectsView,
    ProjectStepExecuteAJAXView
)

urlpatterns = [
    # Main project listing & creation
    path('', ProjectListView.as_view(), name='project_list'),
    path('create/', ProjectCreateView.as_view(), name='project_create'),
    path('seed-demo/', SeedDemoProjectsView.as_view(), name='project_seed_demo'),
    
    # Detail and CRUD modifications
    path('<int:project_id>/', ProjectDetailView.as_view(), name='project_detail'),
    path('<int:project_id>/edit/', ProjectUpdateView.as_view(), name='project_edit'),
    path('<int:project_id>/delete/', ProjectDeleteView.as_view(), name='project_delete'),
    
    # Custom workspace action triggers
    path('<int:project_id>/archive/', ProjectArchiveView.as_view(), name='project_archive'),
    path('<int:project_id>/unarchive/', ProjectUnarchiveView.as_view(), name='project_unarchive'),
    path('<int:project_id>/duplicate/', ProjectDuplicateView.as_view(), name='project_duplicate'),
    path('<int:project_id>/restore/<int:version_number>/', ProjectVersionRestoreView.as_view(), name='project_restore'),
    path('<int:project_id>/timeline/', ProjectTimelineView.as_view(), name='project_timeline'),
    
    # Execution runners
    path('<int:project_id>/step/<int:step_id>/run/', run_plan_step_view, name='run_plan_step'),
    path('<int:project_id>/step/<int:step_id>/auto-run/', ProjectStepExecuteAJAXView.as_view(), name='run_plan_step_ajax'),
    path('<int:project_id>/export/', export_project_view, name='export_project'),
]
