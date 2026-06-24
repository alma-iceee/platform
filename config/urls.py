"""
URL configuration for config project.
"""

from django.contrib import admin
from django.urls import include, path

from .views import health

urlpatterns = [
    path("health/", health, name="health"),
    path("accounts/", include("apps.ordo.accounts.urls")),
    path('admin/', admin.site.urls),
    path("", include("apps.ordo.workspaces.urls")),
]
