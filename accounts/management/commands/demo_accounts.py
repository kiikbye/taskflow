from getpass import getpass

from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User


class Command(BaseCommand):
    help = "Create demo_student, demo_teacher, demo_peer, demo_manager using a password entered privately."

    def handle(self, *args, **kwargs):
        password = getpass("Demo password: ")
        try:
            validate_password(password)
        except ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error
        with transaction.atomic():
            for name, role in (
                ("demo_student", "student"), ("demo_teacher", "teacher"),
                ("demo_peer", "teacher"), ("demo_manager", "manager"),
            ):
                user, created = User.objects.get_or_create(username=name)
                if not created:
                    self.stdout.write(f"{name}: already exists")
                    continue
                user.is_staff = role != "student"
                user.set_password(password)
                user.save()
                user.groups.add(Group.objects.get(name=role))
                self.stdout.write(f"{name}: {role}")
