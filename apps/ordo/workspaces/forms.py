from django import forms
from django.contrib.auth import get_user_model

from apps.ordo.organizations.models import Company, Department

from .models import Workspace, WorkspaceAccessGrant


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
