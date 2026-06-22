from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.ordo.organizations.models import Company, Department
from apps.ordo.workspaces.models import (
    Project,
    Workspace,
    WorkspaceAccessGrant,
)
from apps.ordo.workspaces.services import sync_workspace_department_teams


ROLE_PRIORITY = {
    WorkspaceAccessGrant.Role.VIEWER: 0,
    WorkspaceAccessGrant.Role.MEMBER: 1,
    WorkspaceAccessGrant.Role.ADMIN: 2,
    WorkspaceAccessGrant.Role.OWNER: 3,
}


CROSS_COMPANY_WORKSPACES = (
    {
        "slug": "ore-gold-program",
        "name": "Рудная программа и золотые участки",
        "description": "Совместная программа по оценке рудных участков, разведке и подготовке добычных решений.",
        "projects": (
            {
                "slug": "gold-sites-2026",
                "name": "Оценка золоторудных участков 2026",
                "description": "Сбор геологических данных, приоритизация участков и подготовка решений по разведке.",
                "team_slug": "geology-licenses",
                "team_name": "Геология и лицензии",
                "team_description": "Геология, недропользование и разрешительная документация.",
                "members": {"companies": (0, 1)},
            },
            {
                "slug": "drilling-budget",
                "name": "Бюджет буровой программы",
                "description": "Расчет CAPEX/OPEX, налоговых эффектов и лимитов по буровым работам.",
                "team_slug": "budget-taxes",
                "team_name": "Бюджет и налоги",
                "team_description": "Финансы, бухгалтерия и налоговое планирование.",
                "members": {"departments": (0, 4), "users": (0,)},
            },
            {
                "slug": "drilling-contractors-tender",
                "name": "Тендер на буровых подрядчиков",
                "description": "Сравнение ставок подрядчиков, технических условий и договорных рисков.",
                "team_slug": "tender-committee",
                "team_name": "Тендерный комитет",
                "team_description": "Закупки, юристы и технические специалисты для отбора поставщиков.",
                "members": {"companies": (1,), "departments": (5, 8), "users": (1,)},
            },
            {
                "slug": "exploration-hse",
                "name": "Экология и ОТ для разведки",
                "description": "Контроль экологических требований, охраны труда и промбезопасности на разведочных работах.",
                "team_slug": "hse-environment",
                "team_name": "Экология и безопасность",
                "team_description": "Экология, ОТ, ТБ и производственная безопасность.",
                "members": {"departments": (3, 10), "users": (2, 3)},
            },
            {
                "slug": "core-samples-logistics",
                "name": "Логистика проб и керна",
                "description": "Маршруты, хранение, перевозка и учет проб между участками, складами и лабораториями.",
                "team_slug": "site-logistics",
                "team_name": "Логистика месторождений",
                "team_description": "Логистика, склады и операционные координаторы участков.",
                "members": {"companies": (2, 3), "users": (4,)},
            },
        ),
    },
    {
        "slug": "equipment-procurement",
        "name": "Закупки техники и промышленных поставок",
        "description": "Единый контур тендеров, сравнений цен и закупок для добычных и производственных активов.",
        "projects": (
            {
                "slug": "mining-fleet-purchase",
                "name": "Закупка карьерной техники",
                "description": "Сравнение поставщиков самосвалов, экскаваторов и сервисных условий.",
                "team_slug": "mining-equipment",
                "team_name": "Горная техника",
                "team_description": "Производство, закупки и технические специалисты по карьерной технике.",
                "members": {"companies": (0, 1)},
            },
            {
                "slug": "pump-equipment-tender",
                "name": "Тендер на насосное оборудование",
                "description": "Подбор насосов, анализ цен, сроков поставки и гарантийных условий.",
                "team_slug": "pump-systems",
                "team_name": "Насосные системы",
                "team_description": "Технический блок, МТС и закупки насосного оборудования.",
                "members": {"departments": (6, 12), "users": (5,)},
            },
            {
                "slug": "reagents-price-benchmark",
                "name": "Сравнение цен на реагенты",
                "description": "Сбор коммерческих предложений и анализ стоимости реагентов для производственных нужд.",
                "team_slug": "market-pricing",
                "team_name": "Цены и рынок",
                "team_description": "Закупки, финансы и производственные заказчики.",
                "members": {"companies": (0,), "departments": (1, 9), "users": (6,)},
            },
            {
                "slug": "spare-parts-service-contracts",
                "name": "Сервисные контракты и запасные части",
                "description": "Планирование сервисных договоров, складских остатков и критичных запасных частей.",
                "team_slug": "service-spares",
                "team_name": "Сервис и ЗИП",
                "team_description": "МТС, эксплуатация и сервисные координаторы.",
                "members": {"departments": (7, 14), "users": (7, 8)},
            },
            {
                "slug": "import-logistics-customs",
                "name": "Импортная логистика и таможня",
                "description": "Расчет маршрутов, таможенных платежей, сроков и рисков поставки импортного оборудования.",
                "team_slug": "import-logistics",
                "team_name": "Импорт и логистика",
                "team_description": "Логистика, юристы, финансы и закупки.",
                "members": {"companies": (3,), "departments": (2,), "users": (9,)},
            },
        ),
    },
    {
        "slug": "oilfield-infrastructure",
        "name": "Нефтяные активы и инфраструктура",
        "description": "Проекты по нефтяным вышкам, инфраструктуре, сервисным контрактам и промышленной безопасности.",
        "projects": (
            {
                "slug": "oil-rig-modernization",
                "name": "Модернизация нефтяных вышек",
                "description": "План модернизации оборудования, график остановок и оценка производственного эффекта.",
                "team_slug": "rig-modernization",
                "team_name": "Модернизация вышек",
                "team_description": "Инженеры, производство и подрядчики по нефтяной инфраструктуре.",
                "members": {"companies": (0, 1)},
            },
            {
                "slug": "compressors-pumps-supply",
                "name": "Поставка насосов и компрессоров",
                "description": "Подбор поставщиков, спецификаций и условий поставки насосно-компрессорного оборудования.",
                "team_slug": "compressors-pumps",
                "team_name": "Насосы и компрессоры",
                "team_description": "Технический блок, закупки и логистика.",
                "members": {"departments": (11, 16), "users": (10,)},
            },
            {
                "slug": "service-contract-tax-model",
                "name": "Налоговая модель по сервисным контрактам",
                "description": "Проверка налоговой нагрузки, валютных условий и структуры сервисных договоров.",
                "team_slug": "tax-service-model",
                "team_name": "Налоги и сервисные договоры",
                "team_description": "Финансы, бухгалтерия, юристы и контрактный блок.",
                "members": {"companies": (2,), "departments": (13, 17), "users": (11,)},
            },
            {
                "slug": "oilfield-environment-monitoring",
                "name": "Безопасность и экологический мониторинг",
                "description": "Контроль экологических показателей, требований HSE и отчетности по объектам.",
                "team_slug": "oilfield-hse",
                "team_name": "HSE нефтяных объектов",
                "team_description": "Экология, ОТ, ТБ и производственные ответственные.",
                "members": {"departments": (15, 18), "users": (12, 13)},
            },
            {
                "slug": "shift-camps-supply",
                "name": "Снабжение вахтовых поселков",
                "description": "Планирование поставок, складских запасов и логистики для удаленных объектов.",
                "team_slug": "camp-supply",
                "team_name": "Снабжение объектов",
                "team_description": "МТС, логистика и операционные координаторы.",
                "members": {"companies": (1,), "departments": (19,), "users": (14,)},
            },
        ),
    },
)


def _unique_workspace_slug(name):
    base_slug = slugify(name, allow_unicode=True) or "workspace"
    slug = base_slug
    suffix = 2
    while Workspace.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return slug


def _find_company_workspace(company):
    workspace = Workspace.objects.filter(company=company).order_by("id").first()
    if workspace:
        return workspace

    return (
        Workspace.objects.filter(company__isnull=True, name=company.name)
        .order_by("id")
        .first()
    )


def _ensure_member_or_higher(grant):
    if ROLE_PRIORITY[grant.role] < ROLE_PRIORITY[WorkspaceAccessGrant.Role.MEMBER]:
        grant.role = WorkspaceAccessGrant.Role.MEMBER
        grant.save(update_fields=["role"])
        return True
    return False


def _ensure_company_member_grant(workspace, company):
    grant, created = WorkspaceAccessGrant.objects.get_or_create(
        workspace=workspace,
        company=company,
        defaults={"role": WorkspaceAccessGrant.Role.MEMBER},
    )
    updated = False
    if not created:
        updated = _ensure_member_or_higher(grant)
    return grant, created, updated


def _ensure_department_member_grant(workspace, department):
    grant, created = WorkspaceAccessGrant.objects.get_or_create(
        workspace=workspace,
        department=department,
        defaults={"role": WorkspaceAccessGrant.Role.MEMBER},
    )
    updated = False
    if not created:
        updated = _ensure_member_or_higher(grant)
    return grant, created, updated


def _ensure_user_member_grant(workspace, user):
    grant, created = WorkspaceAccessGrant.objects.get_or_create(
        workspace=workspace,
        user=user,
        defaults={"role": WorkspaceAccessGrant.Role.MEMBER},
    )
    updated = False
    if not created:
        updated = _ensure_member_or_higher(grant)
    return grant, created, updated


def _select_companies(companies, indexes):
    return _select_by_indexes(companies, indexes)


def _select_departments(departments, indexes):
    return _select_by_indexes(departments, indexes)


def _select_users(users, indexes):
    return _select_by_indexes(users, indexes)


def _select_by_indexes(items, indexes):
    if not items:
        return []

    selected = []
    seen_ids = set()
    for index in indexes:
        item = items[index % len(items)]
        if item.id in seen_ids:
            continue
        selected.append(item)
        seen_ids.add(item.id)
    return selected


def _iter_team_subjects(project_data, companies, departments, users):
    members = project_data["members"]
    for company in _select_companies(companies, members.get("companies", ())):
        yield "company", company
    for department in _select_departments(departments, members.get("departments", ())):
        yield "department", department
    for user in _select_users(users, members.get("users", ())):
        yield "user", user


def _ensure_subject_member_grant(workspace, subject_type, subject):
    if subject_type == "company":
        return _ensure_company_member_grant(workspace, subject)
    if subject_type == "department":
        return _ensure_department_member_grant(workspace, subject)
    if subject_type == "user":
        return _ensure_user_member_grant(workspace, subject)
    raise ValueError(f"Unsupported team subject type: {subject_type}")


def _ensure_cross_company_workspace(workspace_data):
    workspace = Workspace.objects.filter(slug=workspace_data["slug"]).first()
    if workspace is None:
        return (
            Workspace.objects.create(
                company=None,
                slug=workspace_data["slug"],
                name=workspace_data["name"],
                description=workspace_data["description"],
                is_active=True,
            ),
            True,
            False,
        )

    changed_fields = []
    if workspace.company_id is not None:
        workspace.company = None
        changed_fields.append("company")
    if workspace.name != workspace_data["name"]:
        workspace.name = workspace_data["name"]
        changed_fields.append("name")
    if workspace.description != workspace_data["description"]:
        workspace.description = workspace_data["description"]
        changed_fields.append("description")
    if not workspace.is_active:
        workspace.is_active = True
        changed_fields.append("is_active")

    if changed_fields:
        workspace.save(update_fields=changed_fields)
        return workspace, False, True

    return workspace, False, False


def _project_department_type(project_data, companies, departments):
    members = project_data["members"]
    selected_departments = _select_departments(
        departments,
        members.get("departments", ()),
    )
    if selected_departments:
        return selected_departments[0].type

    selected_company_ids = {
        company.id
        for company in _select_companies(companies, members.get("companies", ()))
    }
    return next(
        (
            department.type
            for department in departments
            if department.company_id in selected_company_ids
        ),
        None,
    )


def _ensure_project(workspace, team, project_data):
    project = Project.objects.filter(
        workspace=workspace,
        slug=project_data["slug"],
    ).first()
    if project is None:
        return (
            Project.objects.create(
                workspace=workspace,
                team=team,
                slug=project_data["slug"],
                name=project_data["name"],
                description=project_data["description"],
                is_active=True,
            ),
            True,
            False,
        )

    changed_fields = []
    team_id = team.id if team is not None else None
    if project.team_id != team_id:
        project.team = team
        changed_fields.append("team")
    if project.name != project_data["name"]:
        project.name = project_data["name"]
        changed_fields.append("name")
    if project.description != project_data["description"]:
        project.description = project_data["description"]
        changed_fields.append("description")
    if not project.is_active:
        project.is_active = True
        changed_fields.append("is_active")

    if changed_fields:
        project.save(update_fields=changed_fields)
        return project, False, True

    return project, False, False


class Command(BaseCommand):
    help = "Create demo company workspaces, cross-company workspaces, teams, and projects."

    @transaction.atomic
    def handle(self, *args, **options):
        stats = {
            "company_workspaces_created": 0,
            "company_workspaces_updated": 0,
            "cross_workspaces_created": 0,
            "cross_workspaces_updated": 0,
            "access_grants_created": 0,
            "access_grants_updated": 0,
            "access_grants_removed": 0,
            "teams_created": 0,
            "teams_updated": 0,
            "team_members_created": 0,
            "team_members_removed": 0,
            "projects_created": 0,
            "projects_updated": 0,
        }
        companies = list(Company.objects.order_by("name"))
        departments = list(
            Department.objects.select_related("company", "type").order_by(
                "company__name", "name"
            )
        )
        users = list(get_user_model().objects.order_by("email"))

        for company in companies:
            workspace = _find_company_workspace(company)
            if workspace is None:
                workspace = Workspace.objects.create(
                    company=company,
                    name=company.name,
                    slug=_unique_workspace_slug(company.name),
                    is_active=True,
                )
                stats["company_workspaces_created"] += 1
            else:
                changed_fields = []
                if workspace.company_id != company.id:
                    workspace.company = company
                    changed_fields.append("company")
                if workspace.name != company.name:
                    workspace.name = company.name
                    changed_fields.append("name")
                if not workspace.is_active:
                    workspace.is_active = True
                    changed_fields.append("is_active")

                if changed_fields:
                    workspace.save(update_fields=changed_fields)
                    stats["company_workspaces_updated"] += 1

            _grant, created, updated = _ensure_company_member_grant(workspace, company)
            if created:
                stats["access_grants_created"] += 1
            elif updated:
                stats["access_grants_updated"] += 1

        for workspace_data in CROSS_COMPANY_WORKSPACES:
            workspace, created, updated = _ensure_cross_company_workspace(workspace_data)
            if created:
                stats["cross_workspaces_created"] += 1
            elif updated:
                stats["cross_workspaces_updated"] += 1

            initial_team_ids = set(
                workspace.workspace_teams.filter(
                    department_type__isnull=False,
                ).values_list("id", flat=True)
            )
            expected_workspace_grant_ids = set()
            for project_data in workspace_data["projects"]:
                subjects = list(_iter_team_subjects(project_data, companies, departments, users))
                if not subjects:
                    subjects = [("company", company) for company in _select_companies(companies, (0, 1))]

                for subject_type, subject in subjects:
                    grant, created, updated = _ensure_subject_member_grant(
                        workspace,
                        subject_type,
                        subject,
                    )
                    expected_workspace_grant_ids.add(grant.id)
                    if created:
                        stats["access_grants_created"] += 1
                    elif updated:
                        stats["access_grants_updated"] += 1

                sync_workspace_department_teams(workspace)
                department_type = _project_department_type(
                    project_data,
                    companies,
                    departments,
                )
                team = workspace.workspace_teams.filter(
                    department_type=department_type,
                    is_active=True,
                ).first()
                if team is None:
                    team = workspace.workspace_teams.filter(
                        department_type__isnull=False,
                        is_active=True,
                    ).first()

                _project, created, updated = _ensure_project(workspace, team, project_data)
                if created:
                    stats["projects_created"] += 1
                elif updated:
                    stats["projects_updated"] += 1

            removed_grants, _deleted = WorkspaceAccessGrant.objects.filter(
                workspace=workspace,
                role=WorkspaceAccessGrant.Role.MEMBER,
                is_system_generated=False,
            ).exclude(id__in=expected_workspace_grant_ids).delete()
            stats["access_grants_removed"] += removed_grants
            sync_workspace_department_teams(workspace)

            final_team_ids = set(
                workspace.workspace_teams.filter(
                    department_type__isnull=False,
                ).values_list("id", flat=True)
            )
            stats["teams_created"] += len(final_team_ids - initial_team_ids)

        self.stdout.write(
            "Company workspaces: "
            f"created {stats['company_workspaces_created']}, "
            f"updated {stats['company_workspaces_updated']}"
        )
        self.stdout.write(
            "Cross-company workspaces: "
            f"created {stats['cross_workspaces_created']}, "
            f"updated {stats['cross_workspaces_updated']}"
        )
        self.stdout.write(
            "Workspace access grants: "
            f"created {stats['access_grants_created']}, "
            f"updated {stats['access_grants_updated']}, "
            f"removed {stats['access_grants_removed']}"
        )
        self.stdout.write(
            "Workspace teams: "
            f"created {stats['teams_created']}, updated {stats['teams_updated']}"
        )
        self.stdout.write(
            "Workspace team members: "
            f"created {stats['team_members_created']}, removed {stats['team_members_removed']}"
        )
        self.stdout.write(
            "Projects: "
            f"created {stats['projects_created']}, updated {stats['projects_updated']}"
        )
        self.stdout.write(self.style.SUCCESS("Workspace demo data is ready."))
