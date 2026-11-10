from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import BatchForm, RenameForm
from .models import Batch
from .permissions import can_change, visible_batches
from .services import create_batch, publish_batch


@login_required
@permission_required("queueing.view_batch", raise_exception=True)
def dashboard(request):
    batches = visible_batches(request.user).select_related("owner")
    selected = request.GET.get("batch")
    batch = get_object_or_404(batches, pk=selected) if selected and selected.isdigit() and len(selected) <= 18 else batches.first()
    return render(request, "dashboard.html", {
        "batches": batches[:12], "batch": batch, "form": BatchForm(),
        "rename": RenameForm(instance=batch) if batch and can_change(request.user, batch) else None,
    })


@login_required
@permission_required("queueing.add_batch", raise_exception=True)
def new_batch(request):
    form = BatchForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        batch = create_batch(owner=request.user, **form.cleaned_data)
        return redirect(f"/?batch={batch.pk}")
    return render(request, "new_batch.html", {"form": form})


@login_required
@permission_required("queueing.change_batch", raise_exception=True)
@require_POST
def rename_batch(request, pk):
    batch = get_object_or_404(Batch, pk=pk)
    if not can_change(request.user, batch):
        raise PermissionDenied
    form = RenameForm(request.POST, instance=batch)
    if form.is_valid():
        batch.title = form.cleaned_data["title"]
        batch.save(update_fields=["title"])
    else:
        messages.error(request, "Атауы 1–100 таңбадан тұруы керек.")
    return redirect(f"/?batch={pk}")


@login_required
@permission_required("queueing.publish_batch", raise_exception=True)
@require_POST
def publish(request, pk):
    batch = get_object_or_404(Batch, pk=pk)
    if publish_batch(batch.pk):
        messages.success(request, "Нәтиже жарияланды. Оны student рөлі де көре алады.")
    else:
        messages.error(request, "Барлық тапсырма сәтті аяқталған соң жариялауға болады.")
    return redirect(f"/?batch={pk}")
