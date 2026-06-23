"""Workspace permission policy boundary.

Permission functions should answer questions about actions rather than expose
role-specific helpers such as ``ceo_can`` or ``director_can``. Role checks are
implementation details that may contribute to the same action permission.

Planned rules:

* functions accept domain objects, never ``request``;
* functions return ``bool`` and never redirect or raise ``PermissionDenied``;
* views remain responsible for translating ``False`` into HTTP 403/404;
* visibility querysets are selectors and should not live in this module;
* workspace teams are hidden implementation details and must not have public
  view/create/edit permissions; only internal synchronization may mutate them;
* task permissions should live in ``apps.ordo.tasks.permissions`` because task
  create, edit, and move rules will diverge.
"""

from typing import TYPE_CHECKING

from apps.ordo.accounts.models import CompanyMembership

if TYPE_CHECKING:
    from apps.ordo.accounts.models import User

    from .models import Project, Workspace


def _is_ceo(user: "User") -> bool:
    return bool(
        user.is_authenticated
        and getattr(user, "system_role", None) == "ceo"
    )


def can_create_workspace(user: "User") -> bool:
    """Return whether the user may create a custom/cross-company workspace."""
    return _is_ceo(user)


def can_edit_workspace(user: "User", workspace: "Workspace") -> bool:
    """Return whether the user may edit the workspace itself.

    Company workspaces are system-managed and cannot be edited through the
    normal workspace UI.
    """
    return not workspace.company_id and can_create_workspace(user)


def can_manage_workspace_access(user: "User", workspace: "Workspace") -> bool:
    """Return whether the user may add or remove workspace access grants.

    Access follows the same boundary as workspace editing for now, but remains
    a separate action so the policies can diverge later without changing views.
    """
    return can_edit_workspace(user, workspace)


# Project policies are not connected to views yet. The current project views
# keep their existing checks until that migration is made separately.


def can_create_project(user: "User", workspace: "Workspace") -> bool:
    """Return whether the user may create a project in the workspace.

    Expected policy: CEO in every workspace; company director only in the
    company workspace belonging to that director's company.
    """
    if _is_ceo(user):
        return True
    if not user.is_authenticated or not workspace.company_id:
        return False
    return CompanyMembership.objects.filter(
        user=user,
        company_id=workspace.company_id,
        role=CompanyMembership.Role.DIRECTOR,
    ).exists()


def can_edit_project(user: "User", project: "Project") -> bool:
    """Return whether the user may edit the project's user-facing fields.

    Expected policy: the same role boundary as project creation, evaluated
    against the project's workspace.

    Hidden WorkspaceTeam internals are not part of this public permission.
    """
    return can_create_project(user, project.workspace)
