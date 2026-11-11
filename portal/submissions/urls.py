from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "submissions"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="submissions:login", permanent=False), name="root"),
    path("login/", views.PortalLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("start-training/", views.start_training, name="start_training"),
    path("download/<int:pk>/", views.download, name="download"),
    path("admin-panel/", views.admin_panel, name="admin_panel"),
    path("api/materials/", views.api_materials, name="api_materials"),
]
