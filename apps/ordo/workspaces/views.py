from django.shortcuts import render

from .models import Project, Team, Workspace


PROJECT_COLOR_CLASSES = ("blue", "gold", "cyan", "orange", "purple")
TEAM_COLOR_CLASSES = ("blue", "purple", "cyan", "orange", "gold")


def workspace_shell(request):
    workspaces = list(Workspace.objects.filter(is_active=True).order_by("name"))

    requested_workspace_slug = request.GET.get("workspace")
    current_workspace = next(
        (workspace for workspace in workspaces if workspace.slug == requested_workspace_slug),
        None,
    )
    if current_workspace is None and workspaces:
        current_workspace = workspaces[0]

    projects = []
    teams = []
    selected_project = None

    if current_workspace is not None:
        projects = list(
            current_workspace.projects.filter(is_active=True).order_by("name")
        )
        teams = list(
            Team.objects.filter(
                is_active=True,
                workspace_memberships__workspace=current_workspace,
            )
            .distinct()
            .order_by("name")
        )

        requested_project_slug = request.GET.get("project")
        selected_project = next(
            (project for project in projects if project.slug == requested_project_slug),
            None,
        )
        if selected_project is None and projects:
            selected_project = projects[0]

    project_items = [
        {
            "instance": project,
            "color_class": PROJECT_COLOR_CLASSES[index % len(PROJECT_COLOR_CLASSES)],
            "is_active": selected_project is not None and selected_project.pk == project.pk,
        }
        for index, project in enumerate(projects)
    ]
    team_items = [
        {
            "instance": team,
            "color_class": TEAM_COLOR_CLASSES[index % len(TEAM_COLOR_CLASSES)],
        }
        for index, team in enumerate(teams)
    ]

    context = {
        "workspaces": workspaces,
        "current_workspace": current_workspace,
        "project_items": project_items,
        "team_items": team_items,
        "selected_project": selected_project,
        "selected_workspace_slug": current_workspace.slug if current_workspace else "",
    }
    return render(request, "workspaces/shell.html", context)
