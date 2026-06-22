from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify

from apps.ordo.organizations.models import Department

from .models import WorkspaceAccessGrant, WorkspaceTeam, WorkspaceTeamMember


def workspace_department_scope(workspace):
    grants = workspace.access_grants.all()
    company_ids = set(
        grants.filter(company__isnull=False).values_list("company_id", flat=True)
    )
    if workspace.company_id:
        company_ids.add(workspace.company_id)

    explicit_department_ids = grants.filter(
        department__isnull=False,
        is_system_generated=False,
    ).values_list("department_id", flat=True)

    return (
        Department.objects.filter(
            Q(company_id__in=company_ids) | Q(id__in=explicit_department_ids)
        )
        .select_related("company", "type")
        .distinct()
        .order_by("type__name", "company__name", "name")
    )


def _unique_team_slug(workspace, department_type):
    base_slug = f"department-{slugify(department_type.code, allow_unicode=True)}"
    base_slug = base_slug or f"department-type-{department_type.id}"
    slug = base_slug
    suffix = 2
    while WorkspaceTeam.objects.filter(workspace=workspace, slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return slug


@transaction.atomic
def sync_workspace_department_teams(workspace):
    departments = list(workspace_department_scope(workspace))
    scoped_department_ids = {department.id for department in departments}

    department_grants = {}
    for department in departments:
        grant, _ = WorkspaceAccessGrant.objects.get_or_create(
            workspace=workspace,
            department=department,
            defaults={
                "role": WorkspaceAccessGrant.Role.MEMBER,
                "is_system_generated": True,
            },
        )
        department_grants[department.id] = grant

    WorkspaceAccessGrant.objects.filter(
        workspace=workspace,
        department__isnull=False,
        is_system_generated=True,
    ).exclude(department_id__in=scoped_department_ids).delete()

    departments_by_type = {}
    for department in departments:
        departments_by_type.setdefault(department.type_id, []).append(department)

    active_type_ids = set(departments_by_type)
    for department_type_id, typed_departments in departments_by_type.items():
        department_type = typed_departments[0].type
        team = WorkspaceTeam.objects.filter(
            workspace=workspace,
            department_type_id=department_type_id,
        ).first()
        if team is None:
            team = WorkspaceTeam.objects.create(
                workspace=workspace,
                department_type=department_type,
                name=department_type.name,
                slug=_unique_team_slug(workspace, department_type),
                description=f"Automatically managed {department_type.name} team.",
            )
        else:
            changed_fields = []
            if team.name != department_type.name:
                team.name = department_type.name
                changed_fields.append("name")
            if not team.is_active:
                team.is_active = True
                changed_fields.append("is_active")
            if changed_fields:
                team.save(update_fields=changed_fields)

        expected_grant_ids = {
            department_grants[department.id].id for department in typed_departments
        }
        for grant_id in expected_grant_ids:
            WorkspaceTeamMember.objects.get_or_create(
                team=team,
                access_grant_id=grant_id,
            )
        team.members.exclude(access_grant_id__in=expected_grant_ids).delete()

    stale_teams = WorkspaceTeam.objects.filter(
        workspace=workspace,
        department_type__isnull=False,
    ).exclude(department_type_id__in=active_type_ids)
    stale_teams.update(is_active=False)
    WorkspaceTeamMember.objects.filter(team__in=stale_teams).delete()


def sync_department_workspaces(department, *, previous_company_id=None):
    from .models import Workspace

    company_ids = {department.company_id}
    if previous_company_id:
        company_ids.add(previous_company_id)

    workspaces = Workspace.objects.filter(
        Q(company_id__in=company_ids)
        | Q(access_grants__company_id__in=company_ids)
        | Q(access_grants__department=department)
    ).distinct()
    for workspace in workspaces:
        sync_workspace_department_teams(workspace)
