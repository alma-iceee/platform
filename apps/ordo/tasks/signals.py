from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.ordo.organizations.models import Department
from apps.ordo.workspaces.models import Project, Workspace

from .models import Task, TaskDiscussion
from .services import (
    ensure_department_task_board,
    ensure_project_task_board,
    ensure_workspace_task_boards,
)


@receiver(post_save, sender=Task, dispatch_uid="tasks.create_task_discussion")
def create_task_discussion(sender, instance, created, **kwargs):
    if created:
        TaskDiscussion.objects.get_or_create(task=instance)


@receiver(post_save, sender=Workspace, dispatch_uid="tasks.create_workspace_task_boards")
def create_workspace_task_boards(sender, instance, created, **kwargs):
    if created:
        ensure_workspace_task_boards(instance)


@receiver(post_save, sender=Project, dispatch_uid="tasks.create_project_task_board")
def create_project_task_board(sender, instance, created, **kwargs):
    if created:
        ensure_project_task_board(instance)


@receiver(post_save, sender=Department, dispatch_uid="tasks.create_department_task_boards")
def create_department_task_boards(sender, instance, created, **kwargs):
    if not created:
        return

    workspaces = Workspace.objects.filter(company=instance.company)
    for workspace in workspaces:
        ensure_department_task_board(workspace, instance)
