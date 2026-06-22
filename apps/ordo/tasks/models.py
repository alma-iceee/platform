from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.ordo.organizations.models import Department
from apps.ordo.workspaces.models import Project, Workspace


class TaskBoard(models.Model):
    class BoardType(models.TextChoices):
        INBOX = "inbox", "Inbox"
        WORKSPACE = "workspace", "Workspace"
        DEPARTMENT = "department", "Department"
        PROJECT = "project", "Project"

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="task_boards",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="task_boards",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="task_boards",
    )

    board_type = models.CharField(
        max_length=20,
        choices=BoardType.choices,
        default=BoardType.INBOX,
    )
    name = models.CharField(max_length=255)
    is_system = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["workspace__name", "board_type", "name"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        board_type__in=["inbox", "workspace"],
                        department__isnull=True,
                        project__isnull=True,
                    )
                    | models.Q(
                        board_type="department",
                        department__isnull=False,
                        project__isnull=True,
                    )
                    | models.Q(
                        board_type="project",
                        department__isnull=True,
                        project__isnull=False,
                    )
                ),
                name="task_board_context_matches_type",
            ),
            models.UniqueConstraint(
                fields=["workspace", "board_type"],
                condition=models.Q(board_type__in=["inbox", "workspace"]),
                name="unique_system_task_board_per_workspace_type",
            ),
            models.UniqueConstraint(
                fields=["workspace", "department"],
                condition=models.Q(board_type="department", department__isnull=False),
                name="unique_department_task_board_per_workspace",
            ),
            models.UniqueConstraint(
                fields=["workspace", "project"],
                condition=models.Q(board_type="project", project__isnull=False),
                name="unique_project_task_board_per_workspace",
            ),
        ]

    def clean(self):
        if self.board_type in {self.BoardType.INBOX, self.BoardType.WORKSPACE}:
            if self.department_id or self.project_id:
                raise ValidationError(
                    "Inbox and workspace task boards cannot be linked to a department or project."
                )

        if self.board_type == self.BoardType.DEPARTMENT:
            if not self.department_id:
                raise ValidationError("Department task boards must be linked to a department.")
            if self.project_id:
                raise ValidationError("Department task boards cannot be linked to a project.")
            if (
                self.workspace_id
                and self.workspace.company_id
                and self.department.company_id != self.workspace.company_id
            ):
                raise ValidationError(
                    "Department task board must belong to the workspace company."
                )

        if self.board_type == self.BoardType.PROJECT:
            if not self.project_id:
                raise ValidationError("Project task boards must be linked to a project.")
            if self.department_id:
                raise ValidationError("Project task boards cannot be linked to a department.")
            if self.workspace_id and self.project.workspace_id != self.workspace_id:
                raise ValidationError("Project task board must belong to the project workspace.")

    def __str__(self):
        return f"{self.workspace} / {self.name}"


class TaskColumn(models.Model):
    class SemanticType(models.TextChoices):
        TODO = "todo", "To do"
        ACTIVE = "active", "Active"
        REVIEW = "review", "Review"
        BLOCKED = "blocked", "Blocked"
        DONE = "done", "Done"
        CANCELED = "canceled", "Canceled"

    board = models.ForeignKey(
        TaskBoard,
        on_delete=models.CASCADE,
        related_name="columns",
    )

    name = models.CharField(max_length=255)
    key = models.SlugField(max_length=80)
    semantic_type = models.CharField(
        max_length=20,
        choices=SemanticType.choices,
        default=SemanticType.TODO,
    )
    position = models.PositiveIntegerField(default=0)
    is_done = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["board", "position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["board", "key"],
                name="unique_task_column_key_per_board",
            ),
        ]

    def __str__(self):
        return f"{self.board} / {self.name}"


class Task(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    board = models.ForeignKey(
        TaskBoard,
        on_delete=models.PROTECT,
        related_name="tasks",
    )
    column = models.ForeignKey(
        TaskColumn,
        on_delete=models.PROTECT,
        related_name="tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tasks",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    due_date = models.DateField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["workspace__name", "board", "column", "position", "id"]
        indexes = [
            models.Index(fields=["workspace", "board", "column"]),
            models.Index(fields=["workspace", "priority"]),
            models.Index(fields=["workspace", "due_date"]),
        ]

    def clean(self):
        if self.workspace_id and self.board_id and self.board.workspace_id != self.workspace_id:
            raise ValidationError({"board": "Task board must belong to the task workspace."})
        if self.board_id and self.column_id and self.column.board_id != self.board_id:
            raise ValidationError({"column": "Task column must belong to the task board."})

    def __str__(self):
        return self.title


class TaskAssignee(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="assignees",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="task_assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_task_users",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["task", "user"],
                name="unique_task_assignee",
            ),
        ]

    def __str__(self):
        return f"{self.user} -> {self.task}"


class TaskObserver(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="observers",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="observed_tasks",
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="added_task_observers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["task", "user"],
                name="unique_task_observer",
            ),
        ]

    def __str__(self):
        return f"{self.user} watches {self.task}"


class TaskComment(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="task_comments",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["task", "created_at", "id"]
        indexes = [models.Index(fields=["task", "created_at"])]

    def __str__(self):
        return f"Comment #{self.pk} on {self.task}"


class TaskCommentAttachment(models.Model):
    comment = models.ForeignKey(
        TaskComment,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="tasks/comments/%Y/%m/%d/")
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_task_comment_attachments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["comment", "created_at", "id"]

    def __str__(self):
        return self.original_name or self.file.name


class TaskDiscussion(models.Model):
    task = models.OneToOneField(
        Task,
        on_delete=models.CASCADE,
        related_name="discussion",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Discussion for {self.task}"


class TaskDiscussionMessage(models.Model):
    discussion = models.ForeignKey(
        TaskDiscussion,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="task_discussion_messages",
    )
    body = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["discussion", "created_at", "id"]
        indexes = [models.Index(fields=["discussion", "created_at"])]

    def __str__(self):
        return f"Message #{self.pk} in {self.discussion}"


class TaskDiscussionMessageAttachment(models.Model):
    message = models.ForeignKey(
        TaskDiscussionMessage,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="tasks/discussions/%Y/%m/%d/")
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_task_discussion_attachments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["message", "created_at", "id"]

    def __str__(self):
        return self.original_name or self.file.name


class TaskAttachment(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="tasks/attachments/%Y/%m/%d/")
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_task_attachments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["task", "-created_at", "id"]

    def __str__(self):
        return self.original_name or self.file.name
