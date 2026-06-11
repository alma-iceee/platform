from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.ordo.organizations.models import Company, Department

from .models import (
    Project,
    Team,
    Workspace,
    WorkspaceAccessGrant,
    WorkspaceMembership,
    WorkspaceTeam,
    WorkspaceTeamMember,
)


class WorkspaceAccessModelTests(TestCase):
    def test_workspace_access_grant_accepts_direct_user(self):
        user = get_user_model().objects.create_user(email="member@example.com", password="secret")
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")

        grant = WorkspaceAccessGrant.objects.create(workspace=workspace, user=user)

        self.assertEqual(grant.subject, user)
        self.assertEqual(str(grant), f"{user} -> {workspace}")

    def test_workspace_access_grant_requires_exactly_one_subject(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Altyn")
        user = get_user_model().objects.create_user(email="member@example.com", password="secret")

        with self.assertRaises(ValidationError):
            WorkspaceAccessGrant(workspace=workspace).full_clean()

        with self.assertRaises(ValidationError):
            WorkspaceAccessGrant(workspace=workspace, company=company, user=user).full_clean()

    def test_workspace_access_grant_is_unique_per_workspace_and_subject(self):
        user = get_user_model().objects.create_user(email="member@example.com", password="secret")
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        other_workspace = Workspace.objects.create(name="Qazaqstan Retail", slug="qazaqstan-retail")
        WorkspaceAccessGrant.objects.create(workspace=workspace, user=user)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WorkspaceAccessGrant.objects.create(workspace=workspace, user=user)

        WorkspaceAccessGrant.objects.create(workspace=other_workspace, user=user)

    def test_workspace_access_grant_is_unique_for_company_and_department(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Altyn")
        department = Department.objects.create(company=company, name="Design")
        WorkspaceAccessGrant.objects.create(workspace=workspace, company=company)
        WorkspaceAccessGrant.objects.create(workspace=workspace, department=department)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WorkspaceAccessGrant.objects.create(workspace=workspace, company=company)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WorkspaceAccessGrant.objects.create(workspace=workspace, department=department)

    def test_workspace_team_slug_is_unique_per_workspace(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        other_workspace = Workspace.objects.create(name="Qazaqstan Retail", slug="qazaqstan-retail")
        WorkspaceTeam.objects.create(workspace=workspace, name="Product Team", slug="product")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WorkspaceTeam.objects.create(workspace=workspace, name="Product Team Copy", slug="product")

        WorkspaceTeam.objects.create(workspace=other_workspace, name="Product Team", slug="product")

    def test_workspace_team_member_is_unique_per_team_and_access_grant(self):
        user = get_user_model().objects.create_user(email="member@example.com", password="secret")
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        grant = WorkspaceAccessGrant.objects.create(workspace=workspace, user=user)
        team = WorkspaceTeam.objects.create(workspace=workspace, name="Product Team", slug="product")
        WorkspaceTeamMember.objects.create(team=team, access_grant=grant)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WorkspaceTeamMember.objects.create(team=team, access_grant=grant)

    def test_workspace_team_member_accepts_grant_from_same_workspace(self):
        user = get_user_model().objects.create_user(email="member@example.com", password="secret")
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        grant = WorkspaceAccessGrant.objects.create(workspace=workspace, user=user)
        team = WorkspaceTeam.objects.create(workspace=workspace, name="Product Team", slug="product")
        member = WorkspaceTeamMember(team=team, access_grant=grant)

        member.full_clean()
        member.save()

        self.assertEqual(member.team, team)
        self.assertEqual(member.access_grant, grant)

    def test_workspace_team_member_rejects_grant_from_different_workspace(self):
        user = get_user_model().objects.create_user(email="member@example.com", password="secret")
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        other_workspace = Workspace.objects.create(name="Qazaqstan Retail", slug="qazaqstan-retail")
        grant = WorkspaceAccessGrant.objects.create(workspace=other_workspace, user=user)
        team = WorkspaceTeam.objects.create(workspace=workspace, name="Product Team", slug="product")
        member = WorkspaceTeamMember(team=team, access_grant=grant)

        with self.assertRaises(ValidationError):
            member.full_clean()


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
