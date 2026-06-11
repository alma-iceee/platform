from django.test import TestCase
from django.urls import reverse

from .models import Project, Team, Workspace, WorkspaceMembership


class WorkspaceShellViewTests(TestCase):
    def test_shell_renders_with_empty_state(self):
        response = self.client.get(reverse("workspaces:shell"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No workspace data yet")

    def test_shell_lists_workspace_projects_and_teams(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        project = Project.objects.create(
            workspace=workspace,
            name="Website Redesign",
            slug="website-redesign",
        )
        team = Team.objects.create(name="Design Team", slug="design-team")
        WorkspaceMembership.objects.create(workspace=workspace, team=team)

        response = self.client.get(reverse("workspaces:shell"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, workspace.name)
        self.assertContains(response, project.name)
        self.assertContains(response, team.name)
