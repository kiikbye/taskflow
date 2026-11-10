from django.utils import timezone

from .models import Task


def snapshot(batch):
    tasks = list(batch.tasks.prefetch_related("attempts"))
    states = {state: 0 for state in Task.State.values}
    now = timezone.now()
    events = []
    rows = []
    workers = set()
    finishes = []
    retries = 0
    for task in tasks:
        states[task.state] += 1
        attempts = list(task.attempts.all())
        retries += max(0, len(attempts) - 1)
        timeline = []
        for attempt in attempts:
            workers.add(attempt.worker)
            end = attempt.finished_at or now
            if attempt.finished_at:
                finishes.append(attempt.finished_at)
            if end > attempt.started_at:
                events.extend(((attempt.started_at, 1), (end, -1)))
            timeline.append({
                "number": attempt.number, "worker": attempt.worker,
                "state": attempt.get_state_display(),
                "start": round((attempt.started_at - batch.created_at).total_seconds(), 2),
                "end": round((end - batch.created_at).total_seconds(), 2),
                "active": attempt.finished_at is None,
            })
        rows.append({
            "shard": task.shard, "state": task.state, "label": task.get_state_display(),
            "result": task.result, "attempts": timeline,
        })
    peak = active = 0
    for _, delta in sorted(events):
        active += delta
        peak = max(peak, active)
    finished = bool(tasks) and states["done"] + states["failed"] == len(tasks)
    elapsed = max(0, ((max(finishes) if finished and finishes else now) - batch.created_at).total_seconds())
    return {
        "states": states, "tasks": rows, "finished": finished, "workers": len(workers),
        "peak": peak, "elapsed": round(elapsed, 2), "retries": retries,
        "rate": round(states["done"] / elapsed, 2) if elapsed else 0,
        "result": sum(task.result for task in tasks if task.result is not None)
        if tasks and states["done"] == len(tasks) else None,
    }
