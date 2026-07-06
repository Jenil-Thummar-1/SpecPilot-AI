import json
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from apps.projects.models import Project
from apps.planner.models import PlanStep
from apps.generator.models import GeneratedArtifact
from apps.planner.services.planner_service import PlannerService
from apps.projects.services import ProjectService

User = get_user_model()

@override_settings(GEMINI_API_KEY="dummy-api-key-for-now")
class AutonomousPlannerE2ETest(TestCase):
    """
    End-to-end integration test verifying the stability and correctness 
    of the entire autonomous planning workflow, FSM transitions, and AJAX view.
    """

    def setUp(self):
        # Create developer test user (using custom user model support)
        self.user = User.objects.create_user(
            username="developer",
            email="developer@specpilot.ai",
            password="securepassword123"
        )
        # Force staff access for diagnostics capability checks
        self.user.is_staff = True
        self.user.save()

        # Create target project via ProjectService to ensure Phase 1 is auto-completed
        self.project = ProjectService.create_project(
            user=self.user,
            title="E2E Test SpecPilot App",
            description="Build a secure SaaS messaging portal with real-time logs.",
            short_description="SaaS messaging portal with real-time logs.",
            architecture_type="MVC",
            deployment_preference="Docker / VPS"
        )
        self.plan = self.project.plan
        
        self.client = Client()
        self.client.login(username="developer", password="securepassword123")

    def test_complete_autonomous_workflow_e2e(self):
        # 1. Verify project starts in PLANNING state
        self.assertEqual(self.project.status, "PLANNING")
        self.assertEqual(self.plan.steps.count(), 15)

        # 2. Iterate and execute steps sequentially (1 to 14)
        # Note: Step 15 is EXPORT_PREP which runs automatically when others are completed.
        steps = self.plan.steps.all().order_by('order')
        
        for step in steps:
            # Phase 1 is auto-completed during creation
            if step.step_type == 'IDEA':
                self.assertEqual(step.status, "COMPLETED")
                continue
                
            if step.step_type == 'EXPORT_PREP':
                continue
                
            # Perform AJAX post to execute pipeline on step
            run_url = f"/projects/{self.project.id}/step/{step.id}/auto-run/"
            response = self.client.post(
                run_url,
                data=json.dumps({"force_regen": True}),
                content_type="application/json"
            )
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.content)
            self.assertTrue(data["success"])
            self.assertEqual(data["step_id"], step.id)
            self.assertIn("diagnostics", data)
            
            # Confirm artifact generation
            latest_artifact = GeneratedArtifact.objects.filter(project=self.project, step=step).first()
            self.assertIsNotNone(latest_artifact)
            self.assertTrue(latest_artifact.is_approved)

            # Assert step status is marked completed in FSM
            step.refresh_from_db()
            self.assertEqual(step.status, "COMPLETED")

        # 3. Verify final state transitions
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, "COMPLETE")
        
        # 4. Verify Export Prep (Step 15) was compiled automatically
        export_prep_step = self.plan.steps.filter(step_type='EXPORT_PREP').first()
        self.assertEqual(export_prep_step.status, "COMPLETED")
        
        export_artifact = GeneratedArtifact.objects.filter(project=self.project, step=export_prep_step).first()
        self.assertIsNotNone(export_artifact)
        self.assertTrue(export_artifact.is_approved)
