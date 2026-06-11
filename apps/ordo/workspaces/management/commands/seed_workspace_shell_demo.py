from django.core.management.base import BaseCommand
from django.db import transaction

from apps.ordo.workspaces.models import (
    Project,
    ProjectMembership,
    Team,
    Workspace,
    WorkspaceMembership,
)


DEMO_STRUCTURE = (
    {
        "workspace": {
            "name": "Altyn Group",
            "slug": "altyn-group",
            "description": "Workspace shell demo for the Altyn Group context.",
        },
        "projects": (
            ("Website Redesign", "website-redesign"),
            ("Product Launch", "product-launch"),
            ("Q3 Marketing Campaign", "q3-marketing-campaign"),
        ),
        "teams": (
            ("Product Team", "product-team"),
            ("Design Team", "design-team"),
            ("Engineering Team", "engineering-team"),
        ),
    },
    {
        "workspace": {
            "name": "Qazaqstan Retail",
            "slug": "qazaqstan-retail",
            "description": "Workspace shell demo for the Qazaqstan Retail context.",
        },
        "projects": (
            ("IT Department", "it-department"),
            ("Sales Department", "sales-department"),
            ("Finance Department", "finance-department"),
        ),
        "teams": (
            ("IT Team", "it-team"),
            ("Sales Team", "sales-team"),
            ("Finance Team", "finance-team"),
        ),
    },
)


class Command(BaseCommand):
    help = "Create demo workspaces, projects, teams, and memberships for the workspace shell."

    @transaction.atomic
    def handle(self, *args, **options):
        for group in DEMO_STRUCTURE:
            workspace_data = group["workspace"]
            workspace, _ = Workspace.objects.update_or_create(
                slug=workspace_data["slug"],
                defaults={
                    "name": workspace_data["name"],
                    "description": workspace_data["description"],
                    "is_active": True,
                },
            )

            projects = []
            for name, slug in group["projects"]:
                project, _ = Project.objects.update_or_create(
                    workspace=workspace,
                    slug=slug,
                    defaults={
                        "name": name,
                        "description": f"{name} project inside {workspace.name}.",
                        "is_active": True,
                    },
                )
                projects.append(project)

            teams = []
            for name, slug in group["teams"]:
                team, _ = Team.objects.update_or_create(
                    slug=slug,
                    defaults={
                        "name": name,
                        "description": f"{name} workspace access group.",
                        "is_active": True,
                    },
                )
                WorkspaceMembership.objects.update_or_create(
                    workspace=workspace,
                    team=team,
                    defaults={"role": WorkspaceMembership.Role.MEMBER},
                )
                teams.append(team)

            for index, team in enumerate(teams):
                project = projects[index % len(projects)]
                ProjectMembership.objects.update_or_create(
                    project=project,
                    team=team,
                    defaults={"role": ProjectMembership.Role.MEMBER},
                )

        self.stdout.write(self.style.SUCCESS("Workspace shell demo data is ready."))
