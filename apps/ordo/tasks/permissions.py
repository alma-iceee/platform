"""Task mutation permission policy.

Task visibility belongs in selectors. Comments and discussion inherit task
visibility and do not need separate mutation roles at this stage.
"""

from typing import TYPE_CHECKING

from django.db.models import Q

from apps.ordo.accounts.models import CompanyMembership, DepartmentMembership
from apps.ordo.workspaces.models import WorkspaceAccessGrant

from .models import TaskBoard

if TYPE_CHECKING:
    from apps.ordo.accounts.models import User

    from .models import Task


_WORKING_ACCESS_ROLES = (
    WorkspaceAccessGrant.Role.OWNER,
    WorkspaceAccessGrant.Role.ADMIN,
    WorkspaceAccessGrant.Role.MEMBER,
)


def _is_ceo(user: "User") -> bool:
    return bool(
        user.is_authenticated
        and getattr(user, "system_role", None) == "ceo"
    )


def _matching_workspace_grants(user: "User", workspace):
    company_ids = CompanyMembership.objects.filter(user=user).values_list(
        "company_id", flat=True
    )
    department_ids = DepartmentMembership.objects.filter(user=user).values_list(
        "department_id", flat=True
    )
    return WorkspaceAccessGrant.objects.filter(
        workspace=workspace,
        role__in=_WORKING_ACCESS_ROLES,
    ).filter(
        Q(user=user)
        | Q(company_id__in=company_ids)
        | Q(department_id__in=department_ids)
    )


def _has_workspace_access(user: "User", workspace) -> bool:
    if not user.is_authenticated:
        return False
    if _is_ceo(user):
        return True
    if workspace.company_id and CompanyMembership.objects.filter(
        user=user,
        company_id=workspace.company_id,
    ).exists():
        return True
    return _matching_workspace_grants(user, workspace).exists()


def _can_manage_all_workspace_boards(user: "User", workspace) -> bool:
    if _is_ceo(user):
        return True
    if workspace.company_id and CompanyMembership.objects.filter(
        user=user,
        company_id=workspace.company_id,
        role=CompanyMembership.Role.DIRECTOR,
    ).exists():
        return True
    return _matching_workspace_grants(user, workspace).filter(
        role__in=(WorkspaceAccessGrant.Role.OWNER, WorkspaceAccessGrant.Role.ADMIN)
    ).exists()


def _can_access_board(user: "User", board: "TaskBoard") -> bool:
    if not _has_workspace_access(user, board.workspace):
        return False
    if _can_manage_all_workspace_boards(user, board.workspace):
        return True
    if board.board_type in (TaskBoard.BoardType.INBOX, TaskBoard.BoardType.WORKSPACE):
        return True
    if board.board_type == TaskBoard.BoardType.DEPARTMENT:
        return DepartmentMembership.objects.filter(
            user=user,
            department_id=board.department_id,
        ).exists()
    if board.board_type == TaskBoard.BoardType.PROJECT and board.project.team_id:
        return _matching_workspace_grants(user, board.workspace).filter(
            team_memberships__team_id=board.project.team_id,
        ).exists()
    return False


def _chief_can_manage_board(user: "User", board: "TaskBoard") -> bool:
    if board.board_type == TaskBoard.BoardType.DEPARTMENT:
        return DepartmentMembership.objects.filter(
            user=user,
            department_id=board.department_id,
            role=DepartmentMembership.Role.CHIEF,
        ).exists()
    if board.board_type == TaskBoard.BoardType.PROJECT and board.project.team_id:
        return DepartmentMembership.objects.filter(
            user=user,
            role=DepartmentMembership.Role.CHIEF,
            department__workspace_access_grants__role__in=_WORKING_ACCESS_ROLES,
            department__workspace_access_grants__team_memberships__team_id=(
                board.project.team_id
            ),
        ).exists()
    return False


def _can_fully_manage_board(user: "User", board: "TaskBoard") -> bool:
    if _is_ceo(user):
        return True
    if not _can_access_board(user, board):
        return False
    if board.workspace.company_id and CompanyMembership.objects.filter(
        user=user,
        company_id=board.workspace.company_id,
        role=CompanyMembership.Role.DIRECTOR,
    ).exists():
        return True
    return _chief_can_manage_board(user, board)


def can_create_task(user: "User", board: "TaskBoard") -> bool:
    """Return whether the user may create a task on the board.

    CEO can create everywhere. A company director can create in that company's
    company workspace. A department chief can create on their department board
    and project boards where that exact department participates.
    """
    return _can_fully_manage_board(user, board)


def can_edit_task(user: "User", task: "Task") -> bool:
    """Return whether the user may edit user-facing task fields.

    Expected policy: the same full-mutation boundary as task creation. Being
    the author, assignee, or observer is not sufficient.
    """
    return _can_fully_manage_board(user, task.board)


def can_manage_task_participants(user: "User", task: "Task") -> bool:
    """Return whether the user may change task assignees and observers.

    This is separate from general editing so participant management can evolve
    independently without granting broader task permissions.
    """
    return can_edit_task(user, task)


def can_move_task(user: "User", task: "Task") -> bool:
    """Return whether the user may move the task between status columns.

    Any working member may move a task on a board they can access. Assignment
    is not required; inaccessible workspaces and boards remain unavailable.
    """
    return _can_access_board(user, task.board)
