from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import F
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import SignupForm
from .models import User


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            user.groups.add(Group.objects.get(name="student"))
        login(request, user)
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


@login_required
def profile(request):
    request.session["visits"] = request.session.get("visits", 0) + 1
    return render(request, "profile.html", {
        "visits": request.session["visits"],
        "expires": request.session.get_expiry_date(),
        "permissions": sorted(request.user.get_all_permissions()),
    })


@login_required
@require_POST
def logout_everywhere(request):
    User.objects.filter(pk=request.user.pk).update(session_version=F("session_version") + 1)
    logout(request)
    return redirect("login")
