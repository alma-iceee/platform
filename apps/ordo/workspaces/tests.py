from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Project, Team, Workspace, WorkspaceMembership


class WorkspaceShellViewTests(TestCase):
    def test_shell_renders_with_empty_state(self):
        response = self.client.get(reverse("workspaces:shell"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
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
        self.assertContains(response, "Dashboard")
        self.assertContains(response, project.name)
        self.assertContains(response, team.name)

    def test_dashboard_route_renders(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")

        response = self.client.get(f"{reverse('workspaces:dashboard')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        self.assertContains(response, workspace.name)

    def test_tasks_route_renders(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")

        response = self.client.get(f"{reverse('workspaces:tasks')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tasks")
        self.assertContains(response, workspace.name)

    def test_projects_route_renders(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")

        response = self.client.get(f"{reverse('workspaces:projects')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Projects")
        self.assertContains(response, workspace.name)

    def test_teams_route_renders(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")

        response = self.client.get(f"{reverse('workspaces:teams')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Teams")
        self.assertContains(response, workspace.name)

    def test_chats_route_renders(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")

        response = self.client.get(f"{reverse('workspaces:chats')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chats")
        self.assertContains(response, workspace.name)

    def test_storage_route_renders(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")

        response = self.client.get(f"{reverse('workspaces:storage')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Storage")
        self.assertContains(response, workspace.name)

    def test_settings_route_renders(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")

        response = self.client.get(f"{reverse('workspaces:settings')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Settings")
        self.assertContains(response, workspace.name)

    def test_settings_route_shows_memberships(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        team = Team.objects.create(name="Product Team", slug="product-team")
        WorkspaceMembership.objects.create(
            workspace=workspace,
            team=team,
            role=WorkspaceMembership.Role.ADMIN,
        )

        response = self.client.get(f"{reverse('workspaces:settings')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Members &amp; Access")
        self.assertContains(response, "Product Team")
        self.assertContains(response, "Admin")

    def test_workspace_name_can_be_updated_by_allowed_user(self):
        user = get_user_model().objects.create_user(email="owner@example.com", password="secret")
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        team = Team.objects.create(name="Owners", slug="owners")
        team.users.add(user)
        WorkspaceMembership.objects.create(
            workspace=workspace,
            team=team,
            role=WorkspaceMembership.Role.OWNER,
        )
        self.client.force_login(user)

        response = self.client.post(
            f"{reverse('workspaces:settings')}?workspace={workspace.slug}",
            {"name": "Altyn Group Renamed"},
        )

        self.assertEqual(response.status_code, 302)
        workspace.refresh_from_db()
        self.assertEqual(workspace.name, "Altyn Group Renamed")

    def test_unauthorized_user_cannot_update_workspace_name(self):
        owner_user = get_user_model().objects.create_user(email="owner@example.com", password="secret")
        member_user = get_user_model().objects.create_user(email="member@example.com", password="secret")
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        owner_team = Team.objects.create(name="Owners", slug="owners")
        member_team = Team.objects.create(name="Members", slug="members")
        owner_team.users.add(owner_user)
        member_team.users.add(member_user)
        WorkspaceMembership.objects.create(
            workspace=workspace,
            team=owner_team,
            role=WorkspaceMembership.Role.OWNER,
        )
        WorkspaceMembership.objects.create(
            workspace=workspace,
            team=member_team,
            role=WorkspaceMembership.Role.MEMBER,
        )
        self.client.force_login(member_user)

        response = self.client.post(
            f"{reverse('workspaces:settings')}?workspace={workspace.slug}",
            {"name": "Should Not Change"},
        )

        self.assertEqual(response.status_code, 403)
        workspace.refresh_from_db()
        self.assertEqual(workspace.name, "Altyn Group")
