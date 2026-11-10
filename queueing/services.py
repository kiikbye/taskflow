from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Attempt, Batch, Task

LEASE = timedelta(seconds=30)


@transaction.atomic
def create_batch(*, owner, title, mode, count, duration, fail_first=False):
    batch = Batch.objects.create(owner=owner, title=title, mode=mode)
    Task.objects.bulk_create(
        Task(batch=batch, shard=shard, duration=duration, fail_first=fail_first and shard == 1)
        for shard in range(1, count + 1)
    )
    return batch


@transaction.atomic
def claim(task_id, number, worker):
    task = Task.objects.select_for_update().filter(pk=task_id).first()
    if (
        task is None or task.state != Task.State.QUEUED
        or task.dispatch_at is not None or number != task.attempts_used + 1
    ):
        return None
    task.state = Task.State.RUNNING
    task.attempts_used = number
    task.lease_until = timezone.now() + LEASE
    task.save(update_fields=["state", "attempts_used", "lease_until"])
    Attempt.objects.create(task=task, number=number, worker=worker)
    return task


def close_attempt(task, outcome, now, result=None):
    Attempt.objects.filter(task=task, number=task.attempts_used).update(
        state=outcome, finished_at=now,
    )
    task.lease_until = None
    if outcome == Attempt.State.DONE:
        task.state = Task.State.DONE
        task.result = result
    elif task.attempts_used >= Task.MAX_ATTEMPTS:
        task.state = Task.State.FAILED
    else:
        task.state = Task.State.QUEUED
        task.dispatch_at = now + timedelta(seconds=2 ** task.attempts_used)
    task.save(update_fields=["state", "lease_until", "result", "dispatch_at"])


@transaction.atomic
def finish(task_id, number, outcome, result=None):
    task = Task.objects.select_for_update().get(pk=task_id)
    now = timezone.now()
    if task.state == Task.State.RUNNING and task.attempts_used == number and task.lease_until > now:
        close_attempt(task, outcome, now, result)


@transaction.atomic
def recover_expired():
    now = timezone.now()
    expired = Task.objects.select_for_update(skip_locked=True).filter(
        state=Task.State.RUNNING, lease_until__lte=now,
    ).order_by("lease_until")[:32]
    for task in expired:
        close_attempt(task, Attempt.State.LOST, now)


@transaction.atomic
def publish_batch(batch_id):
    batch = Batch.objects.select_for_update().get(pk=batch_id)
    if not batch.tasks.exists() or batch.tasks.exclude(state=Task.State.DONE).exists():
        return False
    if not batch.published_at:
        batch.published_at = timezone.now()
        batch.save(update_fields=["published_at"])
    return True


def shard_sum(shard):
    start = (shard - 1) * 1000 + 1
    return sum(value * value for value in range(start, start + 1000))
