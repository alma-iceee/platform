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
    def _force_login_workspace_owner(self, workspace):
        user = get_user_model().objects.create_user(email="owner@example.com", password="secret")
        team = Team.objects.create(name="Owners", slug=f"owners-{workspace.pk}")
        team.users.add(user)
        WorkspaceMembership.objects.create(
            workspace=workspace,
            team=team,
            role=WorkspaceMembership.Role.OWNER,
        )
        self.client.force_login(user)
        return user

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
        self.assertContains(response, "New Team")
        self.assertContains(response, "Members can be added after the team is created.")
        self.assertNotContains(response, "Team Members")
        self.assertContains(response, workspace.name)

    def test_teams_route_lists_workspace_teams(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        WorkspaceTeam.objects.create(workspace=workspace, name="Product Team", slug="product-team")

        response = self.client.get(f"{reverse('workspaces:teams')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Product Team")
        self.assertContains(response, "New Team")

    def test_team_detail_route_opens_edit_mode(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        team = WorkspaceTeam.objects.create(workspace=workspace, name="Product Team", slug="product-team")

        response = self.client.get(
            f"{reverse('workspaces:team-detail', args=[team.pk])}?workspace={workspace.slug}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit team")
        self.assertContains(response, "Product Team")

    def test_teams_create_workspace_team(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:teams')}?workspace={workspace.slug}",
            {
                "action": "save_team",
                "name": "Product Team",
                "description": "Product access group",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        team = WorkspaceTeam.objects.get(workspace=workspace, slug="product-team")
        self.assertEqual(team.description, "Product access group")
        self.assertTrue(team.is_active)
        self.assertEqual(
            response["Location"],
            f"{reverse('workspaces:team-detail', args=[team.pk])}?workspace={workspace.slug}",
        )

    def test_teams_create_workspace_team_with_russian_names(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        self._force_login_workspace_owner(workspace)

        for team_name in ("Отдел продаж", "Команда разработки", "Бухгалтерия"):
            response = self.client.post(
                f"{reverse('workspaces:teams')}?workspace={workspace.slug}",
                {
                    "action": "save_team",
                    "name": team_name,
                    "description": "",
                },
            )

            self.assertEqual(response.status_code, 302)
            self.assertTrue(WorkspaceTeam.objects.filter(workspace=workspace, name=team_name).exists())

    def test_teams_create_workspace_team_strips_name_and_rejects_empty(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:teams')}?workspace={workspace.slug}",
            {
                "action": "save_team",
                "name": "  Бухгалтерия  ",
                "description": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(WorkspaceTeam.objects.filter(workspace=workspace, name="Бухгалтерия").exists())

        empty_response = self.client.post(
            f"{reverse('workspaces:teams')}?workspace={workspace.slug}",
            {
                "action": "save_team",
                "name": "   ",
                "description": "",
            },
        )

        self.assertEqual(empty_response.status_code, 200)
        self.assertContains(empty_response, "Team name cannot be empty.")

    def test_team_detail_route_updates_workspace_team(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        team = WorkspaceTeam.objects.create(workspace=workspace, name="Product Team", slug="product-team")
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:team-detail', args=[team.pk])}?workspace={workspace.slug}",
            {
                "action": "save_team",
                "name": "Design Team",
                "description": "Design access group",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        team.refresh_from_db()
        self.assertEqual(team.name, "Design Team")
        self.assertEqual(team.slug, "design-team")

    def test_teams_adds_company_member_grant(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Company A")
        grant = WorkspaceAccessGrant.objects.create(workspace=workspace, company=company)
        team = WorkspaceTeam.objects.create(workspace=workspace, name="Product Team", slug="product-team")
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:team-detail', args=[team.pk])}?workspace={workspace.slug}",
            {
                "action": "add_company_member",
                "team_company-company": company.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(WorkspaceTeamMember.objects.filter(team=team, access_grant=grant).exists())

    def test_teams_adds_department_member_grant(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Company A")
        department = Department.objects.create(company=company, name="Finance")
        grant = WorkspaceAccessGrant.objects.create(workspace=workspace, department=department)
        team = WorkspaceTeam.objects.create(workspace=workspace, name="Product Team", slug="product-team")
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:team-detail', args=[team.pk])}?workspace={workspace.slug}",
            {
                "action": "add_department_member",
                "team_department-company": company.pk,
                "team_department-department": department.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(WorkspaceTeamMember.objects.filter(team=team, access_grant=grant).exists())

    def test_teams_rejects_department_member_for_different_company(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Company A")
        other_company = Company.objects.create(name="Company B")
        department = Department.objects.create(company=other_company, name="Finance")
        WorkspaceAccessGrant.objects.create(workspace=workspace, department=department)
        team = WorkspaceTeam.objects.create(workspace=workspace, name="Product Team", slug="product-team")
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:team-detail', args=[team.pk])}?workspace={workspace.slug}",
            {
                "action": "add_department_member",
                "team_department-company": company.pk,
                "team_department-department": department.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Department must belong to the selected company.")
        self.assertEqual(WorkspaceTeamMember.objects.filter(team=team).count(), 0)

    def test_teams_adds_direct_user_member_grant_by_email(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        user = get_user_model().objects.create_user(email="member@example.com", password="secret")
        grant = WorkspaceAccessGrant.objects.create(workspace=workspace, user=user)
        team = WorkspaceTeam.objects.create(workspace=workspace, name="Product Team", slug="product-team")
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:team-detail', args=[team.pk])}?workspace={workspace.slug}",
            {
                "action": "add_user_member",
                "team_user-email": "member@example.com",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(WorkspaceTeamMember.objects.filter(team=team, access_grant=grant).exists())

    def test_teams_rejects_unknown_user_email(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        team = WorkspaceTeam.objects.create(workspace=workspace, name="Product Team", slug="product-team")
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:team-detail', args=[team.pk])}?workspace={workspace.slug}",
            {
                "action": "add_user_member",
                "team_user-email": "missing@example.com",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No user found with this email.")
        self.assertEqual(WorkspaceTeamMember.objects.filter(team=team).count(), 0)

    def test_teams_rejects_user_without_direct_workspace_access(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        user = get_user_model().objects.create_user(email="member@example.com", password="secret")
        team = WorkspaceTeam.objects.create(workspace=workspace, name="Product Team", slug="product-team")
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:team-detail', args=[team.pk])}?workspace={workspace.slug}",
            {
                "action": "add_user_member",
                "team_user-email": user.email,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User must already have direct workspace access.")
        self.assertEqual(WorkspaceTeamMember.objects.filter(team=team).count(), 0)

    def test_teams_duplicate_member_grant_does_not_crash(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Company A")
        grant = WorkspaceAccessGrant.objects.create(workspace=workspace, company=company)
        team = WorkspaceTeam.objects.create(workspace=workspace, name="Product Team", slug="product-team")
        WorkspaceTeamMember.objects.create(team=team, access_grant=grant)
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:team-detail', args=[team.pk])}?workspace={workspace.slug}",
            {
                "action": "add_company_member",
                "team_company-company": company.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(WorkspaceTeamMember.objects.filter(team=team, access_grant=grant).count(), 1)

    def test_teams_removes_member_grant(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Company A")
        grant = WorkspaceAccessGrant.objects.create(workspace=workspace, company=company)
        team = WorkspaceTeam.objects.create(workspace=workspace, name="Product Team", slug="product-team")
        membership = WorkspaceTeamMember.objects.create(team=team, access_grant=grant)
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:team-detail', args=[team.pk])}?workspace={workspace.slug}",
            {
                "action": "remove_member",
                "membership_id": membership.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(WorkspaceTeamMember.objects.filter(pk=membership.pk).exists())

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
        self.assertContains(response, "General")
        self.assertContains(response, workspace.name)

    def test_settings_members_access_route_renders(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")

        response = self.client.get(
            f"{reverse('workspaces:settings-members-access')}?workspace={workspace.slug}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Members &amp; Access")
        self.assertContains(response, workspace.name)

    def test_settings_members_access_route_shows_company_access_grant(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Company A")
        WorkspaceAccessGrant.objects.create(workspace=workspace, company=company)

        response = self.client.get(
            f"{reverse('workspaces:settings-members-access')}?workspace={workspace.slug}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Members &amp; Access")
        self.assertContains(response, "Company A")
        self.assertContains(response, "Company")
        self.assertContains(response, "Whole company")

    def test_settings_members_access_route_shows_department_access_grant(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Company A")
        department = Department.objects.create(company=company, name="Finance Department")
        WorkspaceAccessGrant.objects.create(workspace=workspace, department=department)

        response = self.client.get(
            f"{reverse('workspaces:settings-members-access')}?workspace={workspace.slug}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Finance Department")
        self.assertContains(response, "Department")

    def test_settings_members_access_route_shows_user_access_grant(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        user = get_user_model().objects.create_user(
            email="john@example.com",
            password="secret",
            full_name="John Smith",
        )
        WorkspaceAccessGrant.objects.create(workspace=workspace, user=user)

        response = self.client.get(
            f"{reverse('workspaces:settings-members-access')}?workspace={workspace.slug}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "John Smith")
        self.assertContains(response, "User")
        self.assertContains(response, "Direct user")

    def test_settings_members_access_route_shows_access_grants_empty_state(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")

        response = self.client.get(
            f"{reverse('workspaces:settings-members-access')}?workspace={workspace.slug}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No workspace access has been granted yet.")

    def test_settings_adds_company_access_grant(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Company A")
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:add-company-access')}?workspace={workspace.slug}",
            {"company": company.pk},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            WorkspaceAccessGrant.objects.filter(workspace=workspace, company=company).exists()
        )

    def test_settings_adds_department_access_grant(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Company A")
        department = Department.objects.create(company=company, name="Finance")
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:add-department-access')}?workspace={workspace.slug}",
            {"company": company.pk, "department": department.pk},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            WorkspaceAccessGrant.objects.filter(workspace=workspace, department=department).exists()
        )

    def test_settings_rejects_department_access_grant_for_different_company(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Company A")
        other_company = Company.objects.create(name="Company B")
        department = Department.objects.create(company=other_company, name="Finance")
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:add-department-access')}?workspace={workspace.slug}",
            {"company": company.pk, "department": department.pk},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Department must belong to the selected company.")
        self.assertFalse(
            WorkspaceAccessGrant.objects.filter(workspace=workspace, department=department).exists()
        )

    def test_settings_adds_user_access_grant_by_existing_email(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        user = get_user_model().objects.create_user(email="member@example.com", password="secret")
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:add-user-access')}?workspace={workspace.slug}",
            {"email": "member@example.com"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            WorkspaceAccessGrant.objects.filter(workspace=workspace, user=user).exists()
        )

    def test_settings_unknown_user_email_shows_error_and_does_not_create_grant(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:add-user-access')}?workspace={workspace.slug}",
            {"email": "missing@example.com"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No user found with this email.")
        self.assertEqual(WorkspaceAccessGrant.objects.filter(workspace=workspace).count(), 0)

    def test_settings_removes_access_grant(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Company A")
        grant = WorkspaceAccessGrant.objects.create(workspace=workspace, company=company)
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:remove-access', args=[grant.pk])}?workspace={workspace.slug}"
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(WorkspaceAccessGrant.objects.filter(pk=grant.pk).exists())

    def test_settings_duplicate_access_grant_does_not_crash(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Company A")
        WorkspaceAccessGrant.objects.create(workspace=workspace, company=company)
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:add-company-access')}?workspace={workspace.slug}",
            {"company": company.pk},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            WorkspaceAccessGrant.objects.filter(workspace=workspace, company=company).count(),
            1,
        )

    def test_unauthorized_user_cannot_add_or_remove_access_grants(self):
        member_user = get_user_model().objects.create_user(email="member@example.com", password="secret")
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Company A")
        team = Team.objects.create(name="Members", slug="members")
        team.users.add(member_user)
        WorkspaceMembership.objects.create(
            workspace=workspace,
            team=team,
            role=WorkspaceMembership.Role.MEMBER,
        )
        grant = WorkspaceAccessGrant.objects.create(workspace=workspace, company=company)
        self.client.force_login(member_user)

        add_response = self.client.post(
            f"{reverse('workspaces:add-user-access')}?workspace={workspace.slug}",
            {"email": member_user.email},
        )
        remove_response = self.client.post(
            f"{reverse('workspaces:remove-access', args=[grant.pk])}?workspace={workspace.slug}"
        )

        self.assertEqual(add_response.status_code, 403)
        self.assertEqual(remove_response.status_code, 403)
        self.assertFalse(
            WorkspaceAccessGrant.objects.filter(workspace=workspace, user=member_user).exists()
        )
        self.assertTrue(WorkspaceAccessGrant.objects.filter(pk=grant.pk).exists())

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
