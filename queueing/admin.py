from django.contrib import admin, messages

from .models import Attempt, Batch, Task
from .permissions import can_change, visible_batches
from .services import publish_batch


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "mode", "created_at", "published_at")
    list_filter = ("mode", "published_at")
    readonly_fields = ("owner", "mode", "created_at", "published_at")
    actions = ("publish_results",)

    def get_queryset(self, request):
        return visible_batches(request.user, super().get_queryset(request))

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return can_change(request.user, obj) if obj else super().has_change_permission(request)

    def has_publish_permission(self, request):
        return request.user.has_perm("queueing.publish_batch")

    @admin.action(description="Дайын нәтижелерді жариялау", permissions=["publish"])
    def publish_results(self, request, queryset):
        published = sum(publish_batch(batch.pk) for batch in queryset)
        self.message_user(request, f"Жарияланды: {published}", messages.SUCCESS)


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Task)
class TaskAdmin(ReadOnlyAdmin):
    list_display = ("id", "batch", "shard", "state", "attempts_used", "result")
    list_filter = ("state",)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(batch__in=visible_batches(request.user))


@admin.register(Attempt)
class AttemptAdmin(ReadOnlyAdmin):
    list_display = ("task", "number", "worker", "state", "started_at", "finished_at")
    list_filter = ("state", "worker")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(task__batch__in=visible_batches(request.user))
