from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import CompanyMembership, DepartmentMembership, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User

    list_display = (
        "email",
        "full_name",
        "system_role",
        "is_staff",
        "is_active",
    )
    list_filter = (
        "system_role",
        "is_staff",
        "is_active",
    )
    search_fields = (
        "email",
        "full_name",
    )
    ordering = ("email",)

    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Ordo",
            {
                "fields": (
                    "full_name",
                    "system_role",
                    "email_notifications_enabled",
                    "telegram_notifications_enabled",
                )
            },
        ),
    )

    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        (
            "Ordo",
            {
                "fields": (
                    "email",
                    "full_name",
                    "system_role",
                )
            },
        ),
    )


@admin.register(CompanyMembership)
class CompanyMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "role", "joined_at")
    list_filter = ("company", "role")
    search_fields = ("user__email", "user__full_name", "company__name")
    autocomplete_fields = ("user", "company")
    readonly_fields = ("joined_at",)


@admin.register(DepartmentMembership)
class DepartmentMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "department", "role", "joined_at")
    list_filter = ("department", "role")
    search_fields = ("user__email", "user__full_name", "department__name", "department__company__name")
    autocomplete_fields = ("user", "department")
    readonly_fields = ("joined_at",)
