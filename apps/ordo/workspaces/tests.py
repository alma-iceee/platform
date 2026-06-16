from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.ordo.accounts.models import CompanyMembership, DepartmentMembership
from apps.ordo.organizations.models import Company, Department

from .forms import WorkspaceTeamDepartmentMemberForm
from .models import (
    Project,
    Workspace,
    WorkspaceAccessGrant,
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


class SeedWorkspaceDemoCommandTests(TestCase):
    def call_seed(self):
        stdout = StringIO()
        call_command("seed_workspace_demo", stdout=stdout)
        return stdout.getvalue()

    def test_command_creates_company_workspaces_with_company_member_access(self):
        company_a = Company.objects.create(name="Company A")
        company_b = Company.objects.create(name="Company B")

        output = self.call_seed()

        self.assertIn("Workspace demo data is ready.", output)
        self.assertEqual(Workspace.objects.filter(company__isnull=False).count(), 2)
        for company in (company_a, company_b):
            workspace = Workspace.objects.get(company=company)
            self.assertEqual(workspace.name, company.name)
            self.assertTrue(workspace.is_active)
            self.assertTrue(
                WorkspaceAccessGrant.objects.filter(
                    workspace=workspace,
                    company=company,
                    role=WorkspaceAccessGrant.Role.MEMBER,
                ).exists()
            )

    def test_command_creates_cross_company_workspaces_with_projects_and_teams(self):
        Company.objects.create(name="Company A")
        Company.objects.create(name="Company B")
        Company.objects.create(name="Company C")

        self.call_seed()

        cross_workspaces = Workspace.objects.filter(company__isnull=True)
        self.assertEqual(cross_workspaces.count(), 3)
        self.assertEqual(Project.objects.filter(workspace__company__isnull=True).count(), 15)
        self.assertEqual(WorkspaceTeam.objects.filter(workspace__company__isnull=True).count(), 15)

        for workspace in cross_workspaces:
            self.assertEqual(workspace.projects.count(), 5)
            self.assertEqual(workspace.workspace_teams.count(), 5)
            self.assertTrue(workspace.access_grants.filter(company__isnull=False).exists())
            self.assertFalse(workspace.access_grants.filter(department__isnull=False).exists())

        project = Project.objects.get(slug="pump-equipment-tender")
        self.assertEqual(project.workspace.slug, "equipment-procurement")
        self.assertIsNotNone(project.team)
        self.assertTrue(project.team.members.exists())

    def test_command_creates_varied_team_subject_types(self):
        companies = [
            Company.objects.create(name=f"Company {index}")
            for index in range(4)
        ]
        for company in companies:
            for index in range(5):
                Department.objects.create(company=company, name=f"Department {index}")
        for index in range(15):
            get_user_model().objects.create_user(
                email=f"user{index}@example.com",
                password="secret",
            )

        self.call_seed()

        company_team = WorkspaceTeam.objects.get(slug="geology-licenses")
        company_grants = company_team.members.filter(access_grant__company__isnull=False)
        self.assertEqual(company_grants.count(), 2)
        self.assertFalse(company_team.members.filter(access_grant__department__isnull=False).exists())
        self.assertFalse(company_team.members.filter(access_grant__user__isnull=False).exists())

        department_user_team = WorkspaceTeam.objects.get(slug="budget-taxes")
        self.assertEqual(
            department_user_team.members.filter(access_grant__department__isnull=False).count(),
            2,
        )
        self.assertEqual(
            department_user_team.members.filter(access_grant__user__isnull=False).count(),
            1,
        )
        self.assertFalse(
            department_user_team.members.filter(access_grant__company__isnull=False).exists()
        )

        mixed_team = WorkspaceTeam.objects.get(slug="tender-committee")
        self.assertEqual(mixed_team.members.filter(access_grant__company__isnull=False).count(), 1)
        self.assertEqual(mixed_team.members.filter(access_grant__department__isnull=False).count(), 2)
        self.assertEqual(mixed_team.members.filter(access_grant__user__isnull=False).count(), 1)

    def test_command_is_idempotent(self):
        Company.objects.create(name="Company A")
        Company.objects.create(name="Company B")

        self.call_seed()
        first_counts = {
            "workspaces": Workspace.objects.count(),
            "access_grants": WorkspaceAccessGrant.objects.count(),
            "workspace_teams": WorkspaceTeam.objects.count(),
            "team_members": WorkspaceTeamMember.objects.count(),
            "projects": Project.objects.count(),
        }

        self.call_seed()

        self.assertEqual(Workspace.objects.count(), first_counts["workspaces"])
        self.assertEqual(WorkspaceAccessGrant.objects.count(), first_counts["access_grants"])
        self.assertEqual(WorkspaceTeam.objects.count(), first_counts["workspace_teams"])
        self.assertEqual(WorkspaceTeamMember.objects.count(), first_counts["team_members"])
        self.assertEqual(Project.objects.count(), first_counts["projects"])

    def test_command_promotes_viewer_grant_but_does_not_demote_admin_grant(self):
        viewer_company = Company.objects.create(name="Viewer Company")
        admin_company = Company.objects.create(name="Admin Company")
        viewer_workspace = Workspace.objects.create(
            company=viewer_company,
            name=viewer_company.name,
            slug="viewer-company",
        )
        admin_workspace = Workspace.objects.create(
            company=admin_company,
            name=admin_company.name,
            slug="admin-company",
        )
        viewer_grant = WorkspaceAccessGrant.objects.create(
            workspace=viewer_workspace,
            company=viewer_company,
            role=WorkspaceAccessGrant.Role.VIEWER,
        )
        admin_grant = WorkspaceAccessGrant.objects.create(
            workspace=admin_workspace,
            company=admin_company,
            role=WorkspaceAccessGrant.Role.ADMIN,
        )

        self.call_seed()

        viewer_grant.refresh_from_db()
        admin_grant.refresh_from_db()
        self.assertEqual(viewer_grant.role, WorkspaceAccessGrant.Role.MEMBER)
        self.assertEqual(admin_grant.role, WorkspaceAccessGrant.Role.ADMIN)


class WorkspaceShellViewTests(TestCase):
    def setUp(self):
        self.viewer = get_user_model().objects.create_superuser(
            email="workspace-test-admin@example.com",
            password="secret",
        )
        self.client.force_login(self.viewer)

    def _force_login_workspace_owner(self, workspace):
        user = get_user_model().objects.create_user(email="owner@example.com", password="secret")
        WorkspaceAccessGrant.objects.create(
            workspace=workspace,
            user=user,
            role=WorkspaceAccessGrant.Role.OWNER,
        )
        self.client.force_login(user)
        return user

    def test_shell_requires_authentication(self):
        self.client.logout()

        response = self.client.get(reverse("workspaces:shell"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        self.assertIn(reverse("workspaces:shell"), response["Location"])

    def test_workspace_create_route_requires_authentication(self):
        self.client.logout()

        response = self.client.get(reverse("workspaces:workspace_create"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        self.assertIn(reverse("workspaces:workspace_create"), response["Location"])

    def test_workspace_create_route_renders_without_selected_workspace(self):
        user = get_user_model().objects.create_user(email="creator@example.com", password="secret")
        self.client.force_login(user)

        response = self.client.get(reverse("workspaces:workspace_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New workspace")
        self.assertContains(response, "Create workspace")

    def test_authenticated_user_can_create_workspace(self):
        user = get_user_model().objects.create_user(email="creator@example.com", password="secret")
        self.client.force_login(user)

        response = self.client.post(
            reverse("workspaces:workspace_create"),
            {
                "name": "Demo Workspace",
                "description": "Created from the workspace selector.",
            },
        )

        workspace = Workspace.objects.get(slug="demo-workspace")
        self.assertRedirects(
            response,
            f"{reverse('workspaces:dashboard')}?workspace={workspace.slug}",
        )
        self.assertEqual(workspace.name, "Demo Workspace")
        self.assertEqual(workspace.description, "Created from the workspace selector.")
        self.assertTrue(
            WorkspaceAccessGrant.objects.filter(
                workspace=workspace,
                user=user,
                role=WorkspaceAccessGrant.Role.OWNER,
            ).exists()
        )

    def test_created_workspace_is_visible_to_creator(self):
        user = get_user_model().objects.create_user(email="creator@example.com", password="secret")
        self.client.force_login(user)
        self.client.post(reverse("workspaces:workspace_create"), {"name": "Visible Workspace"})
        workspace = Workspace.objects.get(slug="visible-workspace")

        response = self.client.get(f"{reverse('workspaces:dashboard')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, workspace.name)
        self.assertContains(response, reverse("workspaces:workspace_create"))

    def test_topbar_renders_logout_form(self):
        workspace = Workspace.objects.create(name="Visible Workspace", slug="visible-workspace")
        self._force_login_workspace_owner(workspace)

        response = self.client.get(f"{reverse('workspaces:dashboard')}?workspace={workspace.slug}")

        self.assertContains(response, f'action="{reverse("accounts:logout")}"')
        self.assertContains(response, 'type="submit" role="menuitem">Logout</button>')

    def test_shell_lists_workspace_projects_and_teams(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        project = Project.objects.create(
            workspace=workspace,
            name="Website Redesign",
            slug="website-redesign",
        )
        team = WorkspaceTeam.objects.create(
            workspace=workspace,
            name="Design Team",
            slug="design-team",
        )
        project.team = team
        project.save(update_fields=["team"])

        response = self.client.get(reverse("workspaces:shell"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        self.assertContains(response, project.name)
        self.assertContains(response, team.name)
        self.assertContains(response, reverse("workspaces:teams"))
        self.assertContains(response, reverse("workspaces:projects"))
        self.assertContains(response, reverse("workspaces:project-create"))
        self.assertContains(response, reverse("workspaces:project-detail", args=[project.pk]))
        self.assertNotContains(response, "project=")

    def test_dashboard_shows_workspace_overview_stats(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        Project.objects.create(
            workspace=workspace,
            name="Website Redesign",
            slug="website-redesign",
        )
        WorkspaceTeam.objects.create(
            workspace=workspace,
            name="Design Team",
            slug="design-team",
        )
        WorkspaceAccessGrant.objects.create(
            workspace=workspace,
            user=get_user_model().objects.create_user(email="member@example.com", password="secret"),
        )

        response = self.client.get(f"{reverse('workspaces:dashboard')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Active workspace projects")
        self.assertNotContains(response, "Accessible departments")
        self.assertContains(response, "Workspace teams")
        self.assertContains(response, "Workspace access entries")
        self.assertContains(response, "Recent activity")

    def test_dashboard_shows_workspace_departments_separate_from_projects(self):
        company = Company.objects.create(name="Altyn Operating")
        workspace = Workspace.objects.create(
            name="Altyn Group",
            slug="altyn-group",
            company=company,
        )
        department = Department.objects.create(company=company, name="Finance")
        WorkspaceAccessGrant.objects.create(workspace=workspace, company=company)
        Project.objects.create(
            workspace=workspace,
            name="Project X",
            slug="project-x",
        )

        response = self.client.get(f"{reverse('workspaces:dashboard')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_stats"]["departments"], 1)
        self.assertEqual(response.context["dashboard_stats"]["projects"], 1)
        self.assertContains(response, "Departments")
        self.assertContains(response, department.name)
        self.assertNotContains(response, company.name)
        self.assertContains(response, "Project X")

    def test_dashboard_limits_authenticated_user_to_accessible_departments(self):
        user = get_user_model().objects.create_user(email="member@example.com", password="secret")
        company = Company.objects.create(name="Company A")
        workspace = Workspace.objects.create(name="Company A", slug="company-a", company=company)
        department = Department.objects.create(company=company, name="Department B")
        other_department = Department.objects.create(company=company, name="Department C")
        DepartmentMembership.objects.create(
            user=user,
            department=department,
            role=DepartmentMembership.Role.MEMBER,
        )
        CompanyMembership.objects.create(
            user=user,
            company=company,
            role=CompanyMembership.Role.MEMBER,
        )
        WorkspaceAccessGrant.objects.create(workspace=workspace, company=company)
        self.client.force_login(user)

        response = self.client.get(f"{reverse('workspaces:dashboard')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_stats"]["departments"], 1)
        self.assertContains(response, "Department B")
        self.assertNotContains(response, "Department C")

    def test_company_membership_gives_access_to_company_workspace(self):
        user = get_user_model().objects.create_user(email="employee@example.com", password="secret")
        company = Company.objects.create(name="Company A")
        other_company = Company.objects.create(name="Company B")
        workspace = Workspace.objects.create(name="Company A", slug="company-a", company=company)
        other_workspace = Workspace.objects.create(
            name="Company B",
            slug="company-b",
            company=other_company,
        )
        CompanyMembership.objects.create(
            user=user,
            company=company,
            role=CompanyMembership.Role.MEMBER,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("workspaces:shell"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_workspace"], workspace)
        self.assertEqual(list(response.context["workspaces"]), [workspace])
        self.assertContains(response, "Company A")
        self.assertNotContains(response, other_workspace.name)

    def test_company_workspace_is_selected_before_cross_company_workspace(self):
        user = get_user_model().objects.create_user(email="employee@example.com", password="secret")
        company = Company.objects.create(name="Company A")
        company_workspace = Workspace.objects.create(
            name="Company A",
            slug="company-a",
            company=company,
        )
        cross_workspace = Workspace.objects.create(
            name="A Cross Company Project",
            slug="a-cross-company-project",
        )
        CompanyMembership.objects.create(
            user=user,
            company=company,
            role=CompanyMembership.Role.MEMBER,
        )
        WorkspaceAccessGrant.objects.create(workspace=cross_workspace, company=company)
        self.client.force_login(user)

        response = self.client.get(reverse("workspaces:shell"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_workspace"], company_workspace)
        self.assertEqual(
            list(response.context["workspaces"]),
            [company_workspace, cross_workspace],
        )

    def test_requested_inaccessible_workspace_is_not_selected(self):
        user = get_user_model().objects.create_user(email="employee@example.com", password="secret")
        company = Company.objects.create(name="Company A")
        other_company = Company.objects.create(name="Company B")
        accessible_workspace = Workspace.objects.create(
            name="Company A",
            slug="company-a",
            company=company,
        )
        inaccessible_workspace = Workspace.objects.create(
            name="Company B",
            slug="company-b",
            company=other_company,
        )
        CompanyMembership.objects.create(
            user=user,
            company=company,
            role=CompanyMembership.Role.MEMBER,
        )
        self.client.force_login(user)

        response = self.client.get(
            f"{reverse('workspaces:dashboard')}?workspace={inaccessible_workspace.slug}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_workspace"], accessible_workspace)
        self.assertEqual(list(response.context["workspaces"]), [accessible_workspace])
        self.assertContains(response, accessible_workspace.name)
        self.assertNotContains(response, inaccessible_workspace.name)

    def test_company_workspace_shows_only_users_department_for_company_employee(self):
        user = get_user_model().objects.create_user(email="employee@example.com", password="secret")
        company = Company.objects.create(name="Company A")
        workspace = Workspace.objects.create(name="Company A", slug="company-a", company=company)
        department = Department.objects.create(company=company, name="Department B")
        other_department = Department.objects.create(company=company, name="Department C")
        CompanyMembership.objects.create(
            user=user,
            company=company,
            role=CompanyMembership.Role.MEMBER,
        )
        DepartmentMembership.objects.create(
            user=user,
            department=department,
            role=DepartmentMembership.Role.MEMBER,
        )
        self.client.force_login(user)

        response = self.client.get(f"{reverse('workspaces:dashboard')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_stats"]["departments"], 1)
        self.assertContains(response, department.name)
        self.assertNotContains(response, other_department.name)

    def test_dashboard_hides_departments_for_cross_company_workspace(self):
        workspace = Workspace.objects.create(name="Cross Company", slug="cross-company")
        company_a = Company.objects.create(name="Company A")
        company_b = Company.objects.create(name="Company B")
        Department.objects.create(company=company_a, name="Finance A")
        Department.objects.create(company=company_b, name="Finance B")
        WorkspaceAccessGrant.objects.create(workspace=workspace, company=company_a)
        WorkspaceAccessGrant.objects.create(workspace=workspace, company=company_b)

        response = self.client.get(f"{reverse('workspaces:dashboard')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_stats"]["departments"], 0)
        self.assertFalse(response.context["shows_department_navigation"])
        self.assertNotContains(response, "Accessible departments")
        self.assertNotContains(response, "Finance A")
        self.assertNotContains(response, "Finance B")

        response = self.client.get(f"{reverse('workspaces:departments')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            f"{reverse('workspaces:dashboard')}?workspace={workspace.slug}",
        )

    def test_departments_route_renders_for_company_workspace(self):
        company = Company.objects.create(name="Company A")
        workspace = Workspace.objects.create(name="Company A", slug="company-a", company=company)
        Department.objects.create(company=company, name="Finance")

        response = self.client.get(f"{reverse('workspaces:departments')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Departments")
        self.assertContains(response, "Finance")

    def test_dashboard_shows_regular_projects_for_user_workspace_team(self):
        user = get_user_model().objects.create_user(email="member@example.com", password="secret")
        workspace = Workspace.objects.create(name="Company A", slug="company-a")
        user_grant = WorkspaceAccessGrant.objects.create(workspace=workspace, user=user)
        team = WorkspaceTeam.objects.create(workspace=workspace, name="Project X Team", slug="project-x-team")
        other_team = WorkspaceTeam.objects.create(workspace=workspace, name="Hidden Team", slug="hidden-team")
        WorkspaceTeamMember.objects.create(team=team, access_grant=user_grant)
        project = Project.objects.create(
            workspace=workspace,
            name="Project X",
            slug="project-x",
            team=team,
        )
        other_project = Project.objects.create(
            workspace=workspace,
            name="Project Z",
            slug="project-z",
            team=other_team,
        )
        self.client.force_login(user)

        response = self.client.get(f"{reverse('workspaces:dashboard')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_stats"]["projects"], 1)
        self.assertContains(response, project.name)
        self.assertNotContains(response, other_project.name)
        self.assertContains(response, team.name)
        self.assertNotContains(response, other_team.name)

        response = self.client.get(
            f"{reverse('workspaces:project-detail', args=[other_project.pk])}?workspace={workspace.slug}"
        )

        self.assertEqual(response.status_code, 404)

        response = self.client.get(
            f"{reverse('workspaces:team-detail', args=[other_team.pk])}?workspace={workspace.slug}"
        )

        self.assertEqual(response.status_code, 404)

    def test_dashboard_shows_company_departments_to_company_director(self):
        user = get_user_model().objects.create_user(email="director@example.com", password="secret")
        company = Company.objects.create(name="Company A")
        workspace = Workspace.objects.create(name="Company A", slug="company-a", company=company)
        other_company = Company.objects.create(name="Company Z")
        finance = Department.objects.create(company=company, name="Finance")
        legal = Department.objects.create(company=company, name="Legal")
        external = Department.objects.create(company=other_company, name="External")
        CompanyMembership.objects.create(
            user=user,
            company=company,
            role=CompanyMembership.Role.DIRECTOR,
        )
        WorkspaceAccessGrant.objects.create(workspace=workspace, company=company)
        self.client.force_login(user)

        response = self.client.get(f"{reverse('workspaces:dashboard')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_stats"]["departments"], 2)
        self.assertContains(response, "Finance")
        self.assertContains(response, "Legal")
        self.assertNotContains(response, "External")

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
        self.assertContains(response, "No projects yet.")
        self.assertContains(response, "Create project")

    def test_project_detail_route_renders_selected_project(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        team = WorkspaceTeam.objects.create(workspace=workspace, name="Design Team", slug="design-team")
        project = Project.objects.create(
            workspace=workspace,
            name="Website Redesign",
            slug="website-redesign",
            description="Corporate website refresh",
            team=team,
        )

        response = self.client.get(
            f"{reverse('workspaces:project-detail', args=[project.pk])}?workspace={workspace.slug}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Website Redesign")
        self.assertContains(response, "Corporate website refresh")
        self.assertContains(response, "Linked team")
        self.assertContains(response, team.name)
        self.assertContains(response, "Edit project")
        self.assertContains(response, reverse("workspaces:project-edit", args=[project.pk]))
        self.assertNotContains(response, "<h2>Create project</h2>", html=False)

    def test_projects_create_workspace_project(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        team = WorkspaceTeam.objects.create(workspace=workspace, name="Product Team", slug="product-team")
        owner = self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:project-create')}?workspace={workspace.slug}",
            {
                "name": "Product Launch",
                "team": team.pk,
                "description": "Launch planning workspace",
            },
        )

        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(workspace=workspace, slug="product-launch")
        self.assertEqual(project.team, team)
        self.assertEqual(project.created_by, owner)
        self.assertEqual(project.description, "Launch planning workspace")
        self.assertEqual(
            response["Location"],
            f"{reverse('workspaces:project-detail', args=[project.pk])}?workspace={workspace.slug}",
        )

    def test_project_edit_route_updates_project_team(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        old_team = WorkspaceTeam.objects.create(workspace=workspace, name="Old Team", slug="old-team")
        new_team = WorkspaceTeam.objects.create(workspace=workspace, name="New Team", slug="new-team")
        project = Project.objects.create(
            workspace=workspace,
            name="Product Launch",
            slug="product-launch",
            description="Old description",
            team=old_team,
        )
        self._force_login_workspace_owner(workspace)

        response = self.client.get(
            f"{reverse('workspaces:project-edit', args=[project.pk])}?workspace={workspace.slug}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit project")
        self.assertContains(response, "Product Launch")

        response = self.client.post(
            f"{reverse('workspaces:project-edit', args=[project.pk])}?workspace={workspace.slug}",
            {
                "name": "Product Launch Updated",
                "team": new_team.pk,
                "description": "Updated description",
            },
        )

        self.assertEqual(response.status_code, 302)
        project.refresh_from_db()
        self.assertEqual(project.name, "Product Launch Updated")
        self.assertEqual(project.description, "Updated description")
        self.assertEqual(project.team, new_team)
        self.assertEqual(
            response["Location"],
            f"{reverse('workspaces:project-detail', args=[project.pk])}?workspace={workspace.slug}",
        )

    def test_project_edit_form_uses_saved_values_and_placeholders(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        project = Project.objects.create(
            workspace=workspace,
            name="Website Redesign",
            slug="website-redesign",
            description="Saved project description",
        )
        empty_description_project = Project.objects.create(
            workspace=workspace,
            name="Internal Tools",
            slug="internal-tools",
            description="",
        )
        self._force_login_workspace_owner(workspace)

        response = self.client.get(
            f"{reverse('workspaces:project-edit', args=[project.pk])}?workspace={workspace.slug}"
        )

        project_form = response.context["project_form"]
        self.assertEqual(project_form["name"].value(), "Website Redesign")
        self.assertEqual(project_form["description"].value(), "Saved project description")
        self.assertEqual(
            project_form.fields["name"].widget.attrs["placeholder"],
            "Project name",
        )
        self.assertEqual(
            project_form.fields["description"].widget.attrs["placeholder"],
            "Describe what this project is for",
        )

        response = self.client.get(
            f"{reverse('workspaces:project-edit', args=[empty_description_project.pk])}?workspace={workspace.slug}"
        )

        project_form = response.context["project_form"]
        self.assertEqual(project_form["name"].value(), "Internal Tools")
        self.assertEqual(project_form["description"].value(), "")
        self.assertNotEqual(
            project_form["description"].value(),
            project_form.fields["description"].widget.attrs["placeholder"],
        )

    def test_projects_rejects_team_from_another_workspace(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        other_workspace = Workspace.objects.create(name="Qazaqstan Retail", slug="qazaqstan-retail")
        other_team = WorkspaceTeam.objects.create(
            workspace=other_workspace,
            name="Retail Team",
            slug="retail-team",
        )
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:project-create')}?workspace={workspace.slug}",
            {
                "name": "Product Launch",
                "team": other_team.pk,
                "description": "Launch planning workspace",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertFalse(Project.objects.filter(workspace=workspace, name="Product Launch").exists())

    def test_project_edit_rejects_team_from_another_workspace(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        other_workspace = Workspace.objects.create(name="Qazaqstan Retail", slug="qazaqstan-retail")
        other_team = WorkspaceTeam.objects.create(
            workspace=other_workspace,
            name="Retail Team",
            slug="retail-team",
        )
        project = Project.objects.create(
            workspace=workspace,
            name="Product Launch",
            slug="product-launch",
        )
        self._force_login_workspace_owner(workspace)

        response = self.client.post(
            f"{reverse('workspaces:project-edit', args=[project.pk])}?workspace={workspace.slug}",
            {
                "name": "Product Launch",
                "team": other_team.pk,
                "description": "Launch planning workspace",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        project.refresh_from_db()
        self.assertIsNone(project.team)

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

    def test_team_department_member_form_excludes_inaccessible_companies(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company_with_full_access = Company.objects.create(name="Company A")
        company_with_department_access = Company.objects.create(name="Company B")
        inaccessible_company = Company.objects.create(name="Company C")
        department = Department.objects.create(company=company_with_department_access, name="Finance")
        Department.objects.create(company=inaccessible_company, name="Legal")
        WorkspaceAccessGrant.objects.create(workspace=workspace, company=company_with_full_access)
        WorkspaceAccessGrant.objects.create(workspace=workspace, department=department)

        form = WorkspaceTeamDepartmentMemberForm(workspace=workspace, prefix="team_department")

        self.assertEqual(
            set(form.fields["company"].queryset.values_list("id", flat=True)),
            {company_with_full_access.id, company_with_department_access.id},
        )

    def test_team_department_member_form_company_grant_exposes_all_company_departments(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Company A")
        finance = Department.objects.create(company=company, name="Finance")
        legal = Department.objects.create(company=company, name="Legal")
        inaccessible_department = Department.objects.create(
            company=Company.objects.create(name="Company B"),
            name="Operations",
        )
        WorkspaceAccessGrant.objects.create(workspace=workspace, company=company)

        form = WorkspaceTeamDepartmentMemberForm(workspace=workspace, prefix="team_department")

        self.assertEqual(
            set(form.fields["department"].queryset.values_list("id", flat=True)),
            {finance.id, legal.id},
        )
        self.assertNotIn(
            inaccessible_department.id,
            form.fields["department"].queryset.values_list("id", flat=True),
        )

    def test_team_department_member_form_department_grant_exposes_only_granted_department(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Company A")
        granted_department = Department.objects.create(company=company, name="Finance")
        other_department = Department.objects.create(company=company, name="Legal")
        WorkspaceAccessGrant.objects.create(workspace=workspace, department=granted_department)

        form = WorkspaceTeamDepartmentMemberForm(workspace=workspace, prefix="team_department")

        self.assertEqual(
            set(form.fields["company"].queryset.values_list("id", flat=True)),
            {company.id},
        )
        self.assertEqual(
            set(form.fields["department"].queryset.values_list("id", flat=True)),
            {granted_department.id},
        )
        self.assertNotIn(
            other_department.id,
            form.fields["department"].queryset.values_list("id", flat=True),
        )

    def test_teams_adds_department_member_when_company_has_workspace_access(self):
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        company = Company.objects.create(name="Company A")
        department = Department.objects.create(company=company, name="Finance")
        WorkspaceAccessGrant.objects.create(workspace=workspace, company=company)
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

        department_grant = WorkspaceAccessGrant.objects.get(workspace=workspace, department=department)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            WorkspaceTeamMember.objects.filter(team=team, access_grant=department_grant).exists()
        )

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
        self.assertContains(response, "Select a valid choice.")
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

    def test_company_workspace_hides_settings_navigation(self):
        company = Company.objects.create(name="Company A")
        workspace = Workspace.objects.create(
            company=company,
            name="Company A",
            slug="company-a",
        )

        response = self.client.get(f"{reverse('workspaces:dashboard')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("workspaces:settings"))

    def test_company_workspace_settings_are_forbidden_for_ceo(self):
        ceo = get_user_model().objects.create_user(
            email="ceo@example.com",
            password="secret",
            system_role="ceo",
        )
        company = Company.objects.create(name="Company A")
        workspace = Workspace.objects.create(
            company=company,
            name="Company A",
            slug="company-a",
        )
        self.client.force_login(ceo)

        settings_response = self.client.get(
            f"{reverse('workspaces:settings')}?workspace={workspace.slug}"
        )
        access_response = self.client.get(
            f"{reverse('workspaces:settings-members-access')}?workspace={workspace.slug}"
        )

        self.assertEqual(settings_response.status_code, 403)
        self.assertEqual(access_response.status_code, 403)

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_company_workspace_settings_use_custom_403_page(self):
        company = Company.objects.create(name="Company A")
        workspace = Workspace.objects.create(
            company=company,
            name="Company A",
            slug="company-a",
        )

        response = self.client.get(f"{reverse('workspaces:settings')}?workspace={workspace.slug}")

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Access denied", status_code=403)
        self.assertNotContains(
            response,
            "Company workspace settings are managed through admin.",
            status_code=403,
        )

    def test_company_workspace_settings_mutations_are_forbidden(self):
        company = Company.objects.create(name="Company A")
        workspace = Workspace.objects.create(
            company=company,
            name="Company A",
            slug="company-a",
        )
        other_company = Company.objects.create(name="Company B")
        grant = WorkspaceAccessGrant.objects.create(workspace=workspace, company=company)

        rename_response = self.client.post(
            f"{reverse('workspaces:settings')}?workspace={workspace.slug}",
            {"name": "Renamed Company Workspace"},
        )
        add_response = self.client.post(
            f"{reverse('workspaces:add-company-access')}?workspace={workspace.slug}",
            {"company": other_company.pk},
        )
        remove_response = self.client.post(
            f"{reverse('workspaces:remove-access', args=[grant.pk])}?workspace={workspace.slug}"
        )

        self.assertEqual(rename_response.status_code, 403)
        self.assertEqual(add_response.status_code, 403)
        self.assertEqual(remove_response.status_code, 403)
        workspace.refresh_from_db()
        self.assertEqual(workspace.name, "Company A")
        self.assertFalse(
            WorkspaceAccessGrant.objects.filter(workspace=workspace, company=other_company).exists()
        )
        self.assertTrue(WorkspaceAccessGrant.objects.filter(pk=grant.pk).exists())

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
        self.assertFalse(
            WorkspaceAccessGrant.objects.filter(
                workspace=workspace,
                user__email="missing@example.com",
            ).exists()
        )

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
        WorkspaceAccessGrant.objects.create(
            workspace=workspace,
            user=member_user,
            role=WorkspaceAccessGrant.Role.MEMBER,
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
        self.assertEqual(
            WorkspaceAccessGrant.objects.filter(
                workspace=workspace,
                user=member_user,
                role=WorkspaceAccessGrant.Role.MEMBER,
            ).count(),
            1,
        )
        self.assertTrue(WorkspaceAccessGrant.objects.filter(pk=grant.pk).exists())

    def test_workspace_name_can_be_updated_by_allowed_user(self):
        user = get_user_model().objects.create_user(email="owner@example.com", password="secret")
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        WorkspaceAccessGrant.objects.create(
            workspace=workspace,
            user=user,
            role=WorkspaceAccessGrant.Role.OWNER,
        )
        self.client.force_login(user)

        response = self.client.post(
            f"{reverse('workspaces:settings')}?workspace={workspace.slug}",
            {"name": "Altyn Group Renamed"},
        )

        self.assertEqual(response.status_code, 302)
        workspace.refresh_from_db()
        self.assertEqual(workspace.name, "Altyn Group Renamed")

    def test_workspace_name_can_be_updated_by_company_admin_grant(self):
        user = get_user_model().objects.create_user(email="admin@example.com", password="secret")
        company = Company.objects.create(name="Company A")
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        CompanyMembership.objects.create(
            user=user,
            company=company,
            role=CompanyMembership.Role.MEMBER,
        )
        WorkspaceAccessGrant.objects.create(
            workspace=workspace,
            company=company,
            role=WorkspaceAccessGrant.Role.ADMIN,
        )
        self.client.force_login(user)

        response = self.client.post(
            f"{reverse('workspaces:settings')}?workspace={workspace.slug}",
            {"name": "Company Admin Workspace"},
        )

        self.assertEqual(response.status_code, 302)
        workspace.refresh_from_db()
        self.assertEqual(workspace.name, "Company Admin Workspace")

    def test_unauthorized_user_cannot_update_workspace_name(self):
        owner_user = get_user_model().objects.create_user(email="owner@example.com", password="secret")
        member_user = get_user_model().objects.create_user(email="member@example.com", password="secret")
        workspace = Workspace.objects.create(name="Altyn Group", slug="altyn-group")
        WorkspaceAccessGrant.objects.create(
            workspace=workspace,
            user=owner_user,
            role=WorkspaceAccessGrant.Role.OWNER,
        )
        WorkspaceAccessGrant.objects.create(
            workspace=workspace,
            user=member_user,
            role=WorkspaceAccessGrant.Role.MEMBER,
        )
        self.client.force_login(member_user)

        response = self.client.post(
            f"{reverse('workspaces:settings')}?workspace={workspace.slug}",
            {"name": "Should Not Change"},
        )

        self.assertEqual(response.status_code, 403)
        workspace.refresh_from_db()
        self.assertEqual(workspace.name, "Altyn Group")
