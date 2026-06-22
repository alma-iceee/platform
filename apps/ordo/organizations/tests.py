from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.ordo.accounts.models import CompanyMembership, DepartmentMembership
from apps.ordo.organizations.management.commands import seed_organization_demo
from apps.ordo.organizations.models import Company, Department, DepartmentType
from apps.ordo.workspaces.models import Project, Workspace, WorkspaceAccessGrant, WorkspaceTeam


class SeedOrganizationDemoCommandTests(TestCase):
    def call_seed(self):
        stdout = StringIO()
        with patch.object(
            seed_organization_demo,
            "PRIVATE_SEED_PATH",
            Path("/tmp/ordo-missing-private-seed.json"),
        ):
            call_command("seed_organization_demo", stdout=stdout)
        return stdout.getvalue()

    def test_command_runs_successfully(self):
        output = self.call_seed()

        self.assertIn("Organization demo data is ready.", output)
        self.assertEqual(Company.objects.count(), 4)
        self.assertEqual(DepartmentType.objects.count(), 11)

    def test_command_is_idempotent(self):
        self.call_seed()
        first_counts = {
            "companies": Company.objects.count(),
            "department_types": DepartmentType.objects.count(),
            "departments": Department.objects.count(),
            "users": get_user_model().objects.count(),
            "company_memberships": CompanyMembership.objects.count(),
            "department_memberships": DepartmentMembership.objects.count(),
        }

        self.call_seed()

        self.assertEqual(Company.objects.count(), first_counts["companies"])
        self.assertEqual(DepartmentType.objects.count(), first_counts["department_types"])
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
                "Demo Exploration Company",
                "Demo Holding Services",
                "Demo Metals Company B",
                "Demo Mining Company A",
            ],
        )
        self.assertTrue(
            Department.objects.filter(
                company__name="Demo Mining Company A",
                name="Operations",
                type__code="operations",
            ).exists()
        )
        self.assertTrue(
            Department.objects.filter(
                company__name="Demo Exploration Company",
                name="Audit",
                type__code="audit",
            ).exists()
        )

        finance_type = DepartmentType.objects.get(code="finance")
        self.assertEqual(finance_type.departments.count(), 3)

    def test_operating_company_users_are_department_chiefs(self):
        self.call_seed()

        memberships = DepartmentMembership.objects.all()
        self.assertEqual(memberships.count(), len(seed_organization_demo.PUBLIC_OPERATING_USERS))
        self.assertFalse(memberships.exclude(role=DepartmentMembership.Role.CHIEF).exists())

    def test_managing_company_users_have_ceo_system_role(self):
        self.call_seed()
        User = get_user_model()

        ceo_emails = {
            item.email
            for item in seed_organization_demo.PUBLIC_MANAGING_USERS
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

    def test_seed_creates_one_user_per_email(self):
        self.call_seed()
        User = get_user_model()

        seed_emails = {
            item.email
            for item in (
                seed_organization_demo.PUBLIC_OPERATING_USERS
                + seed_organization_demo.PUBLIC_MANAGING_USERS
            )
        }

        self.assertEqual(User.objects.count(), len(seed_emails) + 1)

    def test_seed_creates_admin_superuser(self):
        self.call_seed()
        User = get_user_model()

        admin_user = User.objects.get(email=seed_organization_demo.ADMIN_EMAIL)

        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.is_active)
        self.assertTrue(admin_user.check_password(seed_organization_demo.ADMIN_PASSWORD))
        self.assertFalse(CompanyMembership.objects.filter(user=admin_user).exists())
        self.assertFalse(DepartmentMembership.objects.filter(user=admin_user).exists())

    def test_command_does_not_seed_workspace_data(self):
        self.call_seed()

        self.assertEqual(Workspace.objects.count(), 0)
        self.assertEqual(Project.objects.count(), 0)
        self.assertEqual(WorkspaceTeam.objects.count(), 0)
        self.assertEqual(WorkspaceAccessGrant.objects.count(), 0)


class DepartmentModelTests(TestCase):
    def test_company_cannot_have_duplicate_department_type(self):
        company = Company.objects.create(name="Company A")
        department_type = DepartmentType.objects.create(code="finance", name="Finance")
        Department.objects.create(
            company=company,
            type=department_type,
            name="Finance",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Department.objects.create(
                company=company,
                type=department_type,
                name="Accounting",
            )

    def test_department_type_can_be_shared_by_companies(self):
        company_a = Company.objects.create(name="Company A")
        company_b = Company.objects.create(name="Company B")
        department_type = DepartmentType.objects.create(code="finance", name="Finance")

        Department.objects.create(company=company_a, type=department_type, name="Finance")
        Department.objects.create(company=company_b, type=department_type, name="Accounting")

        self.assertEqual(department_type.departments.count(), 2)
