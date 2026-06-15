from django.contrib import admin

from .models import (
    Project,
    Workspace,
    WorkspaceAccessGrant,
    WorkspaceTeam,
    WorkspaceTeamMember,
)


class WorkspaceAccessGrantInline(admin.TabularInline):
    model = WorkspaceAccessGrant
    extra = 0
    autocomplete_fields = ("company", "department", "user")


class WorkspaceTeamInline(admin.TabularInline):
    model = WorkspaceTeam
    extra = 0
    prepopulated_fields = {"slug": ("name",)}


class WorkspaceTeamMemberInline(admin.TabularInline):
    model = WorkspaceTeamMember
    extra = 0
    autocomplete_fields = ("access_grant",)


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "company", "is_active", "created_at")
    list_filter = ("company", "is_active")
    search_fields = ("name", "slug", "description", "company__name")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("company",)
    inlines = (WorkspaceAccessGrantInline, WorkspaceTeamInline)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "slug", "is_active", "created_at")
    list_filter = ("workspace", "is_active")
    search_fields = (
        "name",
        "slug",
        "description",
        "workspace__name",
    )
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("workspace", "team")
    readonly_fields = ("created_at", "updated_at")


@admin.register(WorkspaceAccessGrant)
class WorkspaceAccessGrantAdmin(admin.ModelAdmin):
    list_display = ("workspace", "subject_type", "subject", "role", "created_at")
    list_filter = ("role", "workspace")
    search_fields = (
        "workspace__name",
        "company__name",
        "department__name",
        "user__email",
        "user__first_name",
        "user__last_name",
    )
    autocomplete_fields = ("workspace", "company", "department", "user")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Type")
    def subject_type(self, obj):
        if obj.company_id:
            return "Company"
        if obj.department_id:
            return "Department"
        if obj.user_id:
            return "User"
        return "-"

    @admin.display(description="Name")
    def subject(self, obj):
        return obj.subject or "-"


@admin.register(WorkspaceTeam)
class WorkspaceTeamAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "slug", "is_active", "created_at")
    list_filter = ("workspace", "is_active")
    search_fields = ("name", "slug", "description", "workspace__name")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("workspace",)
    inlines = (WorkspaceTeamMemberInline,)
    readonly_fields = ("created_at", "updated_at")


@admin.register(WorkspaceTeamMember)
class WorkspaceTeamMemberAdmin(admin.ModelAdmin):
    list_display = ("team", "access_grant", "created_at")
    list_filter = ("team__workspace",)
    search_fields = (
        "team__name",
        "team__workspace__name",
        "access_grant__workspace__name",
        "access_grant__company__name",
        "access_grant__department__name",
        "access_grant__user__email",
    )
    autocomplete_fields = ("team", "access_grant")
    readonly_fields = ("created_at",)
