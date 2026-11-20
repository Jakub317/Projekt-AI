from django.contrib import admin
from .models import (
    DetectionConfig, Shelf, CameraQueueItem,
    Recipient, RecipientZone, DetectedFrame, Letter, Notification
)


@admin.register(DetectionConfig)
class DetectionConfigAdmin(admin.ModelAdmin):
    list_display = ("mode", "apn_url", "updated_at")


@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "preferred_channel", "phone", "email")
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
    list_display = ("id", "shelf", "photo", "status", "diff_summary", "created_at")
    list_filter = ("status", "shelf")


@admin.register(Letter)
class LetterAdmin(admin.ModelAdmin):
    list_display = ("id", "recipient", "document_type", "status", "due_date", "created_at")
    list_filter = ("status", "recipient")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "channel", "recipient_name", "mms_image", "sent_at")
    list_filter = ("channel",)

    def recipient_name(self, obj):
        return obj.letter.recipient if obj.letter else "-"
    recipient_name.short_description = "Odbiorca"


admin.site.register(DetectedFrame)