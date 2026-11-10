from rest_framework.permissions import DjangoModelPermissions

from .models import Batch


def visible_batches(user, queryset=None):
    if queryset is None:
        queryset = Batch.objects.all()
    if not user.has_perm("queueing.view_batch"):
        return queryset.none()
    if user.has_perm("queueing.publish_batch"):
        return queryset
    if user.has_perm("queueing.change_batch"):
        return queryset.filter(owner=user)
    return queryset.filter(published_at__isnull=False)


def can_change(user, batch):
    return user.has_perm("queueing.change_batch") and (
        batch.owner_id == user.pk or user.has_perm("queueing.publish_batch")
    )


class BatchPermissions(DjangoModelPermissions):
    perms_map = {**DjangoModelPermissions.perms_map, "GET": ["%(app_label)s.view_%(model_name)s"]}

    def has_object_permission(self, request, view, obj):
        if request.method in ("PATCH", "PUT"):
            return can_change(request.user, obj)
        return visible_batches(request.user).filter(pk=obj.pk).exists()
