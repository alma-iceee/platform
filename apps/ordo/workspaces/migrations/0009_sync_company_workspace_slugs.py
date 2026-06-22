from django.db import migrations


def sync_company_workspace_slugs(apps, schema_editor):
    Workspace = apps.get_model("workspaces", "Workspace")

    for workspace in Workspace.objects.filter(company__isnull=False).select_related("company"):
        target_slug = workspace.company.slug
        if Workspace.objects.exclude(pk=workspace.pk).filter(slug=target_slug).exists():
            raise RuntimeError(
                f"Workspace slug '{target_slug}' is already in use and cannot be assigned "
                f"to company workspace {workspace.pk}."
            )
        workspace.slug = target_slug
        workspace.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0003_company_slug"),
        ("workspaces", "0008_automatic_department_teams"),
    ]

    operations = [
        migrations.RunPython(sync_company_workspace_slugs, migrations.RunPython.noop),
    ]
