"""
URL configuration for config project.
"""

from django.contrib import admin
from django.urls import include, path
from apps.ordo.workspaces.views import workspace_shell

urlpatterns = [
    path("workspaces/", include("apps.ordo.workspaces.urls")),
    path("app/", workspace_shell, name="workspace-shell-app"),
    path('admin/', admin.site.urls),
]
