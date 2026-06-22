from django.db.models import Q
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from apps.ordo.organizations.models import Department, DepartmentType

from .models import Workspace, WorkspaceAccessGrant, WorkspaceTeam
from .services import sync_department_workspaces, sync_workspace_department_teams


@receiver(post_save, sender=Workspace)
def sync_workspace_teams_after_workspace_save(sender, instance, **kwargs):
    sync_workspace_department_teams(instance)


@receiver(post_save, sender=WorkspaceAccessGrant)
def sync_workspace_teams_after_grant_save(sender, instance, **kwargs):
    if not instance.is_system_generated:
        sync_workspace_department_teams(instance.workspace)


@receiver(post_delete, sender=WorkspaceAccessGrant)
def sync_workspace_teams_after_grant_delete(sender, instance, **kwargs):
    if not instance.is_system_generated and Workspace.objects.filter(pk=instance.workspace_id).exists():
        sync_workspace_department_teams(instance.workspace)


@receiver(pre_save, sender=Department)
def remember_department_company(sender, instance, **kwargs):
    instance._previous_company_id = (
        Department.objects.filter(pk=instance.pk).values_list("company_id", flat=True).first()
        if instance.pk
        else None
    )


@receiver(post_save, sender=Department)
def sync_workspace_teams_after_department_save(sender, instance, **kwargs):
    sync_department_workspaces(
        instance,
        previous_company_id=getattr(instance, "_previous_company_id", None),
    )


@receiver(pre_delete, sender=Department)
def remember_department_workspaces(sender, instance, **kwargs):
    instance._affected_workspace_ids = list(
        Workspace.objects.filter(
            Q(company=instance.company)
            | Q(access_grants__company=instance.company)
            | Q(access_grants__department=instance)
        )
        .distinct()
        .values_list("id", flat=True)
    )


@receiver(post_delete, sender=Department)
def sync_workspace_teams_after_department_delete(sender, instance, **kwargs):
    for workspace in Workspace.objects.filter(
        id__in=getattr(instance, "_affected_workspace_ids", ())
    ):
        sync_workspace_department_teams(workspace)


@receiver(post_save, sender=DepartmentType)
def sync_team_names_after_department_type_save(sender, instance, **kwargs):
    WorkspaceTeam.objects.filter(department_type=instance).update(name=instance.name)
