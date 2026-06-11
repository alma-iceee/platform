from django.urls import path

from .views import (
    workspace_chats,
    workspace_dashboard,
    workspace_projects,
    workspace_settings,
    workspace_storage,
    workspace_tasks,
    workspace_teams,
)


app_name = "workspaces"

urlpatterns = [
    path("", workspace_dashboard, name="shell"),
    path("dashboard/", workspace_dashboard, name="dashboard"),
    path("tasks/", workspace_tasks, name="tasks"),
    path("projects/", workspace_projects, name="projects"),
    path("teams/", workspace_teams, name="teams"),
    path("chats/", workspace_chats, name="chats"),
    path("storage/", workspace_storage, name="storage"),
    path("settings/", workspace_settings, name="settings"),
]
