from django.conf import settings
from django.core.exceptions import ValidationError
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


class WorkspaceAccessGrant(models.Model):
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="access_grants",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="workspace_access_grants",
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="workspace_access_grants",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="workspace_access_grants",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["workspace__name", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(company__isnull=False, department__isnull=True, user__isnull=True)
                    | models.Q(company__isnull=True, department__isnull=False, user__isnull=True)
                    | models.Q(company__isnull=True, department__isnull=True, user__isnull=False)
                ),
                name="workspace_access_grant_exactly_one_subject",
            ),
            models.UniqueConstraint(
                fields=["workspace", "company"],
                condition=models.Q(company__isnull=False),
                name="unique_workspace_access_company",
            ),
            models.UniqueConstraint(
                fields=["workspace", "department"],
                condition=models.Q(department__isnull=False),
                name="unique_workspace_access_department",
            ),
            models.UniqueConstraint(
                fields=["workspace", "user"],
                condition=models.Q(user__isnull=False),
                name="unique_workspace_access_user",
            ),
        ]

    def clean(self):
        subjects = [self.company_id, self.department_id, self.user_id]
        if sum(subject is not None for subject in subjects) != 1:
            raise ValidationError("Exactly one of company, department, or user must be set.")

    @property
    def subject(self):
        return self.company or self.department or self.user

    def __str__(self):
        return f"{self.subject} -> {self.workspace}"


class WorkspaceTeam(models.Model):
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name="workspace_teams",
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)

    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["workspace__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "slug"],
                name="unique_workspace_team_slug",
            ),
        ]

    def __str__(self):
        return f"{self.workspace} / {self.name}"


class WorkspaceTeamMember(models.Model):
    team = models.ForeignKey(
        WorkspaceTeam,
        on_delete=models.CASCADE,
        related_name="members",
    )

    access_grant = models.ForeignKey(
        WorkspaceAccessGrant,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["team", "access_grant"],
                name="unique_workspace_team_member_grant",
            ),
        ]

    def __str__(self):
        return f"{self.access_grant} -> {self.team}"


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
