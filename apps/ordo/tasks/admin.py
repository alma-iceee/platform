from django.contrib import admin

from .models import (
    Task,
    TaskAssignee,
    TaskAttachment,
    TaskBoard,
    TaskColumn,
    TaskObserver,
)


class TaskColumnInline(admin.TabularInline):
    model = TaskColumn
    extra = 0


class TaskAssigneeInline(admin.TabularInline):
    model = TaskAssignee
    extra = 0
    autocomplete_fields = ("user", "assigned_by")


class TaskObserverInline(admin.TabularInline):
    model = TaskObserver
    extra = 0
    autocomplete_fields = ("user", "added_by")


class TaskAttachmentInline(admin.TabularInline):
    model = TaskAttachment
    extra = 0
    autocomplete_fields = ("uploaded_by",)


@admin.register(TaskBoard)
class TaskBoardAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "board_type", "department", "project", "is_system")
    list_filter = ("board_type", "is_system")
    search_fields = ("name", "workspace__name", "department__name", "project__name")
    autocomplete_fields = ("workspace", "department", "project")
    inlines = (TaskColumnInline,)


@admin.register(TaskColumn)
class TaskColumnAdmin(admin.ModelAdmin):
    list_display = ("name", "board", "key", "semantic_type", "position", "is_done", "is_system")
    list_filter = ("semantic_type", "is_done", "is_system")
    search_fields = ("name", "key", "board__name", "board__workspace__name")
    autocomplete_fields = ("board",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "workspace", "board", "column", "priority", "due_date")
    list_filter = ("priority", "column__semantic_type", "column__is_done")
    search_fields = ("title", "description", "workspace__name", "board__name")
    autocomplete_fields = ("workspace", "board", "column", "created_by")
    inlines = (TaskAssigneeInline, TaskObserverInline, TaskAttachmentInline)


@admin.register(TaskAssignee)
class TaskAssigneeAdmin(admin.ModelAdmin):
    list_display = ("task", "user", "assigned_by", "created_at")
    search_fields = ("task__title", "user__email", "user__full_name")
    autocomplete_fields = ("task", "user", "assigned_by")


@admin.register(TaskObserver)
class TaskObserverAdmin(admin.ModelAdmin):
    list_display = ("task", "user", "added_by", "created_at")
    search_fields = ("task__title", "user__email", "user__full_name")
    autocomplete_fields = ("task", "user", "added_by")


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):
    list_display = ("task", "original_name", "uploaded_by", "created_at")
    search_fields = ("task__title", "original_name", "file")
    autocomplete_fields = ("task", "uploaded_by")
