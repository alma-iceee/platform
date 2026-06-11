"""
URL configuration for config project.
"""

from django.contrib import admin
from django.urls import include, path
from apps.ordo.workspaces.views import (
    workspace_chats,
    workspace_dashboard,
    workspace_projects,
    workspace_settings,
    workspace_storage,
    workspace_tasks,
    workspace_teams,
)

urlpatterns = [
    path("workspaces/", include("apps.ordo.workspaces.urls")),
    path("app/", workspace_dashboard, name="workspace-shell-app"),
    path("app/dashboard/", workspace_dashboard, name="workspace-dashboard-app"),
    path("app/tasks/", workspace_tasks, name="workspace-tasks-app"),
    path("app/projects/", workspace_projects, name="workspace-projects-app"),
    path("app/teams/", workspace_teams, name="workspace-teams-app"),
    path("app/chats/", workspace_chats, name="workspace-chats-app"),
    path("app/storage/", workspace_storage, name="workspace-storage-app"),
    path("app/settings/", workspace_settings, name="workspace-settings-app"),
    path('admin/', admin.site.urls),
]
