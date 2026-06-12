from django import forms
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from apps.ordo.organizations.models import Company, Department

from .models import Project, Workspace, WorkspaceAccessGrant, WorkspaceTeam, WorkspaceTeamMember


class DepartmentSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            department = getattr(value, "instance", None)
            if department is not None:
                option["attrs"]["data-company-id"] = str(department.company_id)
        return option


class _WorkspaceAccessGrantForm(forms.Form):
    field_name = None

    def __init__(self, *args, **kwargs):
        disabled = kwargs.pop("disabled", False)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "shell-input"})
            if disabled:
                field.disabled = True

    def save(self, workspace):
        subject = self.cleaned_data[self.field_name]
        grant, _ = WorkspaceAccessGrant.objects.get_or_create(
            workspace=workspace,
            **{self.field_name: subject},
        )
        return grant


class WorkspaceCompanyAccessGrantForm(_WorkspaceAccessGrantForm):
    field_name = "company"

    company = forms.ModelChoiceField(
        queryset=Company.objects.order_by("name"),
        empty_label="Select company",
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
        fields = ("name", "team", "description")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        self.workspace = kwargs.pop("workspace")
        self.created_by = kwargs.pop("created_by", None)
        disabled = kwargs.pop("disabled", False)
        super().__init__(*args, **kwargs)

        self.fields["team"].queryset = WorkspaceTeam.objects.filter(
            workspace=self.workspace,
            is_active=True,
        ).order_by("name")
        self.fields["team"].required = False
        self.fields["team"].empty_label = "No team assigned"
        self.fields["team"].label = "Team"

        for field_name in ("name", "team", "description"):
            self.fields[field_name].widget.attrs.update({"class": "shell-input"})
        self.fields["name"].widget.attrs["placeholder"] = "Project name"
        self.fields["name"].error_messages["required"] = "Project name cannot be empty."
        self.fields["description"].widget.attrs["placeholder"] = "Describe what this project is for"

        if disabled:
            for field in self.fields.values():
                field.disabled = True

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Project name cannot be empty.")

        duplicate = Project.objects.filter(
            workspace=self.workspace,
            slug=slugify(name, allow_unicode=True),
        )
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("A project with this name already exists in this workspace.")
        return name

    def save(self, commit=True):
        project = super().save(commit=False)
        project.workspace = self.workspace
        if project.pk is None:
            project.created_by = self.created_by
        project.slug = slugify(project.name, allow_unicode=True)
        if commit:
            project.save()
        return project


class WorkspaceTeamForm(forms.ModelForm):
    class Meta:
        model = WorkspaceTeam
        fields = ("name", "description")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        self.workspace = kwargs.pop("workspace")
        disabled = kwargs.pop("disabled", False)
        super().__init__(*args, **kwargs)

        for field_name in ("name", "description"):
            self.fields[field_name].widget.attrs.update({"class": "shell-input"})
        self.fields["name"].widget.attrs["placeholder"] = "Team name"
        self.fields["name"].error_messages["required"] = "Team name cannot be empty."
        self.fields["description"].widget.attrs["placeholder"] = "Describe how this team is used"

        if disabled:
            for field in self.fields.values():
                field.disabled = True

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Team name cannot be empty.")

        duplicate = WorkspaceTeam.objects.filter(
            workspace=self.workspace,
            slug=slugify(name, allow_unicode=True),
        )
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("A team with this name already exists in this workspace.")
        return name

    def save(self, commit=True):
        team = super().save(commit=False)
        team.workspace = self.workspace
        team.slug = slugify(team.name, allow_unicode=True)
        if commit:
            team.save()
        return team


class _WorkspaceTeamMemberForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.workspace = kwargs.pop("workspace")
        disabled = kwargs.pop("disabled", False)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "shell-input"})
            if disabled:
                field.disabled = True

    def save(self, team):
        grant = self.cleaned_data["access_grant"]
        membership, _ = WorkspaceTeamMember.objects.get_or_create(
            team=team,
            access_grant=grant,
        )
        return membership


class WorkspaceTeamCompanyMemberForm(_WorkspaceTeamMemberForm):
    company = forms.ModelChoiceField(
        queryset=Company.objects.none(),
        empty_label="Select company",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["company"].queryset = (
            Company.objects.filter(workspace_access_grants__workspace=self.workspace)
            .distinct()
            .order_by("name")
        )

    def clean(self):
        cleaned_data = super().clean()
        company = cleaned_data.get("company")
        if not company:
            return cleaned_data

        grant = WorkspaceAccessGrant.objects.filter(
            workspace=self.workspace,
            company=company,
        ).first()
        if grant is None:
            self.add_error("company", "Company must already have workspace access.")
            return cleaned_data

        cleaned_data["access_grant"] = grant
        return cleaned_data


class WorkspaceTeamDepartmentMemberForm(_WorkspaceTeamMemberForm):
    company = forms.ModelChoiceField(
        queryset=Company.objects.none(),
        empty_label="Select company",
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.none(),
        empty_label="Select department",
        widget=DepartmentSelect,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["company"].queryset = Company.objects.order_by("name")
        self.fields["department"].queryset = (
            Department.objects.filter(workspace_access_grants__workspace=self.workspace)
            .select_related("company")
            .order_by("company__name", "name")
        )
        self.fields["department"].widget.attrs["data-team-department-select"] = "true"
        self.fields["company"].widget.attrs["data-team-department-company-select"] = "true"

    def clean(self):
        cleaned_data = super().clean()
        company = cleaned_data.get("company")
        department = cleaned_data.get("department")
        if not company or not department:
            return cleaned_data

        if department.company_id != company.id:
            self.add_error("department", "Department must belong to the selected company.")
            return cleaned_data

        grant = WorkspaceAccessGrant.objects.filter(
            workspace=self.workspace,
            department=department,
        ).first()
        if grant is None:
            self.add_error("department", "Department must already have workspace access.")
            return cleaned_data

        cleaned_data["access_grant"] = grant
        return cleaned_data


class WorkspaceTeamUserMemberForm(_WorkspaceTeamMemberForm):
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

        grant = WorkspaceAccessGrant.objects.filter(
            workspace=self.workspace,
            user=user,
        ).first()
        if grant is None:
            self.add_error("email", "User must already have direct workspace access.")
            return cleaned_data

        cleaned_data["access_grant"] = grant
        return cleaned_data
