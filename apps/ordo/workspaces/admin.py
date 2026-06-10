from django.contrib import admin

from .models import (
    Project,
    ProjectMembership,
    Team,
    Workspace,
    WorkspaceMembership,
)


class WorkspaceMembershipInline(admin.TabularInline):
    model = WorkspaceMembership
    extra = 0
    autocomplete_fields = ("team",)


class ProjectMembershipInline(admin.TabularInline):
    model = ProjectMembership
    extra = 0
    autocomplete_fields = ("team",)


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (WorkspaceMembershipInline,)
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


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(admin.ModelAdmin):
    list_display = ("project", "team", "role", "created_at")
    list_filter = ("role", "project__workspace")
    search_fields = ("project__name", "project__workspace__name", "team__name")
    autocomplete_fields = ("project", "team")
    readonly_fields = ("created_at",)