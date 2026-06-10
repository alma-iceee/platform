from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.db.models.functions import Lower
from django.conf import settings
from apps.ordo.organizations.models import Company, Department

class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set.")
        email = self.model.normalize_email_value(email)
        user = self.model(email=email, username=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email=None, password=None, **extra_fields):
        email = email or extra_fields.pop("username", None)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email=None, password=None, **extra_fields):
        email = email or extra_fields.pop("username", None)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class SystemRole(models.TextChoices):
        NONE = "none", "None"
        GENERAL_DIRECTOR = "general_director", "General Director"
        CEO = "ceo", "CEO"

    username_validator = UnicodeUsernameValidator()

    username = models.CharField(
        "username",
        max_length=254,
        unique=True,
        help_text="Internal mirror of the email address.",
        validators=[username_validator],
        error_messages={
            "unique": "A user with that email already exists.",
        },
    )
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    system_role = models.CharField(
        max_length=20,
        choices=SystemRole.choices,
        default=SystemRole.NONE,
    )
    email_notifications_enabled = models.BooleanField(default=False)
    telegram_notifications_enabled = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
        ]

    @staticmethod
    def normalize_email_value(email: str) -> str:
        return email.strip().lower()

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.normalize_email_value(self.email)
            self.username = self.email
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email or self.username


class CompanyMembership(models.Model):
    class Role(models.TextChoices):
        DIRECTOR = "director", "Director"
        MEMBER = "member", "Member"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="company_memberships",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(
        max_length=50,
        choices=Role.choices,
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "company"],
                name="unique_company_membership_per_user",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.company} ({self.role})"


class DepartmentMembership(models.Model):
    class Role(models.TextChoices):
        CHIEF = "chief", "Chief"
        MEMBER = "member", "Member"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="department_memberships",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(
        max_length=50,
        choices=Role.choices,
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "department"],
                name="unique_department_membership_per_user",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.department} ({self.role})"