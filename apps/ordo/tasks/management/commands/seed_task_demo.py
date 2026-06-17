from django.core.management.base import BaseCommand

from apps.ordo.tasks.services import seed_demo_tasks


class Command(BaseCommand):
    help = "Create demo tasks for every existing task board."

    def handle(self, *args, **options):
        counts = seed_demo_tasks()
        self.stdout.write(
            self.style.SUCCESS(
                "Task demo data is ready: "
                f"{counts['tasks']} tasks across {counts['boards']} boards."
            )
        )
