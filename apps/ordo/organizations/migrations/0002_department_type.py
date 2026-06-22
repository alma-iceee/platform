import django.db.models.deletion
from django.db import migrations, models
from django.utils.text import slugify


def populate_department_types(apps, schema_editor):
    Department = apps.get_model("organizations", "Department")
    DepartmentType = apps.get_model("organizations", "DepartmentType")
    used_company_types = set()

    for department in Department.objects.order_by("id"):
        base_code = slugify(department.name, allow_unicode=True) or f"department-{department.id}"
        department_type, _ = DepartmentType.objects.get_or_create(
            code=base_code,
            defaults={"name": department.name},
        )
        company_type = (department.company_id, department_type.id)
        if company_type in used_company_types:
            raise RuntimeError(
                "Duplicate department type found in company "
                f"{department.company_id}: {department_type.code}."
            )

        department.type_id = department_type.id
        department.save(update_fields=["type"])
        used_company_types.add(company_type)


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DepartmentType",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code", models.SlugField(allow_unicode=True, max_length=100, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddField(
            model_name="department",
            name="type",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="departments",
                to="organizations.departmenttype",
            ),
        ),
        migrations.RunPython(populate_department_types, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="department",
            name="type",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="departments",
                to="organizations.departmenttype",
            ),
        ),
        migrations.AddConstraint(
            model_name="department",
            constraint=models.UniqueConstraint(
                fields=("company", "type"),
                name="unique_department_type_per_company",
            ),
        ),
    ]
