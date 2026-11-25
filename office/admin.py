from django.contrib import admin
from django.shortcuts import render
from django.utils.html import format_html
from django.utils import timezone
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
    list_display = ("name", "slot_number", "shelf", "recipient", "x_pct", "y_pct", "w_pct", "h_pct")
    list_display_links = ("name",)
    list_filter = ("shelf", "recipient", "slot_number")
    list_editable = ("slot_number", "recipient")
    search_fields = ("name", "recipient__first_name", "recipient__last_name")
    ordering = ("shelf", "slot_number")
    
    fieldsets = (
        ('Identyfikacja strefy', {
            'fields': ('slot_number', 'name', 'shelf', 'recipient'),
            'description': 'slot_number to numer przegródki na półce (np. 1-14). Może się powtarzać - jeden pracownik może mieć wiele stref.'
        }),
        ('Geometria (współrzędne %)', {
            'fields': ('x_pct', 'y_pct', 'w_pct', 'h_pct'),
            'classes': ('collapse',)
        }),
    )


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
                return not NotificationConfig.objects.exists()
            except Exception:
                return True
except ImportError:
    pass
# ------------------------------------------------

admin.site.register(DetectedFrame)

from .models import ChaosReport

@admin.register(ChaosReport)
class ChaosReportAdmin(admin.ModelAdmin):
    list_display = ['shelf', 'report_type', 'object_type', 'status', 'created_at', 'reviewed_by']
    list_filter = ['status', 'report_type', 'created_at']
    search_fields = ['shelf__name', 'object_type', 'notes']
    readonly_fields = ['created_at', 'reviewed_at']
    list_editable = ['status']
    
    fieldsets = (
        ('Informacje podstawowe', {
            'fields': ('shelf', 'zone', 'report_type', 'object_type', 'confidence', 'status')
        }),
        ('Dokumentacja', {
            'fields': ('image_path', 'notes', 'reviewed_by', 'reviewed_at')
        }),
        ('Metadane', {
            'fields': ('reported_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if obj.status in ['reviewed', 'resolved', 'rejected'] and not obj.reviewed_by:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)


# ===== NOWE MODELE - PORZADEK GRECKI =====
from .models import Administrator, PileScan, PileArchiveEntry, ArchiveConfig


@admin.register(Administrator)
class AdministratorAdmin(admin.ModelAdmin):
    list_display = ['last_name', 'first_name', 'email', 'phone', 'preferred_channel', 'is_active', 'created_at']
    list_filter = ['preferred_channel', 'is_active', 'created_at']
    search_fields = ['first_name', 'last_name', 'email', 'phone']
    list_editable = ['is_active']
    fieldsets = (
        ('Dane osobowe', {
            'fields': ('first_name', 'last_name')
        }),
        ('Kontakt', {
            'fields': ('email', 'phone')
        }),
        ('Powiadomienia', {
            'fields': ('preferred_channel', 'is_active')
        }),
    )


@admin.register(PileScan)
class PileScanAdmin(admin.ModelAdmin):
    list_display = ['id', 'recipient', 'sender', 'tracking_number', 'document_type', 'document_date', 'detected_at', 'confidence']
    list_filter = ['document_type', 'detected_at', 'recipient']
    search_fields = ['sender', 'tracking_number', 'document_type', 'raw_ocr_text', 'recipient__first_name', 'recipient__last_name']
    readonly_fields = ['detected_at']
    date_hierarchy = 'detected_at'
    fieldsets = (
        ('Odczytane dane (OCR)', {
            'fields': ('recipient', 'sender', 'tracking_number', 'document_type', 'document_date')
        }),
        ('Metadane', {
            'fields': ('detected_at', 'confidence', 'image_path')
        }),
        ('Surowy tekst OCR', {
            'fields': ('raw_ocr_text',),
            'classes': ('collapse',)
        }),
    )


@admin.register(PileArchiveEntry)
class PileArchiveEntryAdmin(admin.ModelAdmin):
    list_display = ['scan', 'change_type', 'timestamp', 'description_short']
    list_filter = ['change_type', 'timestamp']
    search_fields = ['description', 'scan__id']
    readonly_fields = ['timestamp']
    
    def description_short(self, obj):
        return obj.description[:100] + '...' if len(obj.description) > 100 else obj.description
    description_short.short_description = 'Opis'


@admin.register(ArchiveConfig)
class ArchiveConfigAdmin(admin.ModelAdmin):
    list_display = ['retention_days', 'auto_cleanup', 'last_updated']
    fieldsets = (
        ('Konfiguracja archiwum', {
            'fields': ('retention_days', 'auto_cleanup'),
            'description': 'Ustawienia okresu przechowywania archiwum zmian w stercie pism.'
        }),
    )


# ===== MATRYCA PRZEGRODEK =====
class SlotMatrixAdmin(admin.ModelAdmin):
    list_display = ('slot_number', 'recipient', 'shelf', 'name', 'geometry_summary')
    list_display_links = ('name',)
    list_filter = ('shelf', 'slot_number', 'recipient')
    list_editable = ('recipient',)
    search_fields = ('recipient__first_name', 'recipient__last_name', 'name')
    ordering = ('shelf', 'slot_number')
    
    actions = ['assign_to_recipient', 'clear_slot_assignment']
    
    def geometry_summary(self, obj):
        return f"x:{obj.x_pct:.0f}% y:{obj.y_pct:.0f}% {obj.w_pct:.0f}x{obj.h_pct:.0f}%"
    geometry_summary.short_description = 'Geometria'
    
    def assign_to_recipient(self, request, queryset):
        from django import forms
        
        class AssignForm(forms.Form):
            recipient = forms.ModelChoiceField(
                queryset=Recipient.objects.all(),
                label='Wybierz pracownika'
            )
        
        if request.POST.get('post'):
            form = AssignForm(request.POST)
            if form.is_valid():
                recipient = form.cleaned_data['recipient']
                updated = queryset.update(recipient=recipient)
                self.message_user(request, f'Przypisano {updated} stref(y) do: {recipient}')
                return None
        else:
            form = AssignForm()
        
        return render(
            request,
            'admin/assign_recipient.html',
            {
                'queryset': queryset,
                'form': form,
                'opts': self.model._meta,
                'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
            }
        )
    assign_to_recipient.short_description = '🎯 Przypisz zaznaczone strefy do pracownika'
    
    def clear_slot_assignment(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'Usunięto {count} stref(y) z matrycy')
    clear_slot_assignment.short_description = '❌ Usuń zaznaczone strefy z matrycy'


class SlotMatrixProxy(RecipientZone):
    class Meta:
        proxy = True
        verbose_name = 'Matryca przegródek'
        verbose_name_plural = 'Matryca przegródek (szybkie przypisanie)'

admin.site.register(SlotMatrixProxy, SlotMatrixAdmin)