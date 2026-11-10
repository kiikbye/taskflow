from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.test import Client, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .management.commands.dispatch_tasks import dispatch_pending
from .models import Attempt, Batch, Task
from .services import claim, create_batch, finish, recover_expired, shard_sum

User = get_user_model()
PASSWORD = "Sample+Key-5208!"
INPUT = {"title": "Demo", "count": 3, "duration": 1, "mode": "parallel"}


class LabTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles", verbosity=0)
        for role in ("student", "teacher", "manager"):
            user = User.objects.create_user(role, password=PASSWORD, is_staff=role != "student")
            user.groups.add(role_group(role))
            setattr(cls, role, user)
        cls.batch = create_batch(owner=cls.teacher, **INPUT)
        cls.peer = User.objects.create_user("peer", password=PASSWORD, is_staff=True)
        cls.peer.groups.add(role_group("teacher"))

    def test_anonymous_redirect_and_api_401(self):
        self.assertRedirects(self.client.get("/"), "/login/?next=/")
        self.assertEqual(self.client.get("/api/batches/").status_code, 401)

    def test_signup_hash_and_student_role(self):
        response = self.client.post("/signup/", {
            "username": "new_reader", "password1": PASSWORD, "password2": PASSWORD,
        })
        self.assertRedirects(response, "/")
        user = User.objects.get(username="new_reader")
        self.assertEqual(user.role, "student")
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(Session.objects.count(), 0)
        self.assertEqual(self.client.get("/profile/").status_code, 200)

    def test_weak_password_rejected(self):
        self.client.post("/signup/", {"username": "weak", "password1": "12345678", "password2": "12345678"})
        self.assertFalse(User.objects.filter(username="weak").exists())

    def test_all_browser_sessions_revoked(self):
        other = Client()
        self.client.force_login(self.teacher)
        other.force_login(self.teacher)
        self.assertEqual(other.get("/profile/").status_code, 200)
        self.assertRedirects(self.client.post("/profile/logout-all/"), "/login/")
        self.assertRedirects(other.get("/profile/"), "/login/?next=/profile/")

    def test_browser_roles_owner_and_publication(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.post("/batches/new/", INPUT).status_code, 403)
        self.assertEqual(self.client.get(f"/?batch={self.batch.pk}").status_code, 404)
        self.client.force_login(self.peer)
        self.assertEqual(self.client.post(f"/batches/{self.batch.pk}/rename/", {"title": "Foreign"}).status_code, 403)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.post(f"/batches/{self.batch.pk}/rename/", {"title": "Own"}).status_code, 302)
        self.assertEqual(self.client.post(f"/batches/{self.batch.pk}/publish/").status_code, 403)
        self.client.force_login(self.manager)
        self.client.post(f"/batches/{self.batch.pk}/publish/")
        self.batch.refresh_from_db()
        self.assertIsNone(self.batch.published_at)
        self.batch.tasks.update(state=Task.State.DONE, result=1)
        self.client.post(f"/batches/{self.batch.pk}/publish/")
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(f"/?batch={self.batch.pk}").status_code, 200)

    def test_admin_queryset_limits_teacher_and_manager(self):
        other = create_batch(owner=self.peer, **{**INPUT, "title": "UniquePeerBatch"})
        self.client.force_login(self.teacher)
        listing = self.client.get("/admin/queueing/batch/")
        self.assertContains(listing, self.batch.title)
        self.assertNotContains(listing, other.title)
        self.client.force_login(self.manager)
        self.assertContains(self.client.get("/admin/queueing/batch/"), other.title)
        self.assertEqual(self.client.get("/admin/auth/group/").status_code, 200)
        admin = User.objects.create_superuser("site_admin", password=PASSWORD)
        self.client.force_login(admin)
        self.assertEqual(self.client.get("/admin/accounts/user/add/").status_code, 200)

    def test_drf_token_200_and_403(self):
        client = APIClient()
        token = client.post("/api/token/", {"username": "student", "password": PASSWORD}).data["token"]
        client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(client.get("/api/me/").data["auth"], "TokenAuthentication")
        self.assertEqual(client.get("/api/batches/").status_code, 200)
        self.assertEqual(client.post("/api/batches/", INPUT, format="json").status_code, 403)

    def test_jwt_create_and_object_403(self):
        client = APIClient()
        pair = client.post("/api/jwt/", {"username": "peer", "password": PASSWORD}).data
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {pair['access']}")
        self.assertEqual(client.get("/api/me/").data["auth"], "JWTAuthentication")
        self.assertEqual(client.post("/api/batches/", INPUT, format="json").status_code, 201)
        self.assertEqual(client.patch(f"/api/batches/{self.batch.pk}/", {"title": "Foreign"}).status_code, 403)
        client.credentials()
        self.assertEqual(client.post("/api/jwt/refresh/", {"refresh": pair["refresh"]}).status_code, 200)
        self.assertEqual(client.post("/api/jwt/logout/", {"refresh": pair["refresh"]}).status_code, 200)
        self.assertEqual(client.post("/api/jwt/refresh/", {"refresh": pair["refresh"]}).status_code, 401)


class QueueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("owner", password=PASSWORD)

    def test_outbox_remains_pending_when_broker_fails(self):
        batch = create_batch(owner=self.owner, **INPUT)
        with patch("queueing.management.commands.dispatch_tasks.process_shard.apply_async", side_effect=OSError):
            with self.assertRaises(OSError):
                dispatch_pending()
        self.assertEqual(batch.tasks.filter(dispatch_at__isnull=False).count(), 3)

    def test_duplicate_and_expired_attempt_cannot_overwrite_result(self):
        batch = create_batch(owner=self.owner, **INPUT)
        task = batch.tasks.first()
        batch.tasks.update(dispatch_at=None)
        self.assertIsNotNone(claim(task.pk, 1, "worker-a"))
        self.assertIsNone(claim(task.pk, 1, "worker-b"))
        Task.objects.filter(pk=task.pk).update(lease_until=timezone.now() - timedelta(seconds=1))
        recover_expired()
        self.assertEqual(task.attempts.get(number=1).state, Attempt.State.LOST)
        self.assertIsNone(claim(task.pk, 2, "worker-b"))
        Task.objects.filter(pk=task.pk).update(dispatch_at=None)
        self.assertIsNone(claim(task.pk, 1, "worker-a"))
        self.assertIsNotNone(claim(task.pk, 2, "worker-b"))
        finish(task.pk, 1, Attempt.State.DONE, 99)
        finish(task.pk, 2, Attempt.State.DONE, shard_sum(1))
        finish(task.pk, 2, Attempt.State.DONE, 99)
        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.DONE)
        self.assertEqual(task.result, 333833500)
        self.assertEqual(task.attempts.count(), 2)


def role_group(role):
    from django.contrib.auth.models import Group
    return Group.objects.get(name=role)
