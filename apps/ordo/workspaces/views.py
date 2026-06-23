from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.ordo.accounts.models import CompanyMembership, DepartmentMembership
from apps.ordo.organizations.models import Department
from apps.ordo.tasks.forms import (
    TaskCommentCreateForm,
    TaskDiscussionMessageCreateForm,
    TaskForm,
)
from apps.ordo.tasks.models import (
    Task,
    TaskBoard,
    TaskComment,
    TaskCommentAttachment,
    TaskDiscussionMessage,
    TaskDiscussionMessageAttachment,
)
from apps.ordo.tasks.permissions import (
    can_create_task,
    can_edit_task,
    can_manage_task_participants,
    can_move_task,
)
from apps.ordo.tasks.selectors import task_board_user_queryset

from .forms import (
    WorkspaceCompanyAccessGrantForm,
    WorkspaceDepartmentAccessGrantForm,
    WorkspaceForm,
    WorkspaceGeneralForm,
    WorkspaceProjectForm,
    WorkspaceProjectTeamForm,
    WorkspaceUserAccessGrantForm,
)
from .models import (
    Project,
    Workspace,
    WorkspaceAccessGrant,
    WorkspaceTeam,
    WorkspaceTeamMember,
)
from .permissions import (
    can_change_project_team,
    can_create_project,
    can_create_workspace,
    can_edit_project,
    can_edit_workspace,
    can_manage_workspace_access,
)


PROJECT_COLOR_CLASSES = ("blue", "gold", "cyan", "orange", "purple")
TEAM_COLOR_CLASSES = ("blue", "purple", "cyan", "orange", "gold")

_FORM_ERROR_SESSION_KEY = "workspace_form_errors"


def _stash_invalid_form(request, scope, *, action="", open_modal=""):
    """Persist a failed POST so the next GET (after a redirect) can re-bind the
    form, render its errors, and re-open the right modal.

    This keeps every modal/inline form on the Post/Redirect/Get pattern: a failed
    submission redirects instead of rendering directly, so refreshing the page
    never triggers the browser's "Confirm form resubmission" warning.
    """
    bucket = request.session.get(_FORM_ERROR_SESSION_KEY, {})
    bucket[scope] = {
        "data": request.POST.urlencode(),
        "action": action,
        "open_modal": open_modal,
    }
    request.session[_FORM_ERROR_SESSION_KEY] = bucket
    request.session.modified = True


def _pop_invalid_form(request, scope):
    """Return and clear a stashed failed POST for ``scope`` (or ``None``)."""
    bucket = request.session.get(_FORM_ERROR_SESSION_KEY)
    if not bucket or scope not in bucket:
        return None
    entry = bucket.pop(scope)
    request.session[_FORM_ERROR_SESSION_KEY] = bucket
    request.session.modified = True
    return {
        "data": QueryDict(entry.get("data", ""), mutable=False),
        "action": entry.get("action", ""),
        "open_modal": entry.get("open_modal", ""),
    }


def _build_workspace_context(request, current_page: str, workspace_slug=None):
    workspaces = sorted(
        _visible_workspaces_queryset(request.user),
        key=lambda workspace: (workspace.company_id is None, workspace.name.lower()),
    )

    requested_workspace_slug = workspace_slug or request.GET.get("workspace")
    current_workspace = next(
        (workspace for workspace in workspaces if workspace.slug == requested_workspace_slug),
        None,
    )
    if workspace_slug and current_workspace is None:
        raise Http404("Workspace not found.")
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
            current_workspace and can_edit_workspace(request.user, current_workspace)
        ),
        "can_create_workspace": can_create_workspace(request.user),
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
        WorkspaceAccessGrant.objects.filter(workspace=workspace, is_system_generated=False)
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
    return redirect(reverse("workspaces:settings", args=[workspace.slug]))


def _settings_access_redirect(workspace):
    return redirect(reverse("workspaces:settings-members-access", args=[workspace.slug]))


def _tasks_redirect(workspace, board=None):
    url = reverse("workspaces:tasks", args=[workspace.slug])
    if board is not None:
        url = f"{url}?board={board.id}"
    return redirect(url)


def _default_task_board(workspace):
    return (
        TaskBoard.objects.filter(
            workspace=workspace,
            board_type=TaskBoard.BoardType.WORKSPACE,
        ).first()
        or TaskBoard.objects.filter(
            workspace=workspace,
            board_type=TaskBoard.BoardType.INBOX,
        ).first()
        or TaskBoard.objects.filter(workspace=workspace).order_by("board_type", "name", "id").first()
    )


def _selected_task_board_from_request(request, workspace):
    board_id = request.POST.get("board") or request.GET.get("board")
    if board_id and board_id.isdigit():
        board = TaskBoard.objects.filter(workspace=workspace, id=int(board_id)).first()
        if board is not None:
            return board
    return _default_task_board(workspace)


def _add_form_errors_to_messages(request, form):
    for field_name, errors in form.errors.items():
        field = form.fields.get(field_name)
        label = field.label if field is not None else field_name
        for error in errors:
            messages.error(request, f"{label}: {error}")


def _is_ajax_request(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _task_move_error(request, workspace, board, message, status=400):
    if _is_ajax_request(request):
        return JsonResponse({"ok": False, "error": message}, status=status)
    messages.error(request, message)
    return _tasks_redirect(workspace, board)


def _accessible_task_or_404(user, workspace_slug, task_id):
    workspace = get_object_or_404(
        _visible_workspaces_queryset(user),
        slug=workspace_slug,
    )
    task = get_object_or_404(
        Task.objects.select_related("workspace", "board", "board__department", "board__project"),
        pk=task_id,
        workspace=workspace,
    )

    if _user_can_manage_workspace(user, workspace):
        return task
    if task.board.board_type in (TaskBoard.BoardType.INBOX, TaskBoard.BoardType.WORKSPACE):
        return task
    if (
        task.board.board_type == TaskBoard.BoardType.DEPARTMENT
        and _visible_workspace_departments_queryset(workspace, user)
        .filter(pk=task.board.department_id)
        .exists()
    ):
        return task
    if (
        task.board.board_type == TaskBoard.BoardType.PROJECT
        and _visible_workspace_projects_queryset(workspace, user)
        .filter(pk=task.board.project_id)
        .exists()
    ):
        return task
    raise Http404("Task not found.")


def _serialize_task_user(user):
    if user is None:
        return None
    return {
        "id": user.id,
        "name": user.full_name or user.email,
        "email": user.email,
        "system_role": user.system_role,
        "system_role_label": user.get_system_role_display(),
    }


def _serialize_task_attachment(attachment):
    return {
        "id": attachment.id,
        "name": attachment.original_name or attachment.file.name.rsplit("/", 1)[-1],
        "url": attachment.file.url,
        "created_at": attachment.created_at.isoformat(),
    }


def _serialize_task_comment(comment, current_user):
    return {
        "id": comment.id,
        "body": comment.body,
        "author": _serialize_task_user(comment.author),
        "is_own": comment.author_id == current_user.id,
        "created_at": comment.created_at.isoformat(),
        "updated_at": comment.updated_at.isoformat(),
        "attachments": [
            _serialize_task_attachment(attachment)
            for attachment in comment.attachments.all()
        ],
    }


def _serialize_task_discussion_message(message, current_user):
    return {
        "id": message.id,
        "body": message.body,
        "author": _serialize_task_user(message.author),
        "is_own": message.author_id == current_user.id,
        "created_at": message.created_at.isoformat(),
        "updated_at": message.updated_at.isoformat(),
        "attachments": [
            _serialize_task_attachment(attachment)
            for attachment in message.attachments.all()
        ],
    }


def _task_collaboration_form_error(form):
    errors = form.errors.get_json_data()
    first_error = next(
        (
            error["message"]
            for field_errors in errors.values()
            for error in field_errors
        ),
        "Invalid request.",
    )
    return JsonResponse({"ok": False, "error": first_error, "errors": errors}, status=400)


def _build_access_grant_forms(*, workspace=None, disabled=False):
    return {
        "company": WorkspaceCompanyAccessGrantForm(workspace=workspace, disabled=disabled),
        "department": WorkspaceDepartmentAccessGrantForm(workspace=workspace, disabled=disabled),
        "user": WorkspaceUserAccessGrantForm(workspace=workspace, disabled=disabled),
    }


def _get_selected_workspace(request, workspace_slug=None):
    return _build_workspace_context(
        request,
        current_page="settings",
        workspace_slug=workspace_slug,
    )["current_workspace"]


def _handle_access_grant_form(
    request,
    form_class,
    modal_id,
    form_key,
    workspace_slug=None,
):
    workspace = _get_selected_workspace(request, workspace_slug)
    if workspace is None:
        return redirect("workspaces:settings-members-access")
    _raise_for_company_workspace_settings(workspace)
    if not can_manage_workspace_access(request.user, workspace):
        raise PermissionDenied("You do not have permission to manage workspace access.")

    form = form_class(request.POST, workspace=workspace)
    if form.is_valid():
        form.save(workspace)
        messages.success(request, "Access granted.")
        return _settings_access_redirect(workspace)

    # Invalid: stash the submission and redirect so the GET re-opens this modal
    # with the bound form's errors (Post/Redirect/Get, no resubmission warning).
    _stash_invalid_form(request, "members_access", action=form_key, open_modal=modal_id)
    return _settings_access_redirect(workspace)


def workspace_dashboard(request, workspace_slug=None):
    context = _build_workspace_context(
        request,
        current_page="dashboard",
        workspace_slug=workspace_slug,
    )
    current_workspace = context["current_workspace"]
    if (
        workspace_slug is None
        and current_workspace is not None
        and request.resolver_match.url_name == "shell"
    ):
        return redirect(reverse("workspaces:dashboard", args=[current_workspace.slug]))
    context["dashboard_stats"] = {
        "departments": len(context["department_items"]),
        "projects": len(context["project_items"]),
        "teams": len(context["team_items"]),
        "access_entries": (
            current_workspace.access_grants.count() if current_workspace is not None else 0
        ),
    }
    context["can_manage_workspace"] = (
        current_workspace is not None
        and can_create_project(request.user, current_workspace)
    )
    return render(request, "workspaces/dashboard/dashboard.html", context)


@login_required
def workspace_create(request):
    if not can_create_workspace(request.user):
        raise PermissionDenied("Only CEO users can create workspaces.")

    context = _build_workspace_context(request, current_page="workspace_create")

    if request.method == "POST":
        workspace_form = WorkspaceForm(request.POST)
        if workspace_form.is_valid():
            with transaction.atomic():
                workspace = workspace_form.save()
                _create_workspace_creator_access(workspace, request.user)
            return redirect(reverse("workspaces:dashboard", args=[workspace.slug]))
        _stash_invalid_form(request, "workspace_create")
        return redirect(reverse("workspaces:workspace_create"))
    else:
        stashed = _pop_invalid_form(request, "workspace_create")
        workspace_form = WorkspaceForm(stashed["data"]) if stashed is not None else WorkspaceForm()

    current_workspace = context["current_workspace"]
    cancel_url = (
        reverse("workspaces:dashboard", args=[current_workspace.slug])
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


def workspace_tasks(request, workspace_slug=None):
    context = _build_workspace_context(request, current_page="tasks", workspace_slug=workspace_slug)
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

    task_users = []
    if selected_board is not None:
        task_users = list(task_board_user_queryset(selected_board))

    # Move permission is uniform across a board, so a representative task is enough
    # to expose it as a board-level presentation flag (cards are gated, not the page).
    sample_task = next(
        (task for entry in board_columns for task in entry["tasks"]),
        None,
    )

    context.update(
        {
            "inbox_board_item": _board_item(inbox_board) if inbox_board else None,
            "workspace_board_item": _board_item(workspace_board) if workspace_board else None,
            "department_board_items": [_board_item(b) for b in department_boards],
            "project_board_items": [_board_item(b) for b in project_boards],
            "selected_board": selected_board,
            "board_columns": board_columns,
            "task_users": task_users,
            "task_priorities": Task.Priority.choices,
            # Full-mutation boundary (create == edit == participants per tasks.permissions).
            "can_mutate_tasks": bool(
                selected_board and can_create_task(request.user, selected_board)
            ),
            # Broader than mutation: any working member may move tasks on an accessible board.
            "can_move_tasks": bool(sample_task and can_move_task(request.user, sample_task)),
        }
    )
    return render(request, "workspaces/tasks/tasks.html", context)


@login_required
def workspace_task_create(request, workspace_slug=None):
    context = _build_workspace_context(request, current_page="tasks", workspace_slug=workspace_slug)
    current_workspace = context["current_workspace"]
    if current_workspace is None:
        return redirect("workspaces:tasks")

    selected_board = _selected_task_board_from_request(request, current_workspace)
    if selected_board is None:
        messages.error(request, "Task board is required.")
        return _tasks_redirect(current_workspace)

    if request.method != "POST":
        return _tasks_redirect(current_workspace, selected_board)
    if not can_create_task(request.user, selected_board):
        raise PermissionDenied("You do not have permission to create tasks on this board.")

    form = TaskForm(
        request.POST,
        workspace=current_workspace,
        selected_board=selected_board,
    )
    if form.is_valid():
        if not can_create_task(request.user, form.cleaned_data["board"]):
            raise PermissionDenied("You do not have permission to create tasks on this board.")
        task = form.save(actor=request.user)
        messages.success(request, "Task created.")
        return _tasks_redirect(current_workspace, task.board)

    _add_form_errors_to_messages(request, form)
    return _tasks_redirect(current_workspace, selected_board)


@login_required
def workspace_task_edit(request, task_id, workspace_slug=None):
    context = _build_workspace_context(request, current_page="tasks", workspace_slug=workspace_slug)
    current_workspace = context["current_workspace"]
    if current_workspace is None:
        return redirect("workspaces:tasks")

    task = _accessible_task_or_404(request.user, current_workspace.slug, task_id)

    if request.method != "POST":
        return _tasks_redirect(current_workspace, task.board)
    if not (
        can_edit_task(request.user, task)
        and can_manage_task_participants(request.user, task)
    ):
        raise PermissionDenied("You do not have permission to edit this task.")

    form = TaskForm(
        request.POST,
        workspace=current_workspace,
        selected_board=task.board,
        instance=task,
    )
    if form.is_valid():
        if not can_create_task(request.user, form.cleaned_data["board"]):
            raise PermissionDenied("You do not have permission to move this task to that board.")
        task = form.save(actor=request.user)
        messages.success(request, "Task updated.")
        return _tasks_redirect(current_workspace, task.board)

    _add_form_errors_to_messages(request, form)
    return _tasks_redirect(current_workspace, task.board)


@login_required
def workspace_task_move(request, task_id, workspace_slug=None):
    context = _build_workspace_context(request, current_page="tasks", workspace_slug=workspace_slug)
    current_workspace = context["current_workspace"]
    if current_workspace is None:
        if _is_ajax_request(request):
            return JsonResponse({"ok": False, "error": "Workspace is required."}, status=404)
        return redirect("workspaces:tasks")

    task = _accessible_task_or_404(request.user, current_workspace.slug, task_id)

    if request.method != "POST":
        return _tasks_redirect(current_workspace, task.board)
    if not can_move_task(request.user, task):
        return _task_move_error(
            request,
            current_workspace,
            task.board,
            "You do not have permission to move this task.",
            status=403,
        )

    column_id = request.POST.get("column")
    if not column_id or not column_id.isdigit():
        return _task_move_error(request, current_workspace, task.board, "Task column is required.")

    column = task.board.columns.filter(id=int(column_id)).first()
    if column is None:
        return _task_move_error(
            request,
            current_workspace,
            task.board,
            "Task column must belong to the task board.",
        )

    raw_position = request.POST.get("position")
    position = task.position
    if raw_position not in (None, ""):
        try:
            position = max(0, int(raw_position))
        except ValueError:
            return _task_move_error(
                request,
                current_workspace,
                task.board,
                "Task position must be a number.",
            )

    task.column = column
    task.position = position
    task.save(update_fields=["column", "position", "updated_at"])

    if _is_ajax_request(request):
        return JsonResponse(
            {
                "ok": True,
                "task": {
                    "id": task.id,
                    "board": task.board_id,
                    "column": task.column_id,
                    "position": task.position,
                },
            }
        )

    messages.success(request, "Task moved.")
    return _tasks_redirect(current_workspace, task.board)


@login_required
def workspace_task_collaboration(request, workspace_slug, task_id):
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "GET is required."}, status=405)

    task = _accessible_task_or_404(request.user, workspace_slug, task_id)
    comments = (
        task.comments.select_related("author")
        .prefetch_related("attachments")
        .order_by("created_at", "id")
    )
    discussion = task.discussion
    discussion_messages = (
        discussion.messages.select_related("author")
        .prefetch_related("attachments")
        .order_by("created_at", "id")
    )

    return JsonResponse(
        {
            "ok": True,
            "task": {"id": task.id, "title": task.title},
            "current_user": _serialize_task_user(request.user),
            "comments": [
                _serialize_task_comment(comment, request.user) for comment in comments
            ],
            "discussion": {
                "id": discussion.id,
                "messages": [
                    _serialize_task_discussion_message(message, request.user)
                    for message in discussion_messages
                ],
            },
        }
    )


@login_required
def workspace_task_comment_create(request, workspace_slug, task_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST is required."}, status=405)

    task = _accessible_task_or_404(request.user, workspace_slug, task_id)
    form = TaskCommentCreateForm(request.POST, request.FILES)
    if not form.is_valid():
        return _task_collaboration_form_error(form)

    with transaction.atomic():
        comment = TaskComment.objects.create(
            task=task,
            author=request.user,
            body=form.cleaned_data["body"],
        )
        for uploaded_file in form.cleaned_data["attachments"]:
            TaskCommentAttachment.objects.create(
                comment=comment,
                file=uploaded_file,
                original_name=uploaded_file.name[:255],
                uploaded_by=request.user,
            )

    comment = (
        TaskComment.objects.select_related("author")
        .prefetch_related("attachments")
        .get(pk=comment.pk)
    )
    return JsonResponse(
        {"ok": True, "comment": _serialize_task_comment(comment, request.user)},
        status=201,
    )


@login_required
def workspace_task_discussion_message_create(request, workspace_slug, task_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST is required."}, status=405)

    task = _accessible_task_or_404(request.user, workspace_slug, task_id)
    form = TaskDiscussionMessageCreateForm(request.POST, request.FILES)
    if not form.is_valid():
        return _task_collaboration_form_error(form)

    with transaction.atomic():
        message = TaskDiscussionMessage.objects.create(
            discussion=task.discussion,
            author=request.user,
            body=form.cleaned_data["body"],
        )
        for uploaded_file in form.cleaned_data["attachments"]:
            TaskDiscussionMessageAttachment.objects.create(
                message=message,
                file=uploaded_file,
                original_name=uploaded_file.name[:255],
                uploaded_by=request.user,
            )

    message = (
        TaskDiscussionMessage.objects.select_related("author")
        .prefetch_related("attachments")
        .get(pk=message.pk)
    )
    return JsonResponse(
        {
            "ok": True,
            "message": _serialize_task_discussion_message(message, request.user),
        },
        status=201,
    )


def workspace_departments(request, workspace_slug=None):
    context = _build_workspace_context(
        request,
        current_page="departments",
        workspace_slug=workspace_slug,
    )
    current_workspace = context["current_workspace"]
    if current_workspace is not None and not context["shows_department_navigation"]:
        return redirect(reverse("workspaces:dashboard", args=[current_workspace.slug]))
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
    args = [project.slug] if project else []
    return redirect(reverse(route_name, args=[workspace.slug, *args]))


def _project_section_redirect(workspace, project, section="general"):
    route_name = {
        "general": "workspaces:project-general",
        "members": "workspaces:project-members",
        "overview": "workspaces:project-detail",
    }.get(section, "workspaces:project-detail")
    return redirect(reverse(route_name, args=[workspace.slug, project.slug]))


def workspace_projects(request, workspace_slug=None, project_slug=None, mode="list"):
    context = _build_workspace_context(
        request,
        current_page="projects",
        workspace_slug=workspace_slug,
    )
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
    if project_slug is not None:
        selected_project = get_object_or_404(
            _visible_workspace_projects_queryset(current_workspace, request.user).select_related(
                "team",
                "created_by",
            ),
            workspace=current_workspace,
            slug=project_slug,
        )

    can_manage_workspace = (
        can_edit_project(request.user, selected_project)
        if selected_project is not None
        else can_create_project(request.user, current_workspace)
    )
    can_change_team = bool(
        selected_project and can_change_project_team(request.user, selected_project)
    )
    project_form = None
    project_team_form = None

    if mode == "create":
        if request.method == "POST":
            if not can_create_project(request.user, current_workspace):
                raise PermissionDenied("You do not have permission to manage workspace projects.")
            project_form = WorkspaceProjectForm(
                request.POST,
                workspace=current_workspace,
                created_by=request.user,
            )
            if project_form.is_valid():
                project = project_form.save()
                return _project_section_redirect(current_workspace, project, "overview")
            _stash_invalid_form(request, "project_create")
            return _projects_redirect(current_workspace)
        else:
            project_form = WorkspaceProjectForm(
                workspace=current_workspace,
                created_by=request.user,
                disabled=not can_manage_workspace,
            )
    elif mode in {"general", "members"}:
        if request.method == "POST":
            action = request.POST.get("action", "save_details")
            if action == "save_team":
                if not can_change_team:
                    raise PermissionDenied("Only the CEO may change a project's team.")
                project_team_form = WorkspaceProjectTeamForm(
                    request.POST,
                    workspace=current_workspace,
                    instance=selected_project,
                )
                if project_team_form.is_valid():
                    project_team_form.save()
                    return _project_section_redirect(current_workspace, selected_project, "members")
                _stash_invalid_form(
                    request, f"project_edit:{selected_project.id}", action="save_team"
                )
                return _project_section_redirect(current_workspace, selected_project, "members")
            elif action == "save_details":
                if not can_edit_project(request.user, selected_project):
                    raise PermissionDenied("You do not have permission to manage workspace projects.")
                project_form = WorkspaceProjectForm(
                    request.POST,
                    workspace=current_workspace,
                    created_by=request.user,
                    instance=selected_project,
                )
                if project_form.is_valid():
                    project_form.save()
                    return _project_section_redirect(current_workspace, selected_project, "general")
                _stash_invalid_form(
                    request, f"project_edit:{selected_project.id}", action="save_details"
                )
                return _project_section_redirect(current_workspace, selected_project, "general")
            else:
                raise SuspiciousOperation("Unsupported project action.")
        else:
            stashed = _pop_invalid_form(request, f"project_edit:{selected_project.id}")
            if mode == "general":
                if stashed is not None and stashed["action"] == "save_details":
                    project_form = WorkspaceProjectForm(
                        stashed["data"],
                        workspace=current_workspace,
                        created_by=request.user,
                        instance=selected_project,
                    )
                else:
                    project_form = WorkspaceProjectForm(
                        workspace=current_workspace,
                        instance=selected_project,
                        disabled=not can_manage_workspace,
                    )
            else:  # members
                if stashed is not None and stashed["action"] == "save_team":
                    project_team_form = WorkspaceProjectTeamForm(
                        stashed["data"],
                        workspace=current_workspace,
                        instance=selected_project,
                        disabled=not can_change_team,
                    )
                else:
                    project_team_form = WorkspaceProjectTeamForm(
                        workspace=current_workspace,
                        instance=selected_project,
                        disabled=not can_change_team,
                    )

    if mode not in {"create", "general", "members"} and project_form is None:
        # List page: re-bind a failed "New project" submission so the create
        # modal re-opens with its errors after the redirect.
        stashed = _pop_invalid_form(request, "project_create")
        if stashed is not None and can_manage_workspace:
            project_form = WorkspaceProjectForm(
                stashed["data"],
                workspace=current_workspace,
                created_by=request.user,
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
            "can_change_project_team": can_change_team,
            "project_team_member_entries": (
                _build_workspace_team_member_entries(selected_project.team)
                if selected_project and selected_project.team_id
                else []
            ),
        }
    )

    if selected_project is None:
        template_name = "workspaces/projects/projects.html"
    elif mode == "general":
        template_name = "workspaces/projects/general.html"
    elif mode == "members":
        template_name = "workspaces/projects/members.html"
    else:
        template_name = "workspaces/projects/overview.html"
    return render(request, template_name, context)


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


@require_GET
def workspace_teams(request, workspace_slug=None, team_id=None):
    context = _build_workspace_context(request, current_page="teams", workspace_slug=workspace_slug)
    current_workspace = context["current_workspace"]

    if current_workspace is None:
        context.update(
            {
                "workspace_team_items": [],
                "selected_workspace_team": None,
                "team_member_entries": [],
                "is_team_list_mode": True,
                "team_section": "overview",
            }
        )
        return render(request, "workspaces/teams/teams.html", context)

    selected_team = None
    if team_id is not None:
        selected_team = get_object_or_404(
            _visible_workspace_teams_queryset(current_workspace, request.user),
            pk=team_id,
        )

    context.update(
        {
            "workspace_team_items": _build_workspace_team_items(
                current_workspace,
                request.user,
                selected_team,
            ),
            "selected_workspace_team": selected_team,
            "team_member_entries": (
                _build_workspace_team_member_entries(selected_team) if selected_team else []
            ),
            "is_team_list_mode": team_id is None,
            "team_section": "overview",
        }
    )
    return render(request, "workspaces/teams/teams.html", context)


@require_GET
def workspace_team_members(request, team_id, workspace_slug=None):
    context = _build_workspace_context(request, current_page="teams", workspace_slug=workspace_slug)
    current_workspace = context["current_workspace"]

    if current_workspace is None:
        return redirect("workspaces:teams")

    selected_team = get_object_or_404(
        _visible_workspace_teams_queryset(current_workspace, request.user),
        pk=team_id,
    )

    context.update(
        {
            "selected_workspace_team": selected_team,
            "team_member_entries": _build_workspace_team_member_entries(selected_team),
            "is_team_list_mode": False,
            "team_section": "members",
        }
    )
    return render(request, "workspaces/teams/teams.html", context)


def workspace_chats(request, workspace_slug=None):
    context = _build_workspace_context(request, current_page="chats", workspace_slug=workspace_slug)
    return render(request, "workspaces/chats/chats.html", context)


def workspace_storage(request, workspace_slug=None):
    context = _build_workspace_context(request, current_page="storage", workspace_slug=workspace_slug)
    return render(request, "workspaces/storage/storage.html", context)


def workspace_settings(request, workspace_slug=None):
    context = _build_workspace_context(request, current_page="settings", workspace_slug=workspace_slug)
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

    can_manage_workspace = can_edit_workspace(request.user, current_workspace)

    if request.method == "POST":
        if not can_manage_workspace:
            raise PermissionDenied("You do not have permission to update this workspace.")

        workspace_form = WorkspaceGeneralForm(request.POST, instance=current_workspace)
        if workspace_form.is_valid():
            workspace_form.save()
            return redirect(request.path)
        _stash_invalid_form(request, f"settings_general:{current_workspace.slug}")
        return redirect(request.path)
    else:
        stashed = _pop_invalid_form(request, f"settings_general:{current_workspace.slug}")
        if stashed is not None and can_manage_workspace:
            workspace_form = WorkspaceGeneralForm(stashed["data"], instance=current_workspace)
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


def _fill_members_access_context(context, workspace, can_manage, *, forms=None, open_modal=""):
    entries = _build_workspace_access_grant_entries(workspace)
    context.update(
        {
            "access_grant_entries": entries,
            "access_user_entries": [e for e in entries if e["type"] == "user"],
            "access_department_entries": [e for e in entries if e["type"] == "department"],
            "access_company_entries": [e for e in entries if e["type"] == "company"],
            "access_grant_forms": forms
            or _build_access_grant_forms(workspace=workspace, disabled=not can_manage),
            "can_manage_workspace": can_manage,
            "open_grant_modal": open_modal,
        }
    )
    return context


def workspace_settings_members_access(request, workspace_slug=None):
    context = _build_workspace_context(request, current_page="settings", workspace_slug=workspace_slug)
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

    can_manage_workspace = can_manage_workspace_access(request.user, current_workspace)

    forms = None
    open_modal = ""
    stashed = _pop_invalid_form(request, "members_access")
    if stashed is not None and can_manage_workspace:
        form_classes = {
            "company": WorkspaceCompanyAccessGrantForm,
            "department": WorkspaceDepartmentAccessGrantForm,
            "user": WorkspaceUserAccessGrantForm,
        }
        form_class = form_classes.get(stashed["action"])
        if form_class is not None:
            forms = _build_access_grant_forms(workspace=current_workspace)
            forms[stashed["action"]] = form_class(stashed["data"], workspace=current_workspace)
            open_modal = stashed["open_modal"]

    _fill_members_access_context(
        context, current_workspace, can_manage_workspace, forms=forms, open_modal=open_modal
    )
    return render(request, "workspaces/settings/members_access.html", context)


def add_company_access_grant(request, workspace_slug=None):
    if request.method != "POST":
        return redirect("workspaces:settings-members-access")
    return _handle_access_grant_form(
        request, WorkspaceCompanyAccessGrantForm, "add-company-modal", "company", workspace_slug
    )


def add_department_access_grant(request, workspace_slug=None):
    if request.method != "POST":
        return redirect("workspaces:settings-members-access")
    return _handle_access_grant_form(
        request,
        WorkspaceDepartmentAccessGrantForm,
        "add-department-modal",
        "department",
        workspace_slug,
    )


def add_user_access_grant(request, workspace_slug=None):
    if request.method != "POST":
        return redirect("workspaces:settings-members-access")
    return _handle_access_grant_form(
        request, WorkspaceUserAccessGrantForm, "add-user-modal", "user", workspace_slug
    )


def remove_access_grant(request, grant_id, workspace_slug=None):
    workspace = _get_selected_workspace(request, workspace_slug)
    if request.method != "POST" or workspace is None:
        return redirect("workspaces:settings-members-access")
    _raise_for_company_workspace_settings(workspace)
    if not can_manage_workspace_access(request.user, workspace):
        raise PermissionDenied("You do not have permission to manage workspace access.")

    grant = get_object_or_404(WorkspaceAccessGrant, pk=grant_id, workspace=workspace)
    grant.delete()
    messages.success(request, "Access removed.")
    return _settings_access_redirect(workspace)
