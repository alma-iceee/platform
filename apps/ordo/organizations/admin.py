from django.contrib import admin

from .models import Company, Department, DepartmentType


@admin.register(DepartmentType)
class DepartmentTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "created_at", "updated_at")
    search_fields = ("name", "code")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at", "updated_at")
    search_fields = ("name", "slug")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "company", "created_at", "updated_at")
    list_filter = ("type", "company")
    search_fields = ("name", "type__name", "type__code", "company__name")
    autocomplete_fields = ("company", "type")
    ordering = ("company__name", "name")
