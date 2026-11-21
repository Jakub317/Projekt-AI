from django.contrib import admin
from django.utils.html import format_html
from .models import (
    DetectionConfig, Shelf, CameraQueueItem,
    Recipient, RecipientZone, DetectedFrame, Letter, Notification
)


@admin.register(DetectionConfig)
class DetectionConfigAdmin(admin.ModelAdmin):
    list_display = ("mode", "apn_token", "updated_at")


@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    list_display = ("id", "first_name", "last_name", "preferred_channel", "phone", "email")
    list_editable = ("preferred_channel", "phone", "email")
    search_fields = ("first_name", "last_name", "phone", "email")


@admin.register(Shelf)
class ShelfAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "photo", "created_at")


@admin.register(RecipientZone)
class RecipientZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "shelf", "recipient", "x_pct", "y_pct", "w_pct", "h_pct")
    list_filter = ("shelf", "recipient")


@admin.register(CameraQueueItem)
class CameraQueueItemAdmin(admin.ModelAdmin):
    list_display = ("id", "shelf", "photo", "status", "created_at")
    list_filter = ("status", "shelf")


@admin.register(Letter)
class LetterAdmin(admin.ModelAdmin):
    list_display = ("id", "recipient", "document_type", "status", "due_date", "created_at")
    list_filter = ("status", "recipient")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "recipient_name", "mms_image_preview", "sent_at")
    list_filter = ("channel",)
    readonly_fields = ("mms_image_preview",)

    @admin.display(description="Odbiorca")
    def recipient_name(self, obj):
        letter = getattr(obj, 'letter', None)
        if letter and letter.recipient:
            return str(letter.recipient)
        return "-"

    @admin.display(description="Podgląd MMS")
    def mms_image_preview(self, obj):
        if obj.mms_image:
            url = f"/omnipost-portal/office/mms-crop/{obj.mms_image}/"
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-height: 150px; border: 1px solid #ccc; padding: 3px; background: #fff; border-radius: 4px;"/>'
                '</a>',
                url, url
            )
        return "-"


# --- SEKCJA DLA NOWYCH OPERATORÓW (SMS/MMS) ---
try:
    from .models import NotificationConfig

    @admin.register(NotificationConfig)
    class NotificationConfigAdmin(admin.ModelAdmin):
        list_display = ("id", "sms_provider", "mms_provider", "email_provider")
        list_display_links = ("id",)
        list_editable = ("sms_provider", "mms_provider", "email_provider")

        def has_add_permission(self, request):
            try:
                # Próba sprawdzenia, czy rekord istnieje
                return not NotificationConfig.objects.exists()
            except Exception:
                # Jeśli tabela jeszcze nie istnieje (przed migracją), zezwól na dodanie
                return True
except ImportError:
    pass
# ------------------------------------------------

admin.site.register(DetectedFrame)