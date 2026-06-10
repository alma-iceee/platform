from django.contrib import admin

from .models import Company, Department


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name",)
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "created_at", "updated_at")
    list_filter = ("company",)
    search_fields = ("name", "company__name")
    autocomplete_fields = ("company",)
    ordering = ("company__name", "name")