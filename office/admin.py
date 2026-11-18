from django.contrib import admin
from .models import Shelf, Recipient, DetectedFrame, Letter, Notification
admin.site.register([Shelf, Recipient, DetectedFrame, Letter, Notification])
