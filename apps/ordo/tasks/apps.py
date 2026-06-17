from django.apps import AppConfig


class TasksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ordo.tasks'

    def ready(self):
        import apps.ordo.tasks.signals  # noqa: F401
