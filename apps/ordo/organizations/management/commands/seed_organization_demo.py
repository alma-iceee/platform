from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.ordo.accounts.models import CompanyMembership, DepartmentMembership
from apps.ordo.organizations.models import Company, Department


DEFAULT_PASSWORD = "password12345"


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


COMPANIES = (
    'ТОО "Jasyl Energy"',
    'ТОО "Aktobe Steels Production"',
    'ТОО "AltynGroup Qazaqstan"',
    'ТОО "Sekisovka"',
)


DEPARTMENTS = {
    'ТОО "Jasyl Energy"': (
        "Бухгалтерия",
        "Отдел кадров",
        "Руководство",
        "Юридический отдел",
        "Отдел ОТ, ТБ, ООС",
        "Отдел МТС",
        "Отдел разработки проектов",
        "Отдел ТП",
    ),
    'ТОО "Aktobe Steels Production"': (
        "Руководство",
        "Геология",
        "Закупки и развитие проектов",
        "Бухгалтерия",
        "Консалтинг",
        "Общий отдел",
    ),
    'ТОО "AltynGroup Qazaqstan"': (
        "Руководство",
        "Производство",
        "Юридический отдел",
        "Горная инженерия",
        "Бухгалтерия",
        "GR и общественные связи",
        "Экология",
        "Общий отдел",
    ),
    'ТОО "Sekisovka"': (
        "Руководство",
        "Производство",
        "Юридический отдел",
        "Недропользование и общественные вопросы",
        "Бухгалтерия",
        "Отдел МТС",
        "Экономический отдел",
        "Финансовая аналитика",
        "Внутренний аудит",
    ),
}


OPERATING_USERS = (
    OperatingUser("Разиева Луиза", "razieva.luiza@ordo.local", "Главный бухгалтер", 'ТОО "Jasyl Energy"', "Бухгалтерия"),
    OperatingUser("Нурмухамет Асель", "nurmukhamet.asel@ordo.local", "Менеджер по налогам", 'ТОО "Jasyl Energy"', "Бухгалтерия"),
    OperatingUser("Куренкова Гизела", "kurenkova.gizela@ordo.local", "Старший специалист по персоналу", 'ТОО "Jasyl Energy"', "Отдел кадров"),
    OperatingUser("Кайнарбаев Серик", "kainarbaev.serik@ordo.local", "Директор по коммерческим вопросам", 'ТОО "Jasyl Energy"', "Руководство"),
    OperatingUser("Евстигнеев Сергей", "evstigneev.sergey@ordo.local", "Директор юридического отдела", 'ТОО "Jasyl Energy"', "Юридический отдел"),
    OperatingUser("Аблаев Калижан", "ablaev.kalizhan@ordo.local", "Генеральный директор", 'ТОО "Jasyl Energy"', "Руководство"),
    OperatingUser("Азербаев Султанбек", "azerbaev.sultanbek@ordo.local", "Заместитель генерального директора / Начальник отдела ОТ, ТБ", 'ТОО "Jasyl Energy"', "Отдел ОТ, ТБ, ООС"),
    OperatingUser("Набиев Тенел", "nabiev.tenel@ordo.local", "Начальник отдела МТС", 'ТОО "Jasyl Energy"', "Отдел МТС"),
    OperatingUser("Чеботарев Сергей", "chebotarev.sergey@ordo.local", "Начальник отдела по разработке проектов", 'ТОО "Jasyl Energy"', "Отдел разработки проектов"),
    OperatingUser("Язов Антон", "yazov.anton@ordo.local", "Старший специалист по ТП", 'ТОО "Jasyl Energy"', "Отдел ТП"),
    OperatingUser("Тимофеев Юрий", "timofeev.yuriy@ordo.local", "Главный геолог", 'ТОО "Aktobe Steels Production"', "Геология"),
    OperatingUser("Урынбасаров Аслан", "urynbasarov.aslan@ordo.local", "Менеджер", 'ТОО "Aktobe Steels Production"', "Общий отдел"),
    OperatingUser("Тимофеев Борис", "timofeev.boris@ordo.local", "Менеджер по закупам и развитию проектов", 'ТОО "Aktobe Steels Production"', "Закупки и развитие проектов"),
    OperatingUser("Леваневский", "levanevsky.user@ordo.local", "Консультант", 'ТОО "Aktobe Steels Production"', "Консалтинг"),
    OperatingUser("Гусейн Индира", "gusein.indira@ordo.local", "Бухгалтер", 'ТОО "Aktobe Steels Production"', "Бухгалтерия"),
    OperatingUser("Арипжанов Ерик", "aripzhanov.erik@ordo.local", "Без должности", 'ТОО "Aktobe Steels Production"', "Общий отдел"),
    OperatingUser("Ашимова Ардак", "ashimova.ardak@ordo.local", "Без должности", 'ТОО "Aktobe Steels Production"', "Общий отдел"),
    OperatingUser("Сырбай Ералы", "syrbai.eraly@ordo.local", "Директор", 'ТОО "AltynGroup Qazaqstan"', "Руководство"),
    OperatingUser("Арипжанов Ерик", "aripzhanov.erik@ordo.local", "Заместитель директора по производству", 'ТОО "AltynGroup Qazaqstan"', "Производство"),
    OperatingUser("Маметов Шухрат", "mametov.shukhrat@ordo.local", "Юрист", 'ТОО "AltynGroup Qazaqstan"', "Юридический отдел"),
    OperatingUser("Жоламанов Оралбек", "zholamanov.oralbek@ordo.local", "Главный горный инженер по разведочным проектам", 'ТОО "AltynGroup Qazaqstan"', "Горная инженерия"),
    OperatingUser("Метельская Марина", "metelskaya.marina@ordo.local", "Главный бухгалтер", 'ТОО "AltynGroup Qazaqstan"', "Бухгалтерия"),
    OperatingUser("Сайдельдаев Айбек", "saideldajev.aibek@ordo.local", "Заместитель директора по связям с общественностью и госорганами", 'ТОО "AltynGroup Qazaqstan"', "GR и общественные связи"),
    OperatingUser("Пахомов Олег", "pakhomov.oleg@ordo.local", "Эколог", 'ТОО "AltynGroup Qazaqstan"', "Экология"),
    OperatingUser("Шаяхметов Сандугаш", "shayakhmetov.sandugash@ordo.local", "Без должности", 'ТОО "AltynGroup Qazaqstan"', "Общий отдел"),
    OperatingUser("Ашимова Ардак", "ashimova.ardak@ordo.local", "Без должности", 'ТОО "AltynGroup Qazaqstan"', "Общий отдел"),
    OperatingUser("Баймагулов Нуржан", "baimagulov.nurzhan@ordo.local", "Региональный директор", 'ТОО "Sekisovka"', "Руководство"),
    OperatingUser("Балашов Евгений", "balashov.evgeniy@ordo.local", "Региональный директор по производству", 'ТОО "Sekisovka"', "Производство"),
    OperatingUser("Магавьянов Болат", "magavyanov.bolat@ordo.local", 'Директор ТОО "Baurgold"', 'ТОО "Sekisovka"', "Руководство"),
    OperatingUser("Кабдоллаев Мерей", "kabdollaev.merey@ordo.local", 'Директор ТОО "Altyn MM"', 'ТОО "Sekisovka"', "Руководство"),
    OperatingUser("Шаяхметов Сандугаш", "shayakhmetov.sandugash@ordo.local", "Главный юрист", 'ТОО "Sekisovka"', "Юридический отдел"),
    OperatingUser("Ашимова Ардак", "ashimova.ardak@ordo.local", "Заместитель директора по недропользованию и общественным вопросам", 'ТОО "Sekisovka"', "Недропользование и общественные вопросы"),
    OperatingUser("Дементьева Надежда", "dementeva.nadezhda@ordo.local", 'Главный бухгалтер ТОО "Baurgold"', 'ТОО "Sekisovka"', "Бухгалтерия"),
    OperatingUser("Жангулакова Сания", "zhangulakova.saniya@ordo.local", 'Главный бухгалтер ТОО "Altyn MM"', 'ТОО "Sekisovka"', "Бухгалтерия"),
    OperatingUser("Бейсенбаев Данияр", "beisenbaev.daniyar@ordo.local", "Начальник ДМТС", 'ТОО "Sekisovka"', "Отдел МТС"),
    OperatingUser("Королева Ирина", "koroleva.irina@ordo.local", "Начальник экономического отдела", 'ТОО "Sekisovka"', "Экономический отдел"),
    OperatingUser("Кутлиметов Ренат", "kutlimetov.renat@ordo.local", "Главный финансовый аналитик", 'ТОО "Sekisovka"', "Финансовая аналитика"),
    OperatingUser("Шатов Илья", "shatov.ilya@ordo.local", "Руководитель внутреннего аудита", 'ТОО "Sekisovka"', "Внутренний аудит"),
    OperatingUser("Беззубцева Анна", "bezzubtseva.anna@ordo.local", "Внутренний аудитор", 'ТОО "Sekisovka"', "Внутренний аудит"),
)


MANAGING_USERS = (
    ManagingUser("Ирсалиев Талгат", "irsaliev.talgat@ordo.local", "Управляющий директор"),
    ManagingUser("Ергали Арман", "ergali.arman@ordo.local", "Директор по развитию бизнеса"),
    ManagingUser("Бижигитова Салтанат", "bizhigitova.saltanat@ordo.local", "Директор по персоналу и администрации"),
    ManagingUser("Тлекметов Асхат", "tlekmetov.askhat@ordo.local", "Финансовый директор"),
    ManagingUser("Бурибаева Марьям", "buribaeva.maryam@ordo.local", ""),
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

        for company_name in COMPANIES:
            company, created = Company.objects.update_or_create(
                name=company_name,
                defaults={},
            )
            stats["companies_created" if created else "companies_updated"] += 1
            companies[company_name] = company

        for company_name, department_names in DEPARTMENTS.items():
            company = companies[company_name]
            for department_name in department_names:
                department, created = Department.objects.update_or_create(
                    company=company,
                    name=department_name,
                    defaults={},
                )
                stats["departments_created" if created else "departments_updated"] += 1
                departments[(company_name, department_name)] = department

        for item in OPERATING_USERS:
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

        for item in MANAGING_USERS:
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
