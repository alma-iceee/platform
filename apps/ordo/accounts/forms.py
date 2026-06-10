from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm

from .models import User


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Эл. почта",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": "form-control", "autofocus": True})
        self.fields["password"].widget.attrs.update({"class": "form-control"})


class EmailUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = (
            "email",
            "full_name",
            "system_role",
            "email_notifications_enabled",
            "telegram_notifications_enabled",
            "is_staff",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True

    def clean_email(self):
        email = User.normalize_email_value(self.cleaned_data["email"])
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже существует.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email
        if commit:
            user.save()
            self.save_m2m()
        return user


class EmailUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = (
            "email",
            "full_name",
            "system_role",
            "email_notifications_enabled",
            "telegram_notifications_enabled",
            "password",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
        )

    def clean_email(self):
        email = User.normalize_email_value(self.cleaned_data["email"])
        queryset = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError("Пользователь с таким email уже существует.")
        return email


class NotificationPreferencesForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("email_notifications_enabled", "telegram_notifications_enabled")
        labels = {
            "email_notifications_enabled": "Email notifications",
            "telegram_notifications_enabled": "Telegram notifications",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-check-input"
