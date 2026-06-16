from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import resolve_url


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated or self._is_allowed_path(request.path_info):
            return self.get_response(request)

        return redirect_to_login(request.get_full_path(), resolve_url(settings.LOGIN_URL))

    def _is_allowed_path(self, path):
        login_path = resolve_url(settings.LOGIN_URL)
        allowed_prefixes = (
            login_path,
            self._path_prefix(settings.STATIC_URL),
            self._path_prefix(settings.MEDIA_URL),
        )
        return any(path.startswith(prefix) for prefix in allowed_prefixes)

    def _path_prefix(self, value):
        if not value:
            return ""
        if value.startswith("http://") or value.startswith("https://"):
            return ""
        return value if value.startswith("/") else f"/{value}"
