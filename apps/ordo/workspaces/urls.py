from django.urls import path

from .views import workspace_shell


app_name = "workspaces"

urlpatterns = [
    path("", workspace_shell, name="shell"),
]
