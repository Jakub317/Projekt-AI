from django.db import models
from submissions.models import UploadedMaterial


class DetectionConfig(models.Model):
    MODE_CHOICES = [
        ("local", "Lokalny wzorzec / Model"),
        ("apn", "Zewnętrzne API / APN"),
    ]
    mode = models.CharField(max_length=16, choices=MODE_CHOICES, default="local")
    apn_url = models.URLField(blank=True, default="https://omnipost.local")
    apn_token = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class Shelf(models.Model):
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=120, blank=True)
    photo = models.ForeignKey(UploadedMaterial, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="shelves")
    created_at = models.DateTimeField(auto_now_add=True)


class CameraQueueItem(models.Model):
    STATUS_CHOICES = [
        ("baseline", "Zdjęcie bazowe (Referencyjne)"),
        ("pending", "Oczekuje w kolejce"),
        ("processed", "Przetworzone (Nowa baza)"),
    ]
    shelf = models.ForeignKey(Shelf, on_delete=models.CASCADE, related_name="queue_items")
    photo = models.ForeignKey(UploadedMaterial, on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    diff_summary = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Recipient(models.Model):
    CHANNEL_CHOICES = [
        ("sms", "SMS tekstowy"),
        ("mms", "MMS (wycinek strefy)"),
        ("email", "E-mail"),
        ("voice_call", "Połączenie głosowe AI"),
    ]
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    preferred_channel = models.CharField(max_length=16, choices=CHANNEL_CHOICES, default="mms")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class DetectedFrame(models.Model):
    shelf = models.ForeignKey(Shelf, on_delete=models.CASCADE, related_name="frames")
    frame_index = models.IntegerField()
    x_pct = models.FloatField(default=0.0)
    y_pct = models.FloatField(default=0.0)
    w_pct = models.FloatField(default=0.0)
    h_pct = models.FloatField(default=0.0)
    confidence = models.FloatField(default=0.0)
    detected_at = models.DateTimeField(auto_now_add=True)


class Letter(models.Model):
    STATUS_CHOICES = [("pending","Oczekuje"),("delivered","Odebrane"),("overdue","Przeterminowane")]
    frame = models.OneToOneField(DetectedFrame, on_delete=models.CASCADE, related_name="letter")
    recipient = models.ForeignKey(Recipient, on_delete=models.CASCADE, related_name="letters")
    due_date = models.DateField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    delivered_at = models.DateTimeField(null=True, blank=True)
    document_type = models.CharField(max_length=64, blank=True, default="Pismo ogólne")
    description = models.TextField(blank=True, default="Brak dodatkowego opisu.")
    notification_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    letter = models.ForeignKey(Letter, on_delete=models.CASCADE, related_name="notifications")
    channel = models.CharField(max_length=12, choices=[("sms","SMS"),("mms","MMS"),("email","E-mail"),("voice_call","Rozmowa AI")])
    sent_at = models.DateTimeField(auto_now_add=True)
    content = models.TextField()
    mms_image = models.CharField(max_length=255, blank=True)


class RecipientZone(models.Model):
    shelf = models.ForeignKey(Shelf, on_delete=models.CASCADE, related_name="zones")
    recipient = models.ForeignKey(Recipient, on_delete=models.CASCADE)
    x_pct = models.FloatField(default=0.0)
    y_pct = models.FloatField(default=0.0)
    w_pct = models.FloatField(default=0.0)
    h_pct = models.FloatField(default=0.0)
    name = models.CharField(max_length=100, blank=True, help_text="Np. Półka Anny")
    
    # NOWE POLE: Numer przegródki (np. 1-14). Może się powtarzać dla jednego pracownika!
    slot_number = models.IntegerField(null=True, blank=True, help_text="Numer przegródki na półce (np. 1-14)")

    class Meta:
        ordering = ['slot_number', 'name']
        verbose_name = 'Strefa pracownika'
        verbose_name_plural = 'Strefy pracowników'

    def __str__(self):
        slot_display = f"Slot #{self.slot_number}" if self.slot_number else "Bez slotu"
        return f"{self.name or self.recipient} ({slot_display} - {self.shelf.name})"

class NotificationConfig(models.Model):
    """Konfiguracja dostawców powiadomień (SMS/MMS/Email)"""
    PROVIDER_CHOICES = [
        ('demo', 'Tryb Demo (Tylko logi w konsoli - bezpieczne dla studentów)'),
        ('twilio', 'Twilio (Płatne SMS/MMS)'),
        ('smsapi', 'SMSAPI.pl'),
        ('telegram', 'Telegram Bot (Darmowy)'),
    ]
    
    sms_provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='demo')
    mms_provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='demo')
    email_provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='demo')
    
    class Meta:
        verbose_name = "Konfiguracja Powiadomień"
        verbose_name_plural = "Konfiguracja Powiadomień"

    def __str__(self):
        return "Ustawienia dostawców powiadomień"

class ChaosReport(models.Model):
    """Zgłoszenie bałaganu (Porządek Grecki)"""
    REPORT_TYPE_CHOICES = [
        ('out_of_zone', 'Obiekt poza strefą'),
        ('unidentified', 'Niezidentyfikowany obiekt'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Oczekuje na review'),
        ('reviewed', 'Przejrzane'),
        ('resolved', 'Rozwiązane'),
        ('rejected', 'Odrzucone'),
    ]
    
    shelf = models.ForeignKey(Shelf, on_delete=models.CASCADE, related_name='chaos_reports')
    zone = models.ForeignKey(RecipientZone, on_delete=models.SET_NULL, null=True, blank=True)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, default='out_of_zone')
    object_type = models.CharField(max_length=100, blank=True)
    confidence = models.FloatField(default=0.0)
    image_path = models.ImageField(upload_to='chaos_reports/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, help_text='Notatki administratora')
    reported_by = models.CharField(max_length=50, default='AI System')
    reviewed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Zgłoszenie bałaganu'
        verbose_name_plural = 'Zgłoszenia bałaganu'
    
    def __str__(self):
        return f"{self.get_report_type_display()} - {self.shelf.name} ({self.get_status_display()})"

class Administrator(models.Model):
    """Administrator systemu - otrzymuje powiadomienia o balaganie"""
    CHANNEL_CHOICES = [
        ('sms', 'SMS'),
        ('mms', 'MMS'),
        ('email', 'E-mail'),
        ('telegram', 'Telegram'),
        ('voice_call', 'Voice Call'),
    ]
    
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    preferred_channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='email')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['last_name', 'first_name']
        verbose_name = 'Administrator'
        verbose_name_plural = 'Administratorzy'
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class PileScan(models.Model):
    """Wynik OCR ze sterty pism (Porzadek Grecki - osobna kamera)"""
    recipient = models.ForeignKey('Recipient', on_delete=models.SET_NULL, null=True, blank=True)
    sender = models.CharField(max_length=200, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    document_type = models.CharField(max_length=100, blank=True)
    document_date = models.DateField(null=True, blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)
    image_path = models.ImageField(upload_to='pile_scans/', blank=True, null=True)
    raw_ocr_text = models.TextField(blank=True)
    confidence = models.FloatField(default=0.0)
    
    class Meta:
        ordering = ['-detected_at']
        verbose_name = 'Skan sterty'
        verbose_name_plural = 'Skany sterty'
    
    def __str__(self):
        return f"Scan #{self.id} - {self.recipient or 'Nieznany'} ({self.detected_at.strftime('%Y-%m-%d %H:%M')})"


class PileArchiveEntry(models.Model):
    """Archiwum zmian w obrebie sterty pism"""
    scan = models.ForeignKey(PileScan, on_delete=models.CASCADE, related_name='archive_entries')
    change_type = models.CharField(max_length=50)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Wpis archiwum sterty'
        verbose_name_plural = 'Wpisy archiwum sterty'
    
    def __str__(self):
        return f"{self.change_type} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class ArchiveConfig(models.Model):
    """Konfiguracja okresu archiwizacji"""
    retention_days = models.IntegerField(default=1, help_text="Ile dni przechowywac archiwum zmian")
    auto_cleanup = models.BooleanField(default=False, help_text="Automatycznie usuwac stare wpisy")
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Konfiguracja archiwum'
        verbose_name_plural = 'Konfiguracja archiwum'
    
    def __str__(self):
        return f"Archiwum: {self.retention_days} dni"
