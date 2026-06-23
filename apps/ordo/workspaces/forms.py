from django import forms
from django.contrib.auth import get_user_model

from apps.ordo.accounts.models import CompanyMembership, DepartmentMembership
from apps.ordo.organizations.models import Company, Department

from .models import Project, Workspace, WorkspaceAccessGrant, WorkspaceTeam
from .slugs import unique_project_slug, unique_workspace_slug


class DepartmentSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            department = getattr(value, "instance", None)
            if department is not None:
                option["attrs"]["data-company-id"] = str(department.company_id)
        return option


class WorkspaceForm(forms.ModelForm):
    class Meta:
        model = Workspace
        fields = ("name", "description")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update(
            {
                "class": "shell-input",
                "placeholder": "Workspace name",
            }
        )
        self.fields["name"].error_messages["required"] = "Workspace name cannot be empty."
        self.fields["description"].widget.attrs.update(
            {
                "class": "shell-input",
                "placeholder": "Describe what this workspace is for",
            }
        )

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Workspace name cannot be empty.")
        return name

    def save(self, commit=True):
        workspace = super().save(commit=False)
        workspace.slug = unique_workspace_slug(workspace.name)
        if commit:
            workspace.save()
        return workspace


class _WorkspaceAccessGrantForm(forms.Form):
    field_name = None

    def __init__(self, *args, **kwargs):
        self.workspace = kwargs.pop("workspace", None)
        disabled = kwargs.pop("disabled", False)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "shell-input"})
            if disabled:
                field.disabled = True
        if self.workspace is not None:
            self.apply_workspace_scope()

    def apply_workspace_scope(self):
        """Hook for subclasses to narrow their choices to subjects that can still
        be granted access — i.e. exclude anything already covered by an existing
        grant (directly, or via a broader company/department grant)."""

    def save(self, workspace):
        subject = self.cleaned_data[self.field_name]
        grant, created = WorkspaceAccessGrant.objects.get_or_create(
            workspace=workspace,
            **{self.field_name: subject},
        )
        if not created and grant.is_system_generated:
            grant.is_system_generated = False
            grant.save(update_fields=["is_system_generated"])
        return grant


class WorkspaceCompanyAccessGrantForm(_WorkspaceAccessGrantForm):
    field_name = "company"

    company = forms.ModelChoiceField(
        queryset=Company.objects.order_by("name"),
        empty_label="Select company",
    )

    def apply_workspace_scope(self):
        granted_company_ids = WorkspaceAccessGrant.objects.filter(
            workspace=self.workspace,
            company__isnull=False,
        ).values_list("company_id", flat=True)
        self.fields["company"].queryset = (
            Company.objects.exclude(id__in=granted_company_ids).order_by("name")
        )


class WorkspaceDepartmentAccessGrantForm(_WorkspaceAccessGrantForm):
    field_name = "department"

    company = forms.ModelChoiceField(
        queryset=Company.objects.order_by("name"),
        empty_label="Select company",
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.select_related("company").order_by("company__name", "name"),
        empty_label="Select department",
        widget=DepartmentSelect,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].widget.attrs["data-department-select"] = "true"
        self.fields["company"].widget.attrs["data-department-company-select"] = "true"
        # Company is already chosen in the sibling select, so show only the name.
        self.fields["department"].label_from_instance = lambda department: department.name

    def apply_workspace_scope(self):
        # A company-level grant already covers all of its departments, so those
        # departments (and the company itself) drop out of the picker. Likewise
        # any department that is already granted directly drops out.
        company_grant_company_ids = WorkspaceAccessGrant.objects.filter(
            workspace=self.workspace,
            company__isnull=False,
        ).values_list("company_id", flat=True)
        granted_department_ids = WorkspaceAccessGrant.objects.filter(
            workspace=self.workspace,
            department__isnull=False,
        ).values_list("department_id", flat=True)

        self.fields["department"].queryset = (
            Department.objects.select_related("company")
            .exclude(company_id__in=company_grant_company_ids)
            .exclude(id__in=granted_department_ids)
            .order_by("company__name", "name")
        )
        # A company that already has a company-level grant has all of its
        # departments covered, so it drops out of the company picker too.
        self.fields["company"].queryset = (
            Company.objects.exclude(id__in=company_grant_company_ids).order_by("name")
        )

    def clean(self):
        cleaned_data = super().clean()
        company = cleaned_data.get("company")
        department = cleaned_data.get("department")
        if company and department and department.company_id != company.id:
            self.add_error("department", "Department must belong to the selected company.")
        return cleaned_data


class WorkspaceUserAccessGrantForm(_WorkspaceAccessGrantForm):
    field_name = "user"

    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "placeholder": "name@example.com",
                "autocomplete": "email",
            }
        )
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        if not email:
            return cleaned_data

        user = get_user_model().objects.filter(email__iexact=email).first()
        if user is None:
            self.add_error("email", "No user found with this email.")
            return cleaned_data

        if self.workspace is not None:
            if WorkspaceAccessGrant.objects.filter(workspace=self.workspace, user=user).exists():
                self.add_error("email", "This user already has workspace access.")
                return cleaned_data

            company_grant_company_ids = WorkspaceAccessGrant.objects.filter(
                workspace=self.workspace,
                company__isnull=False,
            ).values_list("company_id", flat=True)
            if CompanyMembership.objects.filter(
                user=user,
                company_id__in=company_grant_company_ids,
            ).exists():
                self.add_error("email", "This user is already covered by their company's access.")
                return cleaned_data

            department_grant_ids = WorkspaceAccessGrant.objects.filter(
                workspace=self.workspace,
                department__isnull=False,
            ).values_list("department_id", flat=True)
            if DepartmentMembership.objects.filter(
                user=user,
                department_id__in=department_grant_ids,
            ).exists():
                self.add_error("email", "This user is already covered by their department's access.")
                return cleaned_data

        cleaned_data["user"] = user
        return cleaned_data


class WorkspaceGeneralForm(forms.ModelForm):
    class Meta:
        model = Workspace
        fields = ("name",)

    def __init__(self, *args, **kwargs):
        disabled = kwargs.pop("disabled", False)
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update(
            {
                "class": "shell-input",
                "placeholder": "Workspace name",
            }
        )
        if disabled:
            self.fields["name"].disabled = True


class WorkspaceProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ("name", "description")
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "shell-input",
                    "placeholder": "Project name",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "shell-input",
                    "placeholder": "Describe what this project is for",
                    "rows": 4,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.workspace = kwargs.pop("workspace")
        self.created_by = kwargs.pop("created_by", None)
        disabled = kwargs.pop("disabled", False)
        super().__init__(*args, **kwargs)

        self.fields["name"].error_messages["required"] = "Project name cannot be empty."

        if disabled:
            for field in self.fields.values():
                field.disabled = True

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Project name cannot be empty.")
        return name

    def save(self, commit=True):
        project = super().save(commit=False)
        project.workspace = self.workspace
        if project.pk is None:
            project.created_by = self.created_by
        project.slug = unique_project_slug(
            project.name,
            self.workspace,
            exclude_pk=project.pk,
        )
        if commit:
            project.save()
        return project


class WorkspaceProjectTeamForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ("team",)
        widgets = {
            "team": forms.Select(attrs={"class": "shell-input"}),
        }

    def __init__(self, *args, **kwargs):
        self.workspace = kwargs.pop("workspace")
        disabled = kwargs.pop("disabled", False)
        super().__init__(*args, **kwargs)

        self.fields["team"].queryset = WorkspaceTeam.objects.filter(
            workspace=self.workspace,
            is_active=True,
        ).order_by("name")
        self.fields["team"].required = False
        self.fields["team"].empty_label = "No team assigned"
        self.fields["team"].label = "Team"
        # Show only the team name in the picker; the model __str__ prefixes the
        # workspace name ("Workspace / Team"), which reads like a duplicated title.
        self.fields["team"].label_from_instance = lambda team: team.name

        if disabled:
            self.fields["team"].disabled = True
