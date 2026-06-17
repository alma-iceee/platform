from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.ordo.accounts.models import CompanyMembership, DepartmentMembership
from apps.ordo.organizations.models import Department
from apps.ordo.tasks.models import Task, TaskBoard

from .forms import (
    WorkspaceCompanyAccessGrantForm,
    WorkspaceDepartmentAccessGrantForm,
    WorkspaceForm,
    WorkspaceGeneralForm,
    WorkspaceProjectForm,
    WorkspaceProjectTeamForm,
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
    WorkspaceTeam,
    WorkspaceTeamMember,
)


PROJECT_COLOR_CLASSES = ("blue", "gold", "cyan", "orange", "purple")
TEAM_COLOR_CLASSES = ("blue", "purple", "cyan", "orange", "gold")


def _build_workspace_context(request, current_page: str):
    workspaces = sorted(
        _visible_workspaces_queryset(request.user),
        key=lambda workspace: (workspace.company_id is None, workspace.name.lower()),
    )

    requested_workspace_slug = request.GET.get("workspace")
    current_workspace = next(
        (workspace for workspace in workspaces if workspace.slug == requested_workspace_slug),
        None,
    )
    if current_workspace is None and workspaces:
        current_workspace = workspaces[0]

    departments = []
    projects = []
    teams = []

    shows_department_navigation = bool(current_workspace and current_workspace.company_id)

    if current_workspace is not None:
        departments = list(
            _visible_workspace_departments_queryset(current_workspace, request.user)
            .select_related("company")
            .order_by("company__name", "name")
        )
        visible_projects = _visible_workspace_projects_queryset(current_workspace, request.user)
        projects = list(
            visible_projects.select_related("team")
            .order_by("name")
        )
        teams = list(
            _visible_workspace_teams_queryset(current_workspace, request.user)
            .filter(is_active=True)
            .annotate(
                company_count=Count(
                    "members",
                    filter=Q(members__access_grant__company__isnull=False),
                    distinct=True,
                ),
                department_count=Count(
                    "members",
                    filter=Q(members__access_grant__department__isnull=False),
                    distinct=True,
                ),
                user_count=Count(
                    "members",
                    filter=Q(members__access_grant__user__isnull=False),
                    distinct=True,
                ),
            )
            .order_by("name")
        )

    department_items = [
        {
            "instance": department,
            "color_class": PROJECT_COLOR_CLASSES[index % len(PROJECT_COLOR_CLASSES)],
        }
        for index, department in enumerate(departments)
    ]
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
            "company_count": team.company_count,
            "department_count": team.department_count,
            "user_count": team.user_count,
        }
        for index, team in enumerate(teams)
    ]

    return {
        "workspaces": workspaces,
        "current_workspace": current_workspace,
        "department_items": department_items,
        "project_items": project_items,
        "team_items": team_items,
        "selected_workspace_slug": current_workspace.slug if current_workspace else "",
        "current_page": current_page,
        "shows_department_navigation": shows_department_navigation,
        "shows_settings_navigation": bool(
            current_workspace and _user_can_manage_workspace_settings(request.user, current_workspace)
        ),
        "can_create_workspace": _user_can_create_workspace(request.user),
    }


def _user_can_manage_workspace(user, workspace):
    if not user.is_authenticated:
        return False
    if _user_has_global_workspace_access(user):
        return True
    if workspace.company_id and workspace.company_id in _user_director_company_ids(user):
        return True

    return WorkspaceAccessGrant.objects.filter(
        workspace=workspace,
        role__in=(WorkspaceAccessGrant.Role.OWNER, WorkspaceAccessGrant.Role.ADMIN),
    ).filter(
        Q(user=user)
        | Q(company_id__in=CompanyMembership.objects.filter(user=user).values_list("company_id", flat=True))
        | Q(
            department_id__in=DepartmentMembership.objects.filter(user=user).values_list(
                "department_id",
                flat=True,
            )
        )
    ).exists()


def _user_can_manage_workspace_settings(user, workspace):
    if workspace.company_id:
        return False
    return _user_is_ceo(user)


def _user_can_create_workspace(user):
    return _user_is_ceo(user)


def _user_is_ceo(user):
    if not user.is_authenticated:
        return False
    return getattr(user, "system_role", None) == "ceo"


def _raise_for_company_workspace_settings(workspace):
    if workspace.company_id:
        raise PermissionDenied("Company workspace settings are managed through admin.")


def _user_has_global_workspace_access(user):
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return getattr(user, "system_role", None) in ("ceo", "general_director")


def _visible_workspaces_queryset(user):
    workspaces = Workspace.objects.filter(is_active=True).select_related("company")

    if not user.is_authenticated:
        return workspaces.none()
    if _user_has_global_workspace_access(user):
        return workspaces.order_by("name")

    company_ids = _user_company_ids(user)
    department_ids = _user_department_ids(user)

    return (
        workspaces.filter(
            Q(company_id__in=company_ids)
            | Q(access_grants__user=user)
            | Q(access_grants__company_id__in=company_ids)
            | Q(access_grants__department_id__in=department_ids)
        )
        .distinct()
        .order_by("name")
    )


def _user_company_ids(user):
    return CompanyMembership.objects.filter(user=user).values_list("company_id", flat=True)


def _user_director_company_ids(user):
    return CompanyMembership.objects.filter(
        user=user,
        role=CompanyMembership.Role.DIRECTOR,
    ).values_list("company_id", flat=True)


def _user_department_ids(user):
    return DepartmentMembership.objects.filter(user=user).values_list("department_id", flat=True)


def _workspace_granted_company_ids_for_user(user, workspace):
    return WorkspaceAccessGrant.objects.filter(
        workspace=workspace,
        company_id__in=_user_company_ids(user),
    ).values_list("company_id", flat=True)


def _workspace_department_scope_queryset(workspace):
    if not workspace.company_id:
        return Department.objects.none()
    return Department.objects.filter(company_id=workspace.company_id)


def _visible_workspace_departments_queryset(workspace, user):
    departments = _workspace_department_scope_queryset(workspace)

    if _user_can_manage_workspace(user, workspace):
        return departments

    return departments.filter(
        Q(id__in=_user_department_ids(user))
        | Q(
            company_id=workspace.company_id,
            company_id__in=_user_director_company_ids(user),
        )
    ).distinct()


def _workspace_team_ids_for_user(user, workspace):
    return _visible_workspace_teams_queryset(workspace, user).values_list("id", flat=True)


def _visible_workspace_teams_queryset(workspace, user):
    teams = WorkspaceTeam.objects.filter(workspace=workspace)

    if _user_can_manage_workspace(user, workspace):
        return teams

    company_ids = _user_company_ids(user)
    department_ids = _user_department_ids(user)
    director_company_ids = _user_director_company_ids(user)
    granted_company_ids = _workspace_granted_company_ids_for_user(user, workspace)

    return (
        teams.filter(
            Q(members__access_grant__user=user)
            | Q(members__access_grant__company_id__in=company_ids)
            | Q(members__access_grant__department_id__in=department_ids)
            | (
                Q(members__access_grant__department__company_id__in=director_company_ids)
                & Q(members__access_grant__department__company_id__in=granted_company_ids)
            )
        )
        .distinct()
    )


def _visible_workspace_projects_queryset(workspace, user):
    projects = workspace.projects.filter(is_active=True)

    if _user_can_manage_workspace(user, workspace):
        return projects

    team_ids = _workspace_team_ids_for_user(user, workspace)

    return projects.filter(team_id__in=team_ids).distinct()


def _create_workspace_creator_access(workspace, user):
    WorkspaceAccessGrant.objects.update_or_create(
        workspace=workspace,
        user=user,
        defaults={"role": WorkspaceAccessGrant.Role.OWNER},
    )


def _build_workspace_access_grant_entries(workspace):
    grants = (
        WorkspaceAccessGrant.objects.filter(workspace=workspace)
        .select_related("company", "department", "department__company", "user")
        .order_by("company__name", "department__name", "user__full_name", "user__email", "id")
    )

    entries = []
    for grant in grants:
        if grant.company_id:
            entries.append(
                {
                    "id": grant.id,
                    "name": grant.company.name,
                    "type": "company",
                    "type_label": "Company",
                    "scope_label": "Whole company",
                }
            )
        elif grant.department_id:
            entries.append(
                {
                    "id": grant.id,
                    "name": grant.department.name,
                    "subtitle": grant.department.company.name if grant.department.company_id else "",
                    "type": "department",
                    "type_label": "Department",
                    "scope_label": "Department",
                }
            )
        elif grant.user_id:
            entries.append(
                {
                    "id": grant.id,
                    "name": grant.user.full_name or grant.user.email,
                    "type": "user",
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
    _raise_for_company_workspace_settings(workspace)
    if not _user_can_manage_workspace_settings(request.user, workspace):
        raise PermissionDenied("You do not have permission to manage workspace access.")

    form = form_class(request.POST)
    if form.is_valid():
        form.save(workspace)
        messages.success(request, "Access granted.")
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return _settings_access_redirect(workspace)


def workspace_dashboard(request):
    context = _build_workspace_context(request, current_page="dashboard")
    current_workspace = context["current_workspace"]
    context["dashboard_stats"] = {
        "departments": len(context["department_items"]),
        "projects": len(context["project_items"]),
        "teams": len(context["team_items"]),
        "access_entries": (
            current_workspace.access_grants.count() if current_workspace is not None else 0
        ),
    }
    return render(request, "workspaces/dashboard/dashboard.html", context)


@login_required
def workspace_create(request):
    if not _user_can_create_workspace(request.user):
        raise PermissionDenied("Only CEO users can create workspaces.")

    context = _build_workspace_context(request, current_page="workspace_create")

    if request.method == "POST":
        workspace_form = WorkspaceForm(request.POST)
        if workspace_form.is_valid():
            with transaction.atomic():
                workspace = workspace_form.save()
                _create_workspace_creator_access(workspace, request.user)
            return redirect(f"{reverse('workspaces:dashboard')}?workspace={workspace.slug}")
    else:
        workspace_form = WorkspaceForm()

    current_workspace = context["current_workspace"]
    cancel_url = (
        f"{reverse('workspaces:dashboard')}?workspace={current_workspace.slug}"
        if current_workspace is not None
        else reverse("workspaces:shell")
    )
    context.update(
        {
            "workspace_form": workspace_form,
            "cancel_url": cancel_url,
        }
    )
    return render(request, "workspaces/workspaces/create.html", context)


def workspace_tasks(request):
    context = _build_workspace_context(request, current_page="tasks")
    current_workspace = context["current_workspace"]

    if current_workspace is None:
        context.update(
            {
                "inbox_board_item": None,
                "workspace_board_item": None,
                "department_board_items": [],
                "project_board_items": [],
                "selected_board": None,
                "board_columns": [],
            }
        )
        return render(request, "workspaces/tasks/tasks.html", context)

    boards = list(TaskBoard.objects.filter(workspace=current_workspace))

    visible_department_ids = set(
        _visible_workspace_departments_queryset(current_workspace, request.user).values_list(
            "id", flat=True
        )
    )
    visible_project_ids = set(
        _visible_workspace_projects_queryset(current_workspace, request.user).values_list(
            "id", flat=True
        )
    )

    inbox_board = next((b for b in boards if b.board_type == TaskBoard.BoardType.INBOX), None)
    workspace_board = next(
        (b for b in boards if b.board_type == TaskBoard.BoardType.WORKSPACE), None
    )
    department_boards = [
        b
        for b in boards
        if b.board_type == TaskBoard.BoardType.DEPARTMENT and b.department_id in visible_department_ids
    ]
    project_boards = [
        b
        for b in boards
        if b.board_type == TaskBoard.BoardType.PROJECT and b.project_id in visible_project_ids
    ]

    accessible_boards = [
        b for b in [inbox_board, workspace_board, *department_boards, *project_boards] if b
    ]
    accessible_by_id = {b.id: b for b in accessible_boards}

    selected_board = None
    requested_board_id = request.GET.get("board")
    if requested_board_id and requested_board_id.isdigit():
        selected_board = accessible_by_id.get(int(requested_board_id))
    if selected_board is None:
        selected_board = workspace_board or inbox_board or (accessible_boards[0] if accessible_boards else None)

    def _board_item(board):
        return {
            "instance": board,
            "is_active": selected_board is not None and board.id == selected_board.id,
        }

    board_columns = []
    if selected_board is not None:
        columns = list(selected_board.columns.order_by("position", "id"))
        tasks = list(
            Task.objects.filter(board=selected_board)
            .select_related("responsible")
            .order_by("position", "id")
        )
        tasks_by_column = {}
        for task in tasks:
            tasks_by_column.setdefault(task.column_id, []).append(task)
        board_columns = [
            {
                "column": column,
                "tasks": tasks_by_column.get(column.id, []),
                "count": len(tasks_by_column.get(column.id, [])),
            }
            for column in columns
        ]

    context.update(
        {
            "inbox_board_item": _board_item(inbox_board) if inbox_board else None,
            "workspace_board_item": _board_item(workspace_board) if workspace_board else None,
            "department_board_items": [_board_item(b) for b in department_boards],
            "project_board_items": [_board_item(b) for b in project_boards],
            "selected_board": selected_board,
            "board_columns": board_columns,
        }
    )
    return render(request, "workspaces/tasks/tasks.html", context)


def workspace_departments(request):
    context = _build_workspace_context(request, current_page="departments")
    current_workspace = context["current_workspace"]
    if current_workspace is not None and not context["shows_department_navigation"]:
        return redirect(f"{reverse('workspaces:dashboard')}?workspace={current_workspace.slug}")
    return render(request, "workspaces/departments/departments.html", context)


def _build_workspace_project_items(workspace, user, selected_project=None):
    projects = (
        _visible_workspace_projects_queryset(workspace, user)
        .select_related("team")
        .order_by("name")
    )
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


def _project_edit_redirect(workspace, project):
    return redirect(
        f"{reverse('workspaces:project-edit', args=[project.pk])}?workspace={workspace.slug}"
    )


def workspace_projects(request, project_id=None, mode="list"):
    context = _build_workspace_context(request, current_page="projects")
    current_workspace = context["current_workspace"]

    if current_workspace is None:
        context.update(
            {
                "project_form": None,
                "project_team_form": None,
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
            _visible_workspace_projects_queryset(current_workspace, request.user).select_related(
                "team",
                "created_by",
            ),
            workspace=current_workspace,
            pk=project_id,
        )

    can_manage_workspace = _user_can_manage_workspace(request.user, current_workspace)
    project_form = None
    project_team_form = None

    if mode == "create":
        if request.method == "POST":
            if not can_manage_workspace:
                raise PermissionDenied("You do not have permission to manage workspace projects.")
            project_form = WorkspaceProjectForm(
                request.POST,
                workspace=current_workspace,
                created_by=request.user,
            )
            if project_form.is_valid():
                project = project_form.save()
                return _project_edit_redirect(current_workspace, project)
        else:
            project_form = WorkspaceProjectForm(
                workspace=current_workspace,
                created_by=request.user,
                disabled=not can_manage_workspace,
            )
    elif mode == "edit":
        if request.method == "POST":
            if not can_manage_workspace:
                raise PermissionDenied("You do not have permission to manage workspace projects.")
            action = request.POST.get("action", "save_details")
            if action == "save_team":
                project_team_form = WorkspaceProjectTeamForm(
                    request.POST,
                    workspace=current_workspace,
                    instance=selected_project,
                )
                if project_team_form.is_valid():
                    project_team_form.save()
                    return _project_edit_redirect(current_workspace, selected_project)
                project_form = WorkspaceProjectForm(
                    workspace=current_workspace,
                    instance=selected_project,
                    disabled=not can_manage_workspace,
                )
            elif action == "save_details":
                project_form = WorkspaceProjectForm(
                    request.POST,
                    workspace=current_workspace,
                    created_by=request.user,
                    instance=selected_project,
                )
                if project_form.is_valid():
                    project_form.save()
                    return _project_edit_redirect(current_workspace, selected_project)
                project_team_form = WorkspaceProjectTeamForm(
                    workspace=current_workspace,
                    instance=selected_project,
                    disabled=not can_manage_workspace,
                )
            else:
                raise SuspiciousOperation("Unsupported project action.")
        else:
            project_form = WorkspaceProjectForm(
                workspace=current_workspace,
                instance=selected_project,
                disabled=not can_manage_workspace,
            )
            project_team_form = WorkspaceProjectTeamForm(
                workspace=current_workspace,
                instance=selected_project,
                disabled=not can_manage_workspace,
            )

    context.update(
        {
            "project_form": project_form,
            "project_team_form": project_team_form,
            "workspace_project_items": _build_workspace_project_items(
                current_workspace,
                request.user,
                selected_project,
            ),
            "selected_workspace_project": selected_project,
            "project_page_mode": mode,
            "can_manage_workspace": can_manage_workspace,
        }
    )
    return render(request, "workspaces/projects/projects.html", context)


def _build_workspace_team_items(workspace, user, selected_team=None):
    teams = (
        _visible_workspace_teams_queryset(workspace, user)
        .annotate(
            company_count=Count(
                "members",
                filter=Q(members__access_grant__company__isnull=False),
                distinct=True,
            ),
            department_count=Count(
                "members",
                filter=Q(members__access_grant__department__isnull=False),
                distinct=True,
            ),
            user_count=Count(
                "members",
                filter=Q(members__access_grant__user__isnull=False),
                distinct=True,
            ),
        )
        .order_by("name")
    )
    return [
        {
            "instance": team,
            "color_class": TEAM_COLOR_CLASSES[index % len(TEAM_COLOR_CLASSES)],
            "company_count": team.company_count,
            "department_count": team.department_count,
            "user_count": team.user_count,
            "is_active": selected_team is not None and selected_team.pk == team.pk,
        }
        for index, team in enumerate(teams)
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


def _team_members_redirect(workspace, team):
    return redirect(
        f"{reverse('workspaces:team-members', args=[team.pk])}?workspace={workspace.slug}"
    )


def workspace_teams(request, team_id=None):
    context = _build_workspace_context(request, current_page="teams")
    current_workspace = context["current_workspace"]

    if current_workspace is None:
        context.update(
            {
                "workspace_team_items": [],
                "selected_workspace_team": None,
                "team_form": None,
                "is_team_create_mode": True,
                "is_team_list_mode": True,
                "team_section": "edit",
                "can_manage_workspace": False,
            }
        )
        return render(request, "workspaces/teams/teams.html", context)

    selected_team = None
    if team_id is not None:
        selected_team = get_object_or_404(
            _visible_workspace_teams_queryset(current_workspace, request.user),
            pk=team_id,
        )

    can_manage_workspace = _user_can_manage_workspace(request.user, current_workspace)

    if request.method == "POST":
        if not can_manage_workspace:
            raise PermissionDenied("You do not have permission to manage workspace teams.")

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
        else:
            raise SuspiciousOperation("Unsupported team action.")
    else:
        team_form = WorkspaceTeamForm(
            workspace=current_workspace,
            instance=selected_team,
            disabled=not can_manage_workspace,
        )

    context.update(
        {
            "workspace_team_items": _build_workspace_team_items(
                current_workspace,
                request.user,
                selected_team,
            ),
            "selected_workspace_team": selected_team,
            "team_form": team_form,
            "is_team_create_mode": selected_team is None,
            "is_team_list_mode": team_id is None,
            "team_section": "edit",
            "can_manage_workspace": can_manage_workspace,
        }
    )
    return render(request, "workspaces/teams/teams.html", context)


def workspace_team_members(request, team_id):
    context = _build_workspace_context(request, current_page="teams")
    current_workspace = context["current_workspace"]

    if current_workspace is None:
        return redirect("workspaces:teams")

    selected_team = get_object_or_404(
        _visible_workspace_teams_queryset(current_workspace, request.user),
        pk=team_id,
    )

    can_manage_workspace = _user_can_manage_workspace(request.user, current_workspace)
    team_member_forms = _build_team_member_forms(
        current_workspace,
        disabled=not can_manage_workspace,
    )

    if request.method == "POST":
        if not can_manage_workspace:
            raise PermissionDenied("You do not have permission to manage workspace teams.")

        action = request.POST.get("action")
        if action == "add_company_member":
            form = WorkspaceTeamCompanyMemberForm(
                request.POST,
                workspace=current_workspace,
                prefix="team_company",
            )
            if form.is_valid():
                form.save(selected_team)
                return _team_members_redirect(current_workspace, selected_team)
            team_member_forms["company"] = form
        elif action == "add_department_member":
            form = WorkspaceTeamDepartmentMemberForm(
                request.POST,
                workspace=current_workspace,
                prefix="team_department",
            )
            if form.is_valid():
                form.save(selected_team)
                return _team_members_redirect(current_workspace, selected_team)
            team_member_forms["department"] = form
        elif action == "add_user_member":
            form = WorkspaceTeamUserMemberForm(
                request.POST,
                workspace=current_workspace,
                prefix="team_user",
            )
            if form.is_valid():
                form.save(selected_team)
                return _team_members_redirect(current_workspace, selected_team)
            team_member_forms["user"] = form
        elif action == "remove_member":
            membership = get_object_or_404(
                WorkspaceTeamMember,
                pk=request.POST.get("membership_id"),
                team=selected_team,
            )
            membership.delete()
            return _team_members_redirect(current_workspace, selected_team)
        else:
            raise SuspiciousOperation("Unsupported team action.")

    context.update(
        {
            "selected_workspace_team": selected_team,
            "team_member_forms": team_member_forms,
            "team_member_entries": _build_workspace_team_member_entries(selected_team),
            "is_team_create_mode": False,
            "is_team_list_mode": False,
            "team_section": "members",
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

    _raise_for_company_workspace_settings(current_workspace)

    can_manage_workspace = _user_can_manage_workspace_settings(request.user, current_workspace)

    if request.method == "POST":
        if not can_manage_workspace:
            raise PermissionDenied("You do not have permission to update this workspace.")

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

    _raise_for_company_workspace_settings(current_workspace)

    can_manage_workspace = _user_can_manage_workspace_settings(request.user, current_workspace)

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
    _raise_for_company_workspace_settings(workspace)
    if not _user_can_manage_workspace_settings(request.user, workspace):
        raise PermissionDenied("You do not have permission to manage workspace access.")

    grant = get_object_or_404(WorkspaceAccessGrant, pk=grant_id, workspace=workspace)
    grant.delete()
    messages.success(request, "Access removed.")
    return _settings_access_redirect(workspace)
