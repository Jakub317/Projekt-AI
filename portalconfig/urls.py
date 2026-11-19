from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

admin.site.site_url = '/'

urlpatterns = [
    path('', TemplateView.as_view(template_name='office/landing.html'), name='landing'),
    path('admin/', admin.site.urls),
    path('omnipost-portal/', include('submissions.urls')),
    path('omnipost-portal/office/', include('office.urls')),
]
