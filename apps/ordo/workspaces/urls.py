from django.urls import path

from .views import (
    add_company_access_grant,
    add_department_access_grant,
    add_user_access_grant,
    remove_access_grant,
    workspace_chats,
    workspace_create,
    workspace_dashboard,
    workspace_departments,
    workspace_projects,
    workspace_settings,
    workspace_settings_members_access,
    workspace_storage,
    workspace_tasks,
    workspace_team_members,
    workspace_teams,
)


app_name = "workspaces"

urlpatterns = [
    path("", workspace_dashboard, name="shell"),
    path("new/", workspace_create, name="workspace_create"),
    path("dashboard/", workspace_dashboard, name="dashboard"),
    path("departments/", workspace_departments, name="departments"),
    path("tasks/", workspace_tasks, name="tasks"),
    path("projects/", workspace_projects, name="projects"),
    path("projects/new/", workspace_projects, {"mode": "create"}, name="project-create"),
    path("projects/<int:project_id>/", workspace_projects, name="project-detail"),
    path("projects/<int:project_id>/edit/", workspace_projects, {"mode": "edit"}, name="project-edit"),
    path("teams/", workspace_teams, name="teams"),
    path("teams/<int:team_id>/", workspace_teams, name="team-detail"),
    path("teams/<int:team_id>/members/", workspace_team_members, name="team-members"),
    path("chats/", workspace_chats, name="chats"),
    path("storage/", workspace_storage, name="storage"),
    path("settings/", workspace_settings, name="settings"),
    path("settings/members-access/", workspace_settings_members_access, name="settings-members-access"),
    path("settings/access/company/", add_company_access_grant, name="add-company-access"),
    path("settings/access/department/", add_department_access_grant, name="add-department-access"),
    path("settings/access/user/", add_user_access_grant, name="add-user-access"),
    path("settings/access/<int:grant_id>/remove/", remove_access_grant, name="remove-access"),
]
