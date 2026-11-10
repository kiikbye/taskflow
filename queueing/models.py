from django.conf import settings
from django.db import models
from django.utils import timezone


class Batch(models.Model):
    class Mode(models.TextChoices):
        PARALLEL = "parallel", "Параллель"
        SERIAL = "serial", "Кезекпен"

    title = models.CharField("Атауы", max_length=100)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    mode = models.CharField("Режим", max_length=8, choices=Mode.choices)
    created_at = models.DateTimeField("Жасалған уақыт", auto_now_add=True)
    published_at = models.DateTimeField("Жарияланған уақыт", null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        permissions = [("publish_batch", "Can publish completed batches")]

    def __str__(self):
        return self.title


class Task(models.Model):
    class State(models.TextChoices):
        QUEUED = "queued", "Кезекте"
        RUNNING = "running", "Өңделуде"
        DONE = "done", "Дайын"
        FAILED = "failed", "Сәтсіз"

    MAX_ATTEMPTS = 3

    batch = models.ForeignKey(Batch, related_name="tasks", on_delete=models.CASCADE)
    shard = models.PositiveSmallIntegerField()
    duration = models.PositiveSmallIntegerField()
    fail_first = models.BooleanField(default=False)
    state = models.CharField(max_length=8, choices=State.choices, default=State.QUEUED)
    attempts_used = models.PositiveSmallIntegerField(default=0)
    dispatch_at = models.DateTimeField(default=timezone.now, null=True, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    result = models.BigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ("shard",)
        indexes = [
            models.Index(fields=["state", "dispatch_at"]),
            models.Index(fields=["state", "lease_until"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["batch", "shard"], name="one_task_per_shard"),
        ]

    def __str__(self):
        return f"#{self.pk} / {self.batch_id}.{self.shard}"


class Attempt(models.Model):
    class State(models.TextChoices):
        RUNNING = "running", "Өңделуде"
        DONE = "done", "Дайын"
        RETRY = "retry", "Сынақ қатесі"
        LOST = "lost", "Worker тоқтады"

    task = models.ForeignKey(Task, related_name="attempts", on_delete=models.CASCADE)
    number = models.PositiveSmallIntegerField()
    worker = models.CharField(max_length=120)
    state = models.CharField(max_length=8, choices=State.choices, default=State.RUNNING)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("number",)
        constraints = [
            models.UniqueConstraint(fields=["task", "number"], name="one_attempt_per_number"),
        ]
