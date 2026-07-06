from django.db import migrations


def migrate_failed_to_needs_revision(apps, schema_editor):
    """
    Migrate all existing FAILED PlanSteps to NEEDS_REVISION
    so users are no longer stuck in a dead-end state.
    """
    PlanStep = apps.get_model('planner', 'PlanStep')
    updated = PlanStep.objects.filter(status='FAILED').update(status='NEEDS_REVISION')
    print(f"  Migrated {updated} FAILED steps to NEEDS_REVISION.")


def reverse_needs_revision_to_failed(apps, schema_editor):
    """Reverse: set NEEDS_REVISION back to FAILED."""
    PlanStep = apps.get_model('planner', 'PlanStep')
    PlanStep.objects.filter(status='NEEDS_REVISION').update(status='FAILED')


class Migration(migrations.Migration):

    dependencies = [
        ('planner', '0002_planstep_dependencies_str_and_more'),
    ]

    operations = [
        migrations.RunPython(
            migrate_failed_to_needs_revision,
            reverse_needs_revision_to_failed,
        ),
    ]
