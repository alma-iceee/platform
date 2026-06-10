from django.conf import settings
from django.db import models

from apps.ordo.organizations.models import Company, Department


class Workspace(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)

    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)

    description = models.TextField(blank=True)

    companies = models.ManyToManyField(
        Company,
        blank=True,
        related_name="workspace_teams",
    )

    departments = models.ManyToManyField(
        Department,
        blank=True,
        related_name="workspace_teams",
    )

    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="workspace_teams",
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Project(models.Model):
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="projects",
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)

    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("workspace", "slug")]

    def __str__(self):
        return f"{self.workspace} / {self.name}"


class WorkspaceMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"
        VIEWER = "viewer", "Viewer"

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="workspace_memberships",
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MEMBER,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("workspace", "team")]

    def __str__(self):
        return f"{self.team} -> {self.workspace} ({self.role})"


class ProjectMembership(models.Model):
    class Role(models.TextChoices):
        MANAGER = "manager", "Manager"
        MEMBER = "member", "Member"
        VIEWER = "viewer", "Viewer"

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="project_memberships",
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MEMBER,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("project", "team")]

    def __str__(self):
        return f"{self.team} -> {self.project} ({self.role})"