from django.db import migrations, models
from django.utils.text import slugify


CYRILLIC_TO_LATIN = str.maketrans(
    {
        "а": "a", "ә": "a", "б": "b", "в": "v", "г": "g", "ғ": "gh",
        "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
        "і": "i", "й": "i", "к": "k", "қ": "q", "л": "l", "м": "m",
        "н": "n", "ң": "n", "о": "o", "ө": "o", "п": "p", "р": "r",
        "с": "s", "т": "t", "у": "u", "ұ": "u", "ү": "u", "ф": "f",
        "х": "kh", "һ": "h", "ц": "ts", "ч": "ch", "ш": "sh",
        "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e",
        "ю": "yu", "я": "ya",
    }
)


def populate_company_slugs(apps, schema_editor):
    Company = apps.get_model("organizations", "Company")
    used_slugs = set()

    for company in Company.objects.order_by("id"):
        transliterated = company.name.strip().casefold().translate(CYRILLIC_TO_LATIN)
        base_slug = slugify(transliterated, allow_unicode=False) or f"company-{company.id}"
        slug = base_slug
        suffix = 2
        while slug in used_slugs:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        company.slug = slug
        company.save(update_fields=["slug"])
        used_slugs.add(slug)


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0002_department_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="slug",
            # Avoid a deferred PostgreSQL LIKE index before the field becomes
            # unique later in this same migration.
            field=models.SlugField(blank=True, db_index=False, max_length=255, null=True),
        ),
        migrations.RunPython(populate_company_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="company",
            name="slug",
            field=models.SlugField(blank=True, max_length=255, unique=True),
        ),
    ]
