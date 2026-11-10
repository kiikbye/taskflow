import time

from celery import shared_task
from celery.exceptions import Reject
from django.db import OperationalError

from .models import Attempt
from .services import claim, finish, shard_sum


@shared_task(bind=True)
def process_shard(self, task_id, number):
    try:
        task = claim(task_id, number, self.request.hostname)
        if task is None:
            return
        time.sleep(task.duration)
        if task.fail_first and number == 1:
            finish(task_id, number, Attempt.State.RETRY)
        else:
            finish(task_id, number, Attempt.State.DONE, shard_sum(task.shard))
    except OperationalError as error:
        time.sleep(2)
        raise Reject("PostgreSQL unavailable", requeue=True) from error
