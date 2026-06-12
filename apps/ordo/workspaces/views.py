from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.ordo.accounts.models import CompanyMembership, DepartmentMembership

from .forms import (
    WorkspaceCompanyAccessGrantForm,
    WorkspaceDepartmentAccessGrantForm,
    WorkspaceGeneralForm,
    WorkspaceProjectForm,
    WorkspaceTeamCompanyMemberForm,
    WorkspaceTeamDepartmentMemberForm,
    WorkspaceTeamForm,
    WorkspaceTeamUserMemberForm,
    WorkspaceUserAccessGrantForm,
)
from .models import (
    Project,
    Workspace,
    WorkspaceAccessGrant,
    WorkspaceMembership,
    WorkspaceTeam,
    WorkspaceTeamMember,
)


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

    if current_workspace is not None:
        projects = list(
            current_workspace.projects.filter(is_active=True)
            .select_related("team")
            .order_by("name")
        )
        teams = list(
            WorkspaceTeam.objects.filter(
                is_active=True,
                workspace=current_workspace,
            )
            .prefetch_related("members")
            .order_by("name")
        )

    project_items = [
        {
            "instance": project,
            "color_class": PROJECT_COLOR_CLASSES[index % len(PROJECT_COLOR_CLASSES)],
        }
        for index, project in enumerate(projects)
    ]
    team_items = [
        {
            "instance": team,
            "color_class": TEAM_COLOR_CLASSES[index % len(TEAM_COLOR_CLASSES)],
            "member_count": team.members.count(),
        }
        for index, team in enumerate(teams)
    ]

    return {
        "workspaces": workspaces,
        "current_workspace": current_workspace,
        "project_items": project_items,
        "team_items": team_items,
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
                    "id": grant.id,
                    "name": grant.company.name,
                    "type_label": "Company",
                    "scope_label": "Whole company",
                }
            )
        elif grant.department_id:
            entries.append(
                {
                    "id": grant.id,
                    "name": grant.department.name,
                    "type_label": "Department",
                    "scope_label": "Department",
                }
            )
        elif grant.user_id:
            entries.append(
                {
                    "id": grant.id,
                    "name": grant.user.full_name or grant.user.email,
                    "type_label": "User",
                    "scope_label": "Direct user",
                }
            )
    return entries


def _settings_redirect(workspace):
    return redirect(f"{reverse('workspaces:settings')}?workspace={workspace.slug}")


def _settings_access_redirect(workspace):
    return redirect(f"{reverse('workspaces:settings-members-access')}?workspace={workspace.slug}")


def _build_access_grant_forms(*, disabled=False):
    return {
        "company": WorkspaceCompanyAccessGrantForm(disabled=disabled),
        "department": WorkspaceDepartmentAccessGrantForm(disabled=disabled),
        "user": WorkspaceUserAccessGrantForm(disabled=disabled),
    }


def _get_selected_workspace(request):
    return _build_workspace_context(request, current_page="settings")["current_workspace"]


def _handle_access_grant_form(request, form_class):
    workspace = _get_selected_workspace(request)
    if workspace is None:
        return redirect("workspaces:settings-members-access")
    if not _user_can_manage_workspace(request.user, workspace):
        return HttpResponseForbidden("You do not have permission to manage workspace access.")

    form = form_class(request.POST)
    if form.is_valid():
        form.save(workspace)
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return _settings_access_redirect(workspace)


def workspace_dashboard(request):
    context = _build_workspace_context(request, current_page="dashboard")
    current_workspace = context["current_workspace"]
    context["dashboard_stats"] = {
        "projects": len(context["project_items"]),
        "teams": len(context["team_items"]),
        "access_entries": (
            current_workspace.access_grants.count() if current_workspace is not None else 0
        ),
    }
    return render(request, "workspaces/dashboard/dashboard.html", context)


def workspace_tasks(request):
    context = _build_workspace_context(request, current_page="tasks")
    return render(request, "workspaces/tasks/tasks.html", context)


def _build_workspace_project_items(workspace, selected_project=None):
    projects = workspace.projects.filter(is_active=True).select_related("team").order_by("name")
    return [
        {
            "instance": project,
            "color_class": PROJECT_COLOR_CLASSES[index % len(PROJECT_COLOR_CLASSES)],
            "is_active": selected_project is not None and selected_project.pk == project.pk,
        }
        for index, project in enumerate(projects)
    ]


def _projects_redirect(workspace, project=None):
    route_name = "workspaces:project-detail" if project else "workspaces:projects"
    args = [project.pk] if project else []
    return redirect(f"{reverse(route_name, args=args)}?workspace={workspace.slug}")


def workspace_projects(request, project_id=None, mode="list"):
    context = _build_workspace_context(request, current_page="projects")
    current_workspace = context["current_workspace"]

    if current_workspace is None:
        context.update(
            {
                "project_form": None,
                "workspace_project_items": [],
                "selected_workspace_project": None,
                "project_page_mode": mode,
                "can_manage_workspace": False,
            }
        )
        return render(request, "workspaces/projects/projects.html", context)

    selected_project = None
    if project_id is not None:
        selected_project = get_object_or_404(
            Project.objects.select_related("team", "created_by"),
            workspace=current_workspace,
            pk=project_id,
        )

    can_manage_workspace = _user_can_manage_workspace(request.user, current_workspace)
    project_form = None
    is_form_mode = mode in ("create", "edit")

    if request.method == "POST" and is_form_mode:
        if not can_manage_workspace:
            return HttpResponseForbidden("You do not have permission to manage workspace projects.")

        project_form = WorkspaceProjectForm(
            request.POST,
            workspace=current_workspace,
            created_by=request.user,
            instance=selected_project,
        )
        if project_form.is_valid():
            project = project_form.save()
            return _projects_redirect(current_workspace, project)
    elif is_form_mode:
        project_form = WorkspaceProjectForm(
            workspace=current_workspace,
            instance=selected_project,
            disabled=not can_manage_workspace,
        )

    context.update(
        {
            "project_form": project_form,
            "workspace_project_items": _build_workspace_project_items(
                current_workspace,
                selected_project,
            ),
            "selected_workspace_project": selected_project,
            "project_page_mode": mode,
            "can_manage_workspace": can_manage_workspace,
        }
    )
    return render(request, "workspaces/projects/projects.html", context)


def _build_workspace_team_items(workspace, selected_team=None):
    teams = (
        WorkspaceTeam.objects.filter(workspace=workspace)
        .prefetch_related("members")
        .order_by("name")
    )
    return [
        {
            "instance": team,
            "member_count": team.members.count(),
            "is_active": selected_team is not None and selected_team.pk == team.pk,
        }
        for team in teams
    ]


def _build_workspace_team_member_entries(team):
    memberships = (
        WorkspaceTeamMember.objects.filter(team=team)
        .select_related("access_grant__company", "access_grant__department", "access_grant__user")
        .order_by(
            "access_grant__company__name",
            "access_grant__department__name",
            "access_grant__user__full_name",
            "access_grant__user__email",
            "id",
        )
    )

    entries = []
    for membership in memberships:
        grant = membership.access_grant
        if grant.company_id:
            entries.append(
                {
                    "id": membership.id,
                    "name": grant.company.name,
                    "type_label": "Company",
                    "scope_label": "Company users",
                }
            )
        elif grant.department_id:
            entries.append(
                {
                    "id": membership.id,
                    "name": grant.department.name,
                    "type_label": "Department",
                    "scope_label": "Department users",
                }
            )
        elif grant.user_id:
            entries.append(
                {
                    "id": membership.id,
                    "name": grant.user.full_name or grant.user.email,
                    "type_label": "User",
                    "scope_label": "Direct user",
                }
            )
    return entries


def _build_team_member_forms(workspace, *, disabled=False):
    return {
        "company": WorkspaceTeamCompanyMemberForm(
            workspace=workspace,
            disabled=disabled,
            prefix="team_company",
        ),
        "department": WorkspaceTeamDepartmentMemberForm(
            workspace=workspace,
            disabled=disabled,
            prefix="team_department",
        ),
        "user": WorkspaceTeamUserMemberForm(
            workspace=workspace,
            disabled=disabled,
            prefix="team_user",
        ),
    }


def _teams_redirect(workspace, team=None):
    route_name = "workspaces:team-detail" if team else "workspaces:teams"
    args = [team.pk] if team else []
    return redirect(f"{reverse(route_name, args=args)}?workspace={workspace.slug}")


def workspace_teams(request, team_id=None):
    context = _build_workspace_context(request, current_page="teams")
    current_workspace = context["current_workspace"]

    if current_workspace is None:
        context.update(
            {
                "workspace_team_items": [],
                "selected_workspace_team": None,
                "team_form": None,
                "team_member_forms": {},
                "team_member_entries": [],
                "is_team_create_mode": True,
                "can_manage_workspace": False,
            }
        )
        return render(request, "workspaces/teams/teams.html", context)

    selected_team = None
    if team_id is not None:
        selected_team = get_object_or_404(
            WorkspaceTeam,
            workspace=current_workspace,
            pk=team_id,
        )

    can_manage_workspace = _user_can_manage_workspace(request.user, current_workspace)
    team_member_forms = _build_team_member_forms(
        current_workspace,
        disabled=not can_manage_workspace or selected_team is None,
    )

    if request.method == "POST":
        if not can_manage_workspace:
            return HttpResponseForbidden("You do not have permission to manage workspace teams.")

        action = request.POST.get("action", "save_team")
        if action == "save_team":
            team_form = WorkspaceTeamForm(
                request.POST,
                workspace=current_workspace,
                instance=selected_team,
            )
            if team_form.is_valid():
                team = team_form.save()
                return _teams_redirect(current_workspace, team)
        elif selected_team is None:
            return HttpResponseForbidden("Create the team before managing members.")
        elif action == "add_company_member":
            team_form = WorkspaceTeamForm(
                workspace=current_workspace,
                instance=selected_team,
                disabled=not can_manage_workspace,
            )
            form = WorkspaceTeamCompanyMemberForm(
                request.POST,
                workspace=current_workspace,
                prefix="team_company",
            )
            if form.is_valid():
                form.save(selected_team)
                return _teams_redirect(current_workspace, selected_team)
            team_member_forms["company"] = form
        elif action == "add_department_member":
            team_form = WorkspaceTeamForm(
                workspace=current_workspace,
                instance=selected_team,
                disabled=not can_manage_workspace,
            )
            form = WorkspaceTeamDepartmentMemberForm(
                request.POST,
                workspace=current_workspace,
                prefix="team_department",
            )
            if form.is_valid():
                form.save(selected_team)
                return _teams_redirect(current_workspace, selected_team)
            team_member_forms["department"] = form
        elif action == "add_user_member":
            team_form = WorkspaceTeamForm(
                workspace=current_workspace,
                instance=selected_team,
                disabled=not can_manage_workspace,
            )
            form = WorkspaceTeamUserMemberForm(
                request.POST,
                workspace=current_workspace,
                prefix="team_user",
            )
            if form.is_valid():
                form.save(selected_team)
                return _teams_redirect(current_workspace, selected_team)
            team_member_forms["user"] = form
        elif action == "remove_member":
            membership = get_object_or_404(
                WorkspaceTeamMember,
                pk=request.POST.get("membership_id"),
                team=selected_team,
            )
            membership.delete()
            return _teams_redirect(current_workspace, selected_team)
        else:
            return HttpResponseForbidden("Unsupported team action.")
    else:
        team_form = WorkspaceTeamForm(
            workspace=current_workspace,
            instance=selected_team,
            disabled=not can_manage_workspace,
        )

    context.update(
        {
            "workspace_team_items": _build_workspace_team_items(current_workspace, selected_team),
            "selected_workspace_team": selected_team,
            "team_form": team_form,
            "team_member_forms": team_member_forms,
            "team_member_entries": (
                _build_workspace_team_member_entries(selected_team) if selected_team else []
            ),
            "is_team_create_mode": selected_team is None,
            "can_manage_workspace": can_manage_workspace,
        }
    )
    return render(request, "workspaces/teams/teams.html", context)


def workspace_chats(request):
    context = _build_workspace_context(request, current_page="chats")
    return render(request, "workspaces/chats/chats.html", context)


def workspace_storage(request):
    context = _build_workspace_context(request, current_page="storage")
    return render(request, "workspaces/storage/storage.html", context)


def workspace_settings(request):
    context = _build_workspace_context(request, current_page="settings")
    current_workspace = context["current_workspace"]
    context["current_settings_section"] = "general"

    if current_workspace is None:
        context.update(
            {
                "workspace_form": None,
                "can_manage_workspace": False,
            }
        )
        return render(request, "workspaces/settings/general.html", context)

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
        }
    )
    return render(request, "workspaces/settings/general.html", context)


def workspace_settings_members_access(request):
    context = _build_workspace_context(request, current_page="settings")
    current_workspace = context["current_workspace"]
    context["current_settings_section"] = "members_access"

    if current_workspace is None:
        context.update(
            {
                "can_manage_workspace": False,
                "access_grant_entries": [],
                "access_grant_forms": _build_access_grant_forms(disabled=True),
            }
        )
        return render(request, "workspaces/settings/members_access.html", context)

    can_manage_workspace = _user_can_manage_workspace(request.user, current_workspace)

    context.update(
        {
            "access_grant_entries": _build_workspace_access_grant_entries(current_workspace),
            "access_grant_forms": _build_access_grant_forms(disabled=not can_manage_workspace),
            "can_manage_workspace": can_manage_workspace,
        }
    )
    return render(request, "workspaces/settings/members_access.html", context)


def add_company_access_grant(request):
    if request.method != "POST":
        return redirect("workspaces:settings-members-access")
    return _handle_access_grant_form(request, WorkspaceCompanyAccessGrantForm)


def add_department_access_grant(request):
    if request.method != "POST":
        return redirect("workspaces:settings-members-access")
    return _handle_access_grant_form(request, WorkspaceDepartmentAccessGrantForm)


def add_user_access_grant(request):
    if request.method != "POST":
        return redirect("workspaces:settings-members-access")
    return _handle_access_grant_form(request, WorkspaceUserAccessGrantForm)


def remove_access_grant(request, grant_id):
    workspace = _get_selected_workspace(request)
    if request.method != "POST" or workspace is None:
        return redirect("workspaces:settings-members-access")
    if not _user_can_manage_workspace(request.user, workspace):
        return HttpResponseForbidden("You do not have permission to manage workspace access.")

    grant = get_object_or_404(WorkspaceAccessGrant, pk=grant_id, workspace=workspace)
    grant.delete()
    return _settings_access_redirect(workspace)
