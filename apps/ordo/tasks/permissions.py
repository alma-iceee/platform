"""Task mutation permission policy.

This module currently defines the planned public API only. It is not imported
by views and therefore does not change task authorization yet.

Task visibility belongs in selectors. Comments and discussion inherit task
visibility and do not need separate mutation roles at this stage.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.ordo.accounts.models import User

    from .models import Task, TaskBoard


def can_create_task(user: "User", board: "TaskBoard") -> bool:
    """Return whether the user may create a task on the board.

    Expected policy: CEO on every board; department chief on a project board
    only when that exact department participates in the project's hidden team.
    """
    raise NotImplementedError("Task permission policy is not implemented yet.")


def can_edit_task(user: "User", task: "Task") -> bool:
    """Return whether the user may edit user-facing task fields.

    Expected policy: CEO, or an eligible department chief for a project task.
    Being the author, assignee, or observer is not sufficient.
    """
    raise NotImplementedError("Task permission policy is not implemented yet.")


def can_manage_task_participants(user: "User", task: "Task") -> bool:
    """Return whether the user may change task assignees and observers.

    This is separate from general editing so participant management can evolve
    independently without granting broader task permissions.
    """
    raise NotImplementedError("Task permission policy is not implemented yet.")


def can_move_task(user: "User", task: "Task") -> bool:
    """Return whether the user may move the task between status columns.

    Expected policy: users with full task mutation permission, plus an assignee
    moving their own assigned task without gaining edit/participant rights.
    """
    raise NotImplementedError("Task permission policy is not implemented yet.")
