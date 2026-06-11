from django import forms

from .models import Workspace


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
