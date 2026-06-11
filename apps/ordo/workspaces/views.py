from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render

from apps.ordo.accounts.models import CompanyMembership, DepartmentMembership

from .forms import WorkspaceGeneralForm
from .models import Project, Team, Workspace, WorkspaceAccessGrant, WorkspaceMembership


PROJECT_COLOR_CLASSES = ("blue", "gold", "cyan", "orange", "purple")
TEAM_COLOR_CLASSES = ("blue", "purple", "cyan", "orange", "gold")


def _build_workspace_context(request, current_page: str):
    workspaces = list(Workspace.objects.filter(is_active=True).order_by("name"))

    requested_workspace_slug = request.GET.get("workspace")
    current_workspace = next(
        (workspace for workspace in workspaces if workspace.slug == requested_workspace_slug),
        None,
    )
    if current_workspace is None and workspaces:
        current_workspace = workspaces[0]

    projects = []
    teams = []
    selected_project = None

    if current_workspace is not None:
        projects = list(
            current_workspace.projects.filter(is_active=True).order_by("name")
        )
        teams = list(
            Team.objects.filter(
                is_active=True,
                workspace_memberships__workspace=current_workspace,
            )
            .distinct()
            .order_by("name")
        )

        requested_project_slug = request.GET.get("project")
        selected_project = next(
            (project for project in projects if project.slug == requested_project_slug),
            None,
        )
        if selected_project is None and projects:
            selected_project = projects[0]

    project_items = [
        {
            "instance": project,
            "color_class": PROJECT_COLOR_CLASSES[index % len(PROJECT_COLOR_CLASSES)],
            "is_active": selected_project is not None and selected_project.pk == project.pk,
        }
        for index, project in enumerate(projects)
    ]
    team_items = [
        {
            "instance": team,
            "color_class": TEAM_COLOR_CLASSES[index % len(TEAM_COLOR_CLASSES)],
        }
        for index, team in enumerate(teams)
    ]

    return {
        "workspaces": workspaces,
        "current_workspace": current_workspace,
        "project_items": project_items,
        "team_items": team_items,
        "selected_project": selected_project,
        "selected_workspace_slug": current_workspace.slug if current_workspace else "",
        "current_page": current_page,
    }


def _workspace_access_queryset_for_user(user):
    if not user.is_authenticated:
        return WorkspaceMembership.objects.none()

    company_ids = CompanyMembership.objects.filter(user=user).values_list("company_id", flat=True)
    department_ids = DepartmentMembership.objects.filter(user=user).values_list("department_id", flat=True)

    return WorkspaceMembership.objects.filter(
        Q(team__users=user)
        | Q(team__companies__in=company_ids)
        | Q(team__departments__in=department_ids)
    ).distinct()


def _user_can_manage_workspace(user, workspace):
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True

    return _workspace_access_queryset_for_user(user).filter(
        workspace=workspace,
        role__in=(WorkspaceMembership.Role.OWNER, WorkspaceMembership.Role.ADMIN),
    ).exists()


def _build_workspace_access_grant_entries(workspace):
    grants = (
        WorkspaceAccessGrant.objects.filter(workspace=workspace)
        .select_related("company", "department", "user")
        .order_by("company__name", "department__name", "user__full_name", "user__email", "id")
    )

    entries = []
    for grant in grants:
        if grant.company_id:
            entries.append(
                {
                    "name": grant.company.name,
                    "type_label": "Company",
                    "scope_label": "Whole company",
                }
            )
        elif grant.department_id:
            entries.append(
                {
                    "name": grant.department.name,
                    "type_label": "Department",
                    "scope_label": "Department",
                }
            )
        elif grant.user_id:
            entries.append(
                {
                    "name": grant.user.full_name or grant.user.email,
                    "type_label": "User",
                    "scope_label": "Direct user",
                }
            )
    return entries


def workspace_dashboard(request):
    context = _build_workspace_context(request, current_page="dashboard")
    return render(request, "workspaces/dashboard.html", context)


def workspace_tasks(request):
    context = _build_workspace_context(request, current_page="tasks")
    return render(request, "workspaces/tasks.html", context)


def workspace_projects(request):
    context = _build_workspace_context(request, current_page="projects")
    return render(request, "workspaces/projects.html", context)


def workspace_teams(request):
    context = _build_workspace_context(request, current_page="teams")
    return render(request, "workspaces/teams.html", context)


def workspace_chats(request):
    context = _build_workspace_context(request, current_page="chats")
    return render(request, "workspaces/chats.html", context)


def workspace_storage(request):
    context = _build_workspace_context(request, current_page="storage")
    return render(request, "workspaces/storage.html", context)


def workspace_settings(request):
    context = _build_workspace_context(request, current_page="settings")
    current_workspace = context["current_workspace"]

    if current_workspace is None:
        context.update(
            {
                "workspace_form": None,
                "can_manage_workspace": False,
                "access_grant_entries": [],
            }
        )
        return render(request, "workspaces/settings.html", context)

    can_manage_workspace = _user_can_manage_workspace(request.user, current_workspace)

    if request.method == "POST":
        if not can_manage_workspace:
            return HttpResponseForbidden("You do not have permission to update this workspace.")

        workspace_form = WorkspaceGeneralForm(request.POST, instance=current_workspace)
        if workspace_form.is_valid():
            workspace_form.save()
            return redirect(f"{request.path}?workspace={current_workspace.slug}")
    else:
        workspace_form = WorkspaceGeneralForm(
            instance=current_workspace,
            disabled=not can_manage_workspace,
        )

    context.update(
        {
            "workspace_form": workspace_form,
            "can_manage_workspace": can_manage_workspace,
            "access_grant_entries": _build_workspace_access_grant_entries(current_workspace),
        }
    )
    return render(request, "workspaces/settings.html", context)
