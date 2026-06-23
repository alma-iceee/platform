"""Read-side selectors for task-related user scopes."""

from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.ordo.accounts.models import CompanyMembership
from apps.ordo.workspaces.models import WorkspaceAccessGrant

from .models import TaskBoard


_WORKING_ACCESS_ROLES = (
    WorkspaceAccessGrant.Role.OWNER,
    WorkspaceAccessGrant.Role.ADMIN,
    WorkspaceAccessGrant.Role.MEMBER,
)


def _matching_grant_q(workspace, roles, *, team_id=None):
    query = Q()
    grant_paths = (
        "workspace_access_grants",
        "company_memberships__company__workspace_access_grants",
        "department_memberships__department__workspace_access_grants",
    )
    for path in grant_paths:
        criteria = {
            f"{path}__workspace": workspace,
            f"{path}__role__in": roles,
        }
        if team_id is not None:
            criteria[f"{path}__team_memberships__team_id"] = team_id
        query |= Q(**criteria)
    return query


def _workspace_user_q(workspace):
    query = Q(system_role="ceo") | _matching_grant_q(
        workspace,
        _WORKING_ACCESS_ROLES,
    )
    if workspace.company_id:
        query |= Q(company_memberships__company_id=workspace.company_id)
    return query


def _workspace_manager_q(workspace):
    query = Q(system_role="ceo") | _matching_grant_q(
        workspace,
        (WorkspaceAccessGrant.Role.OWNER, WorkspaceAccessGrant.Role.ADMIN),
    )
    if workspace.company_id:
        query |= Q(
            company_memberships__company_id=workspace.company_id,
            company_memberships__role=CompanyMembership.Role.DIRECTOR,
        )
    return query


def task_board_user_queryset(board: TaskBoard):
    """Return active users who can work with tasks on ``board``.

    The selector intentionally excludes viewer-only grants. It mirrors the
    working-access boundary used by task move permissions and is shared by the
    task form and its people-picker context.
    """
    users = get_user_model().objects.filter(is_active=True)
    workspace_user_q = _workspace_user_q(board.workspace)

    if board.board_type in (TaskBoard.BoardType.INBOX, TaskBoard.BoardType.WORKSPACE):
        board_user_q = workspace_user_q
    elif board.board_type == TaskBoard.BoardType.DEPARTMENT:
        board_user_q = workspace_user_q & (
            _workspace_manager_q(board.workspace)
            | Q(department_memberships__department_id=board.department_id)
        )
    elif board.board_type == TaskBoard.BoardType.PROJECT:
        project_user_q = _workspace_manager_q(board.workspace)
        if board.project.team_id:
            project_user_q |= _matching_grant_q(
                board.workspace,
                _WORKING_ACCESS_ROLES,
                team_id=board.project.team_id,
            )
        board_user_q = workspace_user_q & project_user_q
    else:
        return users.none()

    return users.filter(board_user_q).distinct().order_by("full_name", "email")
