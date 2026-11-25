from django.urls import path
from . import views

app_name = "office"

urlpatterns = [
    path("", views.demo_office, name="demo"),
    path("operations/", views.operations_panel, name="operations"),
    path("console/", views.system_console, name="system_console"),
    path("documents/", views.document_editor, name="document_editor"),
    path("employee-documents/", views.employee_documents, name="employee_documents"),
    path("photo/<int:pk>/", views.public_photo, name="photo"),
    path("mms-crop/<path:rel_path>/", views.public_mms_crop, name="mms_crop"),
    path("api/config/", views.api_toggle_detection_mode, name="api_config"),
    path("api/queue/enqueue/", views.api_enqueue_photo, name="api_enqueue"),
    path("api/queue/process-next/", views.api_process_next_in_queue, name="api_process_next"),
    path("api/queue/reset/", views.api_reset_queue, name="api_reset_queue"),
    path("api/analyze/", views.api_analyze_images, name="api_analyze"),
    path("api/diff-engine/", views.api_run_diff_engine, name="api_diff"),
    path("api/latest-notifications/", views.api_latest_notifications, name="api_latest_notifications"),
    path("api/detect-chaos/", views.api_detect_chaos, name="api_detect_chaos"),
    path("api/pile/scan/", views.api_scan_pile, name="api_scan_pile"),
    path("zones/", views.list_shelves, name="list_shelves"),
    path("zones/<int:shelf_id>/", views.edit_shelf_zones, name="edit_shelf_zones"),
    path("api/zones/save/", views.save_zone, name="save_zone"),
    path("api/zones/<int:zone_id>/delete/", views.delete_zone, name="delete_zone"),
]
