import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q
from django.utils.text import slugify


def rebuild_department_teams(apps, schema_editor):
    Department = apps.get_model("organizations", "Department")
    Workspace = apps.get_model("workspaces", "Workspace")
    WorkspaceAccessGrant = apps.get_model("workspaces", "WorkspaceAccessGrant")
    WorkspaceTeam = apps.get_model("workspaces", "WorkspaceTeam")
    WorkspaceTeamMember = apps.get_model("workspaces", "WorkspaceTeamMember")

    WorkspaceTeam.objects.all().delete()

    for workspace in Workspace.objects.all():
        company_ids = set(
            WorkspaceAccessGrant.objects.filter(
                workspace=workspace,
                company__isnull=False,
            ).values_list("company_id", flat=True)
        )
        if workspace.company_id:
            company_ids.add(workspace.company_id)
        explicit_department_ids = WorkspaceAccessGrant.objects.filter(
            workspace=workspace,
            department__isnull=False,
        ).values_list("department_id", flat=True)
        departments = list(
            Department.objects.filter(
                Q(company_id__in=company_ids) | Q(id__in=explicit_department_ids)
            )
            .select_related("type")
            .distinct()
        )

        grants_by_department = {}
        for department in departments:
            grant, _ = WorkspaceAccessGrant.objects.get_or_create(
                workspace=workspace,
                department=department,
                defaults={"role": "member", "is_system_generated": True},
            )
            grants_by_department[department.id] = grant

        departments_by_type = {}
        for department in departments:
            departments_by_type.setdefault(department.type_id, []).append(department)

        for department_type_id, typed_departments in departments_by_type.items():
            department_type = typed_departments[0].type
            base_slug = f"department-{slugify(department_type.code, allow_unicode=True)}"
            team = WorkspaceTeam.objects.create(
                workspace=workspace,
                department_type_id=department_type_id,
                name=department_type.name,
                slug=base_slug,
                description=f"Automatically managed {department_type.name} team.",
            )
            WorkspaceTeamMember.objects.bulk_create(
                [
                    WorkspaceTeamMember(
                        team=team,
                        access_grant=grants_by_department[department.id],
                    )
                    for department in typed_departments
                ]
            )


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0002_department_type"),
        ("workspaces", "0007_access_grant_roles_remove_legacy_memberships"),
    ]

    operations = [
        migrations.AddField(
            model_name="workspaceaccessgrant",
            name="is_system_generated",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="workspaceteam",
            name="department_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="workspace_teams",
                to="organizations.departmenttype",
            ),
        ),
        migrations.AddConstraint(
            model_name="workspaceteam",
            constraint=models.UniqueConstraint(
                condition=models.Q(department_type__isnull=False),
                fields=("workspace", "department_type"),
                name="unique_workspace_department_type_team",
            ),
        ),
        migrations.RunPython(rebuild_department_teams, migrations.RunPython.noop),
    ]
