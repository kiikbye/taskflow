import time

from celery import current_app
from django.core.management.base import BaseCommand
from django.db import close_old_connections, transaction
from django.utils import timezone

from queueing.models import Task
from queueing.services import recover_expired
from queueing.tasks import process_shard


@transaction.atomic
def dispatch_pending():
    tasks = list(Task.objects.select_for_update(skip_locked=True, of=("self",))
                 .select_related("batch").filter(
                     state=Task.State.QUEUED, dispatch_at__lte=timezone.now(),
                 ).order_by("dispatch_at", "pk")[:24])
    if not tasks:
        return
    with current_app.producer_or_acquire() as producer:
        for task in tasks:
            process_shard.apply_async(
                args=(task.pk, task.attempts_used + 1),
                queue=task.batch.mode,
                producer=producer,
                retry=False,
                confirm_timeout=4,
            )
            task.dispatch_at = None
        Task.objects.bulk_update(tasks, ["dispatch_at"])


class Command(BaseCommand):
    help = "Publish durable pending tasks and reclaim expired execution leases."

    def handle(self, *args, **kwargs):
        self.stdout.write("TaskFlow dispatcher ready")
        while True:
            try:
                close_old_connections()
                recover_expired()
                dispatch_pending()
            except Exception as error:
                self.stderr.write(f"Dispatch loop: {type(error).__name__}")
                time.sleep(3)
            time.sleep(0.5)
