from django.urls import path

from .views import (
    add_company_access_grant,
    add_department_access_grant,
    add_user_access_grant,
    remove_access_grant,
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
    path("settings/access/company/", add_company_access_grant, name="add-company-access"),
    path("settings/access/department/", add_department_access_grant, name="add-department-access"),
    path("settings/access/user/", add_user_access_grant, name="add-user-access"),
    path("settings/access/<int:grant_id>/remove/", remove_access_grant, name="remove-access"),
]
