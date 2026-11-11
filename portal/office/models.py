from django.db import models
from submissions.models import UploadedMaterial


class Shelf(models.Model):
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=120, blank=True)
    photo = models.ForeignKey(UploadedMaterial, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="shelves")
    created_at = models.DateTimeField(auto_now_add=True)


class Recipient(models.Model):
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class DetectedFrame(models.Model):
    shelf = models.ForeignKey(Shelf, on_delete=models.CASCADE, related_name="frames")
    frame_index = models.IntegerField()
    x = models.IntegerField()
    y = models.IntegerField()
    w = models.IntegerField()
    h = models.IntegerField()
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
    channel = models.CharField(max_length=8, choices=[("sms","SMS"),("email","E-mail")])
    sent_at = models.DateTimeField(auto_now_add=True)
    content = models.TextField()
