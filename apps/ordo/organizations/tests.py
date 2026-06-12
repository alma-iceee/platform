from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.ordo.accounts.models import CompanyMembership, DepartmentMembership
from apps.ordo.organizations.models import Company, Department
from apps.ordo.workspaces.models import Project, Workspace, WorkspaceAccessGrant, WorkspaceTeam


class SeedOrganizationDemoCommandTests(TestCase):
    def call_seed(self):
        stdout = StringIO()
        call_command("seed_organization_demo", stdout=stdout)
        return stdout.getvalue()

    def test_command_runs_successfully(self):
        output = self.call_seed()

        self.assertIn("Organization demo data is ready.", output)
        self.assertEqual(Company.objects.count(), 4)

    def test_command_is_idempotent(self):
        self.call_seed()
        first_counts = {
            "companies": Company.objects.count(),
            "departments": Department.objects.count(),
            "users": get_user_model().objects.count(),
            "company_memberships": CompanyMembership.objects.count(),
            "department_memberships": DepartmentMembership.objects.count(),
        }

        self.call_seed()

        self.assertEqual(Company.objects.count(), first_counts["companies"])
        self.assertEqual(Department.objects.count(), first_counts["departments"])
        self.assertEqual(get_user_model().objects.count(), first_counts["users"])
        self.assertEqual(CompanyMembership.objects.count(), first_counts["company_memberships"])
        self.assertEqual(
            DepartmentMembership.objects.count(),
            first_counts["department_memberships"],
        )

    def test_seed_creates_expected_companies_and_key_departments(self):
        self.call_seed()

        self.assertQuerySetEqual(
            Company.objects.order_by("name").values_list("name", flat=True),
            [
                'ТОО "Aktobe Steels Production"',
                'ТОО "AltynGroup Qazaqstan"',
                'ТОО "Jasyl Energy"',
                'ТОО "Sekisovka"',
            ],
        )
        self.assertTrue(
            Department.objects.filter(
                company__name='ТОО "Jasyl Energy"',
                name="Отдел разработки проектов",
            ).exists()
        )
        self.assertTrue(
            Department.objects.filter(
                company__name='ТОО "Sekisovka"',
                name="Внутренний аудит",
            ).exists()
        )

    def test_operating_company_users_are_department_chiefs(self):
        self.call_seed()

        memberships = DepartmentMembership.objects.all()
        self.assertEqual(memberships.count(), 39)
        self.assertFalse(memberships.exclude(role=DepartmentMembership.Role.CHIEF).exists())

    def test_managing_company_users_have_ceo_system_role(self):
        self.call_seed()
        User = get_user_model()

        ceo_emails = {
            "irsaliev.talgat@ordo.local",
            "ergali.arman@ordo.local",
            "bizhigitova.saltanat@ordo.local",
            "tlekmetov.askhat@ordo.local",
            "buribaeva.maryam@ordo.local",
        }
        self.assertEqual(
            set(
                User.objects.filter(system_role=User.SystemRole.CEO).values_list(
                    "email",
                    flat=True,
                )
            ),
            ceo_emails,
        )
        self.assertFalse(CompanyMembership.objects.filter(user__email__in=ceo_emails).exists())
        self.assertFalse(DepartmentMembership.objects.filter(user__email__in=ceo_emails).exists())

    def test_duplicate_people_are_single_users_with_multiple_memberships(self):
        self.call_seed()
        User = get_user_model()

        aripzhanov = User.objects.get(email="aripzhanov.erik@ordo.local")
        ashimova = User.objects.get(email="ashimova.ardak@ordo.local")
        shayakhmetov = User.objects.get(email="shayakhmetov.sandugash@ordo.local")

        self.assertEqual(aripzhanov.company_memberships.count(), 2)
        self.assertEqual(ashimova.company_memberships.count(), 3)
        self.assertEqual(shayakhmetov.company_memberships.count(), 2)

    def test_command_does_not_seed_workspace_data(self):
        self.call_seed()

        self.assertEqual(Workspace.objects.count(), 0)
        self.assertEqual(Project.objects.count(), 0)
        self.assertEqual(WorkspaceTeam.objects.count(), 0)
        self.assertEqual(WorkspaceAccessGrant.objects.count(), 0)
