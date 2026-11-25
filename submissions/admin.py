from django.contrib import admin
from .models import AuditLog, UploadedMaterial, UserProfile
import hashlib
import mimetypes


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "is_blocked", "created_by", "created_at")
    list_filter = ("role", "is_blocked")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at",)


@admin.register(UploadedMaterial)
class UploadedMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "original_name", "material_type", "camera_source", "status",
        "uploaded_by", "size_bytes", "uploaded_at",
    )
    list_filter = ("material_type", "camera_source", "status", "uploaded_at")
    search_fields = ("original_name", "sha256", "uploaded_by__username")
    readonly_fields = ("sha256", "size_bytes", "mime_type", "uploaded_at")
    date_hierarchy = "uploaded_at"

    # Automatyczne wyliczanie pól przy zapisie z panelu Admina
    def save_model(self, request, obj, form, change):
        if obj.file:
            if not obj.size_bytes:
                obj.size_bytes = obj.file.size
            if not obj.mime_type:
                obj.mime_type = mimetypes.guess_type(obj.file.name)[0] or "application/octet-stream"
            if not obj.sha256:
                hasher = hashlib.sha256()
                for chunk in obj.file.chunks():
                    hasher.update(chunk)
                obj.sha256 = hasher.hexdigest()
                obj.file.seek(0)
        if not obj.uploaded_by:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "target_repr", "ip")
    list_filter = ("action", "created_at")
    search_fields = ("actor__username", "action", "target_repr")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"