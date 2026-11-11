from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    ROLE_CHOICES = [("student", "Student"), ("admin", "Administrator")]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default="student")
    is_blocked = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="created_profiles",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class UploadedMaterial(models.Model):
    TYPE_CHOICES = [
        ("photo", "Zdjęcie półki"),
        ("code", "Kod źródłowy"),
        ("archive", "Archiwum ZIP"),
        ("model", "Model ML"),
        ("dataset", "Zbiór danych (ZIP)"),
        ("other", "Inne"),
    ]
    STATUS_CHOICES = [
        ("pending", "Oczekuje"),
        ("accepted", "Zaakceptowany"),
        ("rejected", "Odrzucony"),
    ]

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="materials"
    )
    file = models.FileField(upload_to="uploads/%Y/%m/")
    original_name = models.CharField(max_length=255)
    material_type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    mime_type = models.CharField(max_length=128, blank=True)
    size_bytes = models.BigIntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    note = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["uploaded_by", "material_type"]),
            models.Index(fields=["status", "-uploaded_at"]),
        ]

    def __str__(self):
        return f"{self.original_name} ({self.material_type}, {self.uploaded_by})"


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="audit_entries",
    )
    action = models.CharField(max_length=64)
    target_repr = models.CharField(max_length=255, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor} {self.action}"

class TrainingJob(models.Model):
    STATUS_CHOICES = [
        ("pending", "Oczekuje"),
        ("running", "W trakcie treningu"),
        ("completed", "Zakończony"),
        ("failed", "Błąd"),
    ]
    started_by = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    epochs = models.IntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    log_output = models.TextField(blank=True)
    result_file = models.ForeignKey(UploadedMaterial, null=True, blank=True, on_delete=models.SET_NULL)
