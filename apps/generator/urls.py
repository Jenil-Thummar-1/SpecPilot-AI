from django.urls import path
from apps.generator.views import (
    ArtifactDetailView, ArtifactEditView, ArtifactApproveView, ArtifactRejectView, ArtifactCompareView
)

urlpatterns = [
    path('<int:artifact_id>/', ArtifactDetailView.as_view(), name='artifact_detail'),
    path('<int:artifact_id>/edit/', ArtifactEditView.as_view(), name='artifact_edit'),
    path('<int:artifact_id>/approve/', ArtifactApproveView.as_view(), name='artifact_approve'),
    path('<int:artifact_id>/reject/', ArtifactRejectView.as_view(), name='artifact_reject'),
    path('<int:artifact_id>/compare/<int:compare_id>/', ArtifactCompareView.as_view(), name='artifact_compare'),
]
