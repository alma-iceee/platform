from django.core.management.base import BaseCommand

from apps.ordo.tasks.services import sync_task_boards


class Command(BaseCommand):
    help = "Create missing system task boards and default columns."

    def handle(self, *args, **options):
        counts = sync_task_boards()
        self.stdout.write(
            self.style.SUCCESS(
                "Task boards synced: "
                f"{counts['workspaces']} workspaces, "
                f"{counts['projects']} projects, "
                f"{counts['departments']} department boards."
            )
        )
