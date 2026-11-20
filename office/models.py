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

    def __str__(self):
        return f"{self.name or self.recipient} ({self.shelf.name})"
