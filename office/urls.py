from django.urls import path
from . import views

app_name = 'office'

urlpatterns = [
    path('', views.demo_office, name='demo'),
    path('operations/', views.operations_panel, name='operations'),
    path('console/', views.system_console, name='system_console'),
    path('employee-documents/', views.employee_documents, name='employee_documents'),
    path('photo/<int:pk>/', views.public_photo, name='photo'),
    path('api/analyze/', views.api_analyze_images, name='api_analyze'),
    path('api/diff-engine/', views.api_run_diff_engine, name='api_diff'),
    path('api/latest-notifications/', views.api_latest_notifications, name='api_latest_notifications'),
    path('zones/', views.list_shelves, name='list_shelves'),
    path('zones/<int:shelf_id>/', views.edit_shelf_zones, name='edit_shelf_zones'),
    path('api/zones/save/', views.save_zone, name='save_zone'),
    path('api/zones/<int:zone_id>/delete/', views.delete_zone, name='delete_zone'),
]
