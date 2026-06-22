from django.db import models

from .slugs import unreserved_root_slug


class DepartmentType(models.Model):
    code = models.SlugField(max_length=100, unique=True, allow_unicode=True)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Company(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "companies"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        base_slug = unreserved_root_slug(
            self.slug or self.name,
            fallback="company",
            suffix="company",
        )
        slug = base_slug
        suffix = 2
        existing = type(self).objects.exclude(pk=self.pk)
        while existing.filter(slug=slug).exists():
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        self.slug = slug
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"slug"}
        super().save(*args, **kwargs)


class Department(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="departments",
    )
    type = models.ForeignKey(
        DepartmentType,
        on_delete=models.PROTECT,
        related_name="departments",
    )
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"],
                name="unique_department_name_per_company",
            ),
            models.UniqueConstraint(
                fields=["company", "type"],
                name="unique_department_type_per_company",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.company}: {self.name}"
