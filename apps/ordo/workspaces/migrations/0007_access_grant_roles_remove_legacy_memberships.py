# Generated manually after replacing legacy workspace memberships with WorkspaceAccessGrant roles.

from django.conf import settings
from django.db import migrations, models


ROLE_PRIORITY = {
    "viewer": 0,
    "member": 1,
    "admin": 2,
    "owner": 3,
}


def _promote_grant_role(grant, role):
    if ROLE_PRIORITY.get(role, 0) > ROLE_PRIORITY.get(grant.role, 0):
        grant.role = role
        grant.save(update_fields=["role"])


def migrate_legacy_workspace_memberships(apps, schema_editor):
    WorkspaceAccessGrant = apps.get_model("workspaces", "WorkspaceAccessGrant")
    WorkspaceMembership = apps.get_model("workspaces", "WorkspaceMembership")

    memberships = WorkspaceMembership.objects.select_related("workspace", "team").all()
    for membership in memberships:
        role = membership.role
        workspace = membership.workspace
        team = membership.team

        for company in team.companies.all():
            grant, _ = WorkspaceAccessGrant.objects.get_or_create(
                workspace=workspace,
                company=company,
                defaults={"role": role},
            )
            _promote_grant_role(grant, role)

        for department in team.departments.all():
            grant, _ = WorkspaceAccessGrant.objects.get_or_create(
                workspace=workspace,
                department=department,
                defaults={"role": role},
            )
            _promote_grant_role(grant, role)

        for user in team.users.all():
            grant, _ = WorkspaceAccessGrant.objects.get_or_create(
                workspace=workspace,
                user=user,
                defaults={"role": role},
            )
            _promote_grant_role(grant, role)


class Migration(migrations.Migration):

    dependencies = [
        ("workspaces", "0006_workspace_company"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="workspaceaccessgrant",
            name="role",
            field=models.CharField(
                choices=[
                    ("owner", "Owner"),
                    ("admin", "Admin"),
                    ("member", "Member"),
                    ("viewer", "Viewer"),
                ],
                default="member",
                max_length=20,
            ),
        ),
        migrations.RunPython(
            migrate_legacy_workspace_memberships,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.DeleteModel(
            name="ProjectMembership",
        ),
        migrations.DeleteModel(
            name="WorkspaceMembership",
        ),
        migrations.DeleteModel(
            name="Team",
        ),
    ]
