import hashlib
import mimetypes
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from .forms import MaterialUploadForm
from .models import AuditLog, UploadedMaterial, UserProfile
from office.models import DetectedFrame, Letter, Recipient, Shelf, Notification
from office.detection import detect_frames


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_action(request, action, target_repr=""):
    AuditLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        action=action,
        target_repr=target_repr[:255],
        ip=_client_ip(request),
    )


def _user_role(user):
    if not user.is_authenticated:
        return None
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile.role


def role_required(role):
    def decorator(view_func):
        @login_required
        def _wrapped(request, *args, **kwargs):
            if _user_role(request.user) != role:
                return HttpResponseForbidden("Brak uprawnien.")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


class PortalLoginView(LoginView):
    template_name = "submissions/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request, "login", self.request.user.username)
        return response


def logout_view(request):
    if request.user.is_authenticated:
        log_action(request, "logout", request.user.username)
    auth_logout(request)
    return redirect("submissions:login")


@login_required
@require_http_methods(["GET", "POST"])
def dashboard(request):
    role = _user_role(request.user)
    if role == "admin":
        return redirect("submissions:admin_panel")

    if request.method == "POST":
        form = MaterialUploadForm(request.POST, request.FILES)
        if form.is_valid():
            material = form.save(commit=False)
            material.uploaded_by = request.user
            uploaded_file = form.cleaned_data["file"]
            material.original_name = uploaded_file.name
            material.size_bytes = uploaded_file.size
            material.mime_type = uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name)[0] or ""
            hasher = hashlib.sha256()
            for chunk in uploaded_file.chunks():
                hasher.update(chunk)
            material.sha256 = hasher.hexdigest()
            uploaded_file.seek(0)
            material.save()
            log_action(request, "upload", f"UploadedMaterial#{material.pk} {material.original_name}")
            messages.success(request, "Plik został przesłany i czeka na akceptację administratora.")
            return redirect("submissions:dashboard")
    else:
        form = MaterialUploadForm()

    materials = UploadedMaterial.objects.filter(uploaded_by=request.user)
    return render(request, "submissions/dashboard.html", {"form": form, "materials": materials})


@login_required
@require_http_methods(["GET"])
def download(request, pk):
    material = get_object_or_404(UploadedMaterial, pk=pk)
    role = _user_role(request.user)
    if role != "admin" and material.uploaded_by_id != request.user.id:
        return HttpResponseForbidden("Brak dostępu.")
    if not material.file or not default_storage.exists(material.file.name):
        raise Http404("Plik nie istnieje.")
    log_action(request, "download", f"UploadedMaterial#{material.pk}")
    return FileResponse(
        default_storage.open(material.file.name, "rb"),
        as_attachment=True,
        filename=material.original_name,
        content_type=material.mime_type or "application/octet-stream",
    )


@role_required("admin")
@require_http_methods(["GET", "POST"])
def admin_panel(request):
    if request.method == "POST":
        action = request.POST.get("action")
        pk = request.POST.get("pk")
        material = get_object_or_404(UploadedMaterial, pk=pk)
        
        if action in ["accept", "reject"]:
            material.status = "accepted" if action == "accept" else "rejected"
            material.save()
            messages.success(request, f"Materiał {material.original_name} został zmieniony na: {material.get_status_display()}.")
        return redirect("submissions:admin_panel")

    qs = UploadedMaterial.objects.select_related("uploaded_by").all().order_by("-uploaded_at")
    user_filter = request.GET.get("user", "").strip()
    type_filter = request.GET.get("type", "").strip()
    status_filter = request.GET.get("status", "").strip()
    if user_filter: qs = qs.filter(uploaded_by__username=user_filter)
    if type_filter: qs = qs.filter(material_type=type_filter)
    if status_filter: qs = qs.filter(status=status_filter)
    
    return render(request, "submissions/admin_panel.html", {
        "materials": qs,
        "user_filter": user_filter,
        "type_filter": type_filter,
        "status_filter": status_filter,
        "type_choices": UploadedMaterial.TYPE_CHOICES,
        "status_choices": UploadedMaterial.STATUS_CHOICES,
    })


# --- API dla demonstracji /omnipost/ ---
from django.http import JsonResponse

def api_materials(request):
    if request.method != "GET":
        return JsonResponse({"error": "method not allowed"}, status=405)
    qs = UploadedMaterial.objects.select_related("uploaded_by").filter(
        status="accepted"
    ).order_by("-uploaded_at")[:50]
    data = [
        {
            "id": m.pk,
            "name": m.original_name,
            "type": m.get_material_type_display(),
            "type_code": m.material_type,
            "size": m.size_bytes,
            "uploaded_at": m.uploaded_at.strftime("%Y-%m-%d %H:%M"),
            "uploaded_by": m.uploaded_by.username,
            "url": f"/omnipost-portal/download/{m.pk}/",
        }
        for m in qs
    ]
    return JsonResponse({"materials": data, "count": len(data)})


# --- Trening modelu w tle ---
from django.conf import settings

def start_training(request):
    if request.method == "POST" and request.user.is_authenticated:
        from .models import TrainingJob
        if not TrainingJob.objects.filter(status__in=["pending", "running"]).exists():
            epochs = int(request.POST.get("epochs", 10))
            TrainingJob.objects.create(started_by=request.user, epochs=epochs)
            # Uruchamiamy komendę Django w tle
            subprocess.Popen([f"{settings.BASE_DIR}/venv/bin/python", f"{settings.BASE_DIR}/manage.py", "run_training"])
            messages.success(request, "Trening został uruchomiony w tle! Wyniki pojawią się w panelu admina.")
        else:
            messages.warning(request, "Inny trening już trwa. Poczekaj na jego zakończenie.")
    return redirect("submissions:dashboard")
