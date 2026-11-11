from django.urls import path
from . import views

app_name = "office"

urlpatterns = [
    path("", views.demo_office, name="demo"),
    path("photo/<int:pk>/", views.public_photo, name="photo"),
    path("upload-model/", views.upload_model, name="upload_model"),
    path("api/simulate-sms/", views.api_simulate_sms, name="api_simulate_sms"),
]
