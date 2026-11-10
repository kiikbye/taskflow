from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q


class Command(BaseCommand):
    help = "Create or update the three lab roles."

    @transaction.atomic
    def handle(self, *args, **kwargs):
        permissions = {
            "student": ("view_batch", "view_task", "view_attempt"),
            "teacher": ("view_batch", "view_task", "view_attempt", "add_batch", "change_batch"),
            "manager": (
                "view_batch", "view_task", "view_attempt", "add_batch",
                "change_batch", "publish_batch",
            ),
        }
        for role, codenames in permissions.items():
            group, _ = Group.objects.get_or_create(name=role)
            rules = Q(content_type__app_label="queueing", codename__in=codenames)
            if role == "manager":
                rules |= Q(content_type__app_label="auth", codename="view_group")
            group.permissions.set(Permission.objects.filter(rules))
            self.stdout.write(f"{role}: {group.permissions.count()}")
