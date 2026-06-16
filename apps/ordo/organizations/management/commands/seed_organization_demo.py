import json
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.ordo.accounts.models import CompanyMembership, DepartmentMembership
from apps.ordo.organizations.models import Company, Department


DEFAULT_PASSWORD = "password12345"
PRIVATE_SEED_PATH = Path(settings.BASE_DIR) / "local_data" / "private_seed_organization.json"


@dataclass(frozen=True)
class OperatingUser:
    full_name: str
    email: str
    position: str
    company: str
    department: str


@dataclass(frozen=True)
class ManagingUser:
    full_name: str
    email: str
    position: str


PUBLIC_COMPANIES = (
    "Demo Mining Company A",
    "Demo Metals Company B",
    "Demo Holding Services",
    "Demo Exploration Company",
)


PUBLIC_DEPARTMENTS = {
    "Demo Mining Company A": (
        "Management",
        "Finance",
        "Operations",
        "Safety",
    ),
    "Demo Metals Company B": (
        "Management",
        "Geology",
        "Procurement",
        "Finance",
    ),
    "Demo Holding Services": (
        "Management",
        "Legal",
        "HR",
        "Finance",
    ),
    "Demo Exploration Company": (
        "Management",
        "Exploration",
        "Environmental",
        "Audit",
    ),
}


PUBLIC_OPERATING_USERS = (
    OperatingUser(
        "Demo Employee 01",
        "demo.employee01@ordo.local",
        "Finance Lead",
        "Demo Mining Company A",
        "Finance",
    ),
    OperatingUser(
        "Demo Employee 02",
        "demo.employee02@ordo.local",
        "Operations Lead",
        "Demo Mining Company A",
        "Operations",
    ),
    OperatingUser(
        "Demo Employee 03",
        "demo.employee03@ordo.local",
        "Geology Lead",
        "Demo Metals Company B",
        "Geology",
    ),
    OperatingUser(
        "Demo Employee 04",
        "demo.employee04@ordo.local",
        "Procurement Lead",
        "Demo Metals Company B",
        "Procurement",
    ),
    OperatingUser(
        "Demo Employee 05",
        "demo.employee05@ordo.local",
        "Legal Lead",
        "Demo Holding Services",
        "Legal",
    ),
    OperatingUser(
        "Demo Employee 06",
        "demo.employee06@ordo.local",
        "Exploration Lead",
        "Demo Exploration Company",
        "Exploration",
    ),
)


PUBLIC_MANAGING_USERS = (
    ManagingUser("Demo CEO", "demo.ceo@ordo.local", "CEO"),
    ManagingUser("Demo CFO", "demo.cfo@ordo.local", "CFO"),
)


def _load_seed_data():
    if PRIVATE_SEED_PATH.exists():
        raw_data = json.loads(PRIVATE_SEED_PATH.read_text(encoding="utf-8"))
        companies = tuple(raw_data["companies"])
        departments = {
            company: tuple(department_names)
            for company, department_names in raw_data["departments"].items()
        }
        operating_users = tuple(
            OperatingUser(**item)
            for item in raw_data["operating_users"]
        )
        managing_users = tuple(
            ManagingUser(**item)
            for item in raw_data["managing_users"]
        )
        return companies, departments, operating_users, managing_users

    return (
        PUBLIC_COMPANIES,
        PUBLIC_DEPARTMENTS,
        PUBLIC_OPERATING_USERS,
        PUBLIC_MANAGING_USERS,
    )


class Command(BaseCommand):
    help = "Create local demo organization companies, departments, users, and memberships."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        stats = {
            "companies_created": 0,
            "companies_updated": 0,
            "departments_created": 0,
            "departments_updated": 0,
            "users_created": 0,
            "users_updated": 0,
            "memberships_created": 0,
            "memberships_updated": 0,
        }

        companies = {}
        departments = {}
        counted_user_emails = set()
        (
            seed_companies,
            seed_departments,
            seed_operating_users,
            seed_managing_users,
        ) = _load_seed_data()

        for company_name in seed_companies:
            company, created = Company.objects.update_or_create(
                name=company_name,
                defaults={},
            )
            stats["companies_created" if created else "companies_updated"] += 1
            companies[company_name] = company

        for company_name, department_names in seed_departments.items():
            company = companies[company_name]
            for department_name in department_names:
                department, created = Department.objects.update_or_create(
                    company=company,
                    name=department_name,
                    defaults={},
                )
                stats["departments_created" if created else "departments_updated"] += 1
                departments[(company_name, department_name)] = department

        for item in seed_operating_users:
            user, created = User.objects.get_or_create(
                email=item.email,
                defaults={
                    "full_name": item.full_name,
                    "system_role": User.SystemRole.NONE,
                },
            )
            if created:
                user_counter = "users_created"
            else:
                user_counter = "users_updated"

            if item.email not in counted_user_emails:
                stats[user_counter] += 1
                counted_user_emails.add(item.email)

            user.full_name = item.full_name
            user.system_role = User.SystemRole.NONE
            user.set_password(DEFAULT_PASSWORD)
            user.save()

            company_membership, created = CompanyMembership.objects.update_or_create(
                user=user,
                company=companies[item.company],
                defaults={"role": CompanyMembership.Role.MEMBER},
            )
            stats["memberships_created" if created else "memberships_updated"] += 1

            department_membership, created = DepartmentMembership.objects.update_or_create(
                user=user,
                department=departments[(item.company, item.department)],
                defaults={"role": DepartmentMembership.Role.CHIEF},
            )
            stats["memberships_created" if created else "memberships_updated"] += 1

        for item in seed_managing_users:
            user, created = User.objects.get_or_create(
                email=item.email,
                defaults={
                    "full_name": item.full_name,
                    "system_role": User.SystemRole.CEO,
                },
            )
            if created:
                user_counter = "users_created"
            else:
                user_counter = "users_updated"

            if item.email not in counted_user_emails:
                stats[user_counter] += 1
                counted_user_emails.add(item.email)

            user.full_name = item.full_name
            user.system_role = User.SystemRole.CEO
            user.set_password(DEFAULT_PASSWORD)
            user.save()

        self.stdout.write(
            f"Companies: created {stats['companies_created']}, updated {stats['companies_updated']}"
        )
        self.stdout.write(
            f"Departments: created {stats['departments_created']}, updated {stats['departments_updated']}"
        )
        self.stdout.write(
            f"Users: created {stats['users_created']}, updated {stats['users_updated']}"
        )
        self.stdout.write(
            "Memberships: "
            f"created {stats['memberships_created']}, updated {stats['memberships_updated']}"
        )
        self.stdout.write(self.style.SUCCESS("Organization demo data is ready."))
