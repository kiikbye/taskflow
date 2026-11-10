from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import User


class AdminUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


class CreateUserForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = CreateUserForm
    form = AdminUserChangeForm
    list_display = ("username", "email", "role_name", "is_staff", "is_active", "last_login")
    list_filter = ("groups", "is_staff", "is_superuser", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (("Қосымша", {"fields": ("phone",)}),)

    @admin.display(description="Рөл")
    def role_name(self, obj):
        return obj.role
