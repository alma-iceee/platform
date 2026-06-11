from django.contrib import admin

from .models import (
    Project,
    ProjectMembership,
    Team,
    Workspace,
    WorkspaceAccessGrant,
    WorkspaceMembership,
    WorkspaceTeam,
    WorkspaceTeamMember,
)


class WorkspaceMembershipInline(admin.TabularInline):
    model = WorkspaceMembership
    extra = 0
    autocomplete_fields = ("team",)


class ProjectMembershipInline(admin.TabularInline):
    model = ProjectMembership
    extra = 0
    autocomplete_fields = ("team",)


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
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (WorkspaceMembershipInline, WorkspaceAccessGrantInline, WorkspaceTeamInline)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "slug", "is_active", "created_at")
    list_filter = ("workspace", "is_active")
    search_fields = ("name", "slug", "description", "workspace__name")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("workspace",)
    inlines = (ProjectMembershipInline,)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = (
        "name",
        "slug",
        "description",
        "companies__name",
        "departments__name",
        "users__email",
        "users__first_name",
        "users__last_name",
    )
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("companies", "departments", "users")
    readonly_fields = ("created_at", "updated_at")


@admin.register(WorkspaceMembership)
class WorkspaceMembershipAdmin(admin.ModelAdmin):
    list_display = ("workspace", "team", "role", "created_at")
    list_filter = ("role", "workspace")
    search_fields = ("workspace__name", "team__name")
    autocomplete_fields = ("workspace", "team")
    readonly_fields = ("created_at",)


@admin.register(WorkspaceAccessGrant)
class WorkspaceAccessGrantAdmin(admin.ModelAdmin):
    list_display = ("workspace", "subject_type", "subject", "created_at")
    list_filter = ("workspace",)
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


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(admin.ModelAdmin):
    list_display = ("project", "team", "role", "created_at")
    list_filter = ("role", "project__workspace")
    search_fields = ("project__name", "project__workspace__name", "team__name")
    autocomplete_fields = ("project", "team")
    readonly_fields = ("created_at",)
