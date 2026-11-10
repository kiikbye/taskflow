from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.crypto import salted_hmac


class User(AbstractUser):
    phone = models.CharField("Телефон", max_length=20, blank=True)
    session_version = models.PositiveIntegerField(default=0, editable=False)

    @property
    def role(self):
        if self.is_superuser:
            return "admin"
        groups = set(self.groups.values_list("name", flat=True))
        return next((role for role in ("manager", "teacher", "student") if role in groups), "—")

    def _get_session_auth_hash(self, secret=None):
        return salted_hmac(
            "accounts.User.session", f"{self.password}:{self.session_version}",
            secret=secret, algorithm="sha256",
        ).hexdigest()
