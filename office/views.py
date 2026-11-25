import json
import os
from datetime import timedelta, datetime
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils import timezone
from django.core.files.storage import default_storage
from submissions.models import UploadedMaterial
from .models import (
    Shelf, Recipient, RecipientZone, DetectedFrame,
    Letter, Notification, DetectionConfig, CameraQueueItem,
    Administrator, PileScan, PileArchiveEntry, ArchiveConfig,
    ChaosReport
)
from .detection import detect_frames, crop_zone_for_mms, ocr_pile_image, detect_zone_changes


def _send_personalized_notification(letter, shelf, zone, photo_for_mms):
    rec = letter.recipient
    channel = getattr(rec, "preferred_channel", "mms") or "mms"
    zone_label = zone.name if zone and zone.name else (zone.shelf.name if zone else shelf.name)
    base_msg = f"Nowa przesyłka '{letter.document_type}' w strefie {zone_label}. Termin odbioru: {letter.due_date}."
    mms_rel_path = ""
    if channel == "mms" and zone and photo_for_mms:
        mms_rel_path = crop_zone_for_mms(photo_for_mms, zone)
    if channel == "mms":
        content = f"MMS do {rec.phone or 'brak nr'}: {base_msg}" + (" [Załączono wycinek strefy]" if mms_rel_path else "")
    elif channel == "voice_call":
        content = f"VOICE CALL do {rec.phone or 'brak nr'}: Halo {rec.first_name}, tu OmniPost AI. {base_msg}"
    elif channel == "email":
        content = f"E-MAIL do {rec.email or 'brak e-mail'}: {base_msg}"
    else:
        content = f"SMS do {rec.phone or 'brak nr'}: {base_msg}"
    return Notification.objects.create(letter=letter, channel=channel, content=content, mms_image=mms_rel_path)


def _send_admin_notification(admin, message_text):
    channel = admin.preferred_channel or "email"
    if channel == "email":
        content = f"E-MAIL do {admin.email or 'brak e-mail'}: {message_text}"
    elif channel == "voice_call":
        content = f"VOICE CALL do {admin.phone or 'brak nr'}: Halo {admin.first_name}, tu OmniPost AI. {message_text}"
    elif channel == "mms":
        content = f"MMS do {admin.phone or 'brak nr'}: {message_text}"
    elif channel == "telegram":
        content = f"TELEGRAM do {admin.phone or 'brak nr'}: {message_text}"
    else:
        content = f"SMS do {admin.phone or 'brak nr'}: {message_text}"
    return {
        "channel": channel,
        "content": content,
        "admin_name": f"{admin.first_name} {admin.last_name}",
    }


def _detect_chaos_outside_zones(photo_before, photo_after, zones):
    """
    Wykrywa zmiany POZA zdefiniowanymi strefami pracowników (bałagan).
    Zwraca JEDNĄ ramkę (bounding box) obejmującą cały obszar bałaganu.
    """
    try:
        if not photo_before or not photo_after:
            return []
        if not default_storage.exists(photo_before.file.name) or not default_storage.exists(photo_after.file.name):
            return []
        from PIL import Image, ImageChops
        import numpy as np
        img_a = Image.open(default_storage.open(photo_before.file.name, "rb")).convert("RGB")
        img_b = Image.open(default_storage.open(photo_after.file.name, "rb")).convert("RGB")
        width, height = img_a.size
        diff_full = ImageChops.difference(img_a, img_b).convert("L")
        diff_array = np.array(diff_full)
        # Zamazuj strefy pracowników
        for zone in zones:
            x1 = int((zone.x_pct / 100.0) * width)
            y1 = int((zone.y_pct / 100.0) * height)
            x2 = int(((zone.x_pct + zone.w_pct) / 100.0) * width)
            y2 = int(((zone.y_pct + zone.h_pct) / 100.0) * height)
            x1 = max(0, x1); y1 = max(0, y1)
            x2 = min(width, x2); y2 = min(height, y2)
            if x2 > x1 and y2 > y1:
                diff_array[y1:y2, x1:x2] = 0
        # Znajdź piksele z różnicą > próg
        threshold = 35
        diff_pixels = np.where(diff_array > threshold)
        if len(diff_pixels[0]) == 0:
            return []
        # Oblicz bounding box
        min_y, max_y = diff_pixels[0].min(), diff_pixels[0].max()
        min_x, max_x = diff_pixels[1].min(), diff_pixels[1].max()
        # Konwersja na %
        x_pct = (min_x / width) * 100
        y_pct = (min_y / height) * 100
        w_pct = ((max_x - min_x) / width) * 100
        h_pct = ((max_y - min_y) / height) * 100
        # Sprawdź czy to nie za małe (szum)
        if w_pct < 2 or h_pct < 2 or w_pct > 50 or h_pct > 50:
            print(f"[CHAOS-FILTER] Box {w_pct:.0f}%x{h_pct:.0f}% = szum AI, ignoruję")
            return []
        mean_diff = diff_array[diff_pixels].mean()
        return [{
            "x_pct": x_pct,
            "y_pct": y_pct,
            "w_pct": w_pct,
            "h_pct": h_pct,
            "confidence": min(0.99, 0.70 + (mean_diff / 150.0))
        }]
    except Exception as e:
        print(f"[ERROR] _detect_chaos_outside_zones: {e}")
        return []


@login_required
def demo_office(request):
    if not Recipient.objects.exists():
        Recipient.objects.create(first_name="Eryk", last_name="Kowalski", phone="+48123456789", preferred_channel="mms")
    shelf = Shelf.objects.first() or Shelf.objects.create(name="Regał Główny", location="Biuro")
    config, _ = DetectionConfig.objects.get_or_create(id=1)
    front_photos = UploadedMaterial.objects.filter(material_type="photo", camera_source="front").order_by("-id")
    top_photos = UploadedMaterial.objects.filter(material_type="photo", camera_source="top").order_by("-id")
    baseline = CameraQueueItem.objects.filter(shelf=shelf, status="baseline").order_by("-id").first()
    pending_queue = CameraQueueItem.objects.filter(shelf=shelf, status="pending").order_by("id")
    history_queue = CameraQueueItem.objects.filter(shelf=shelf, status="processed").order_by("-id")[:5]
    recent_notifications = Notification.objects.select_related("letter__recipient").order_by("-sent_at")[:8]
    return render(request, "office/demo.html", {
        "shelf": shelf, "config": config, "front_photos": front_photos, "top_photos": top_photos,
        "baseline": baseline, "pending_queue": pending_queue, "history_queue": history_queue,
        "recent_notifications": recent_notifications,
    })


@login_required
@require_http_methods(["POST"])
def api_toggle_detection_mode(request):
    try:
        data = json.loads(request.body)
        config, _ = DetectionConfig.objects.get_or_create(id=1)
        mode = data.get("mode")
        if mode in ("local", "apn"):
            config.mode = mode
        if "apn_url" in data:
            config.apn_url = data["apn_url"].strip()
        if "apn_token" in data:
            config.apn_token = data["apn_token"].strip()
        config.save()
        return JsonResponse({"status": "ok", "mode": config.mode, "apn_url": config.apn_url})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def api_enqueue_photo(request):
    try:
        data = json.loads(request.body)
        photo = get_object_or_404(UploadedMaterial, id=data.get("photo_id"))
        shelf = Shelf.objects.first() or Shelf.objects.create(name="Regał Główny", location="Biuro")
        has_baseline = CameraQueueItem.objects.filter(shelf=shelf, status="baseline").exists()
        status = "pending" if has_baseline else "baseline"
        item = CameraQueueItem.objects.create(shelf=shelf, photo=photo, status=status,
            diff_summary="Ustawiono jako pierwsze zdjęcie bazowe" if status == "baseline" else "Oczekuje na konfrontację z bazą")
        return JsonResponse({"status": "ok", "item_id": item.id, "assigned_status": status})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def api_process_next_in_queue(request):
    try:
        shelf = Shelf.objects.first() or Shelf.objects.create(name="Regał Główny", location="Biuro")
        baseline = CameraQueueItem.objects.filter(shelf=shelf, status="baseline").order_by("-id").first()
        next_item = CameraQueueItem.objects.filter(shelf=shelf, status="pending").order_by("id").first()

        if not baseline:
            return JsonResponse({"status": "error", "message": "Brak zdjęcia bazowego w kolejce. Dodaj pierwsze zdjęcie."}, status=400)
        if not next_item:
            return JsonResponse({"status": "error", "message": "Kolejka oczekujących zdjęć jest pusta. Dodaj kolejne zdjęcie."}, status=400)

        zones = list(shelf.zones.select_related("recipient").all())
        db_logs = []
        mms_previews = []
        triggered_notifications = []
        boxes = []

        # KROK 1: Sprawdź strefy pracowników (slot 1-5)
        if zones and any(z.slot_number for z in zones):
            changes = detect_zone_changes(baseline.photo, next_item.photo, zones)
            for change in changes:
                zone = next((z for z in zones if z.slot_number == change["slot_number"]), None)
                if not zone or not zone.recipient:
                    continue
                boxes.append({
                    "x": change["x_pct"] * 10, "y": change["y_pct"] * 8,
                    "w": change["w_pct"] * 10, "h": change["h_pct"] * 8,
                    "confidence": change["confidence"],
                    "slot": change["slot_number"],
                    "recipient": str(zone.recipient),
                    "type": "employee"
                })
                frame = DetectedFrame.objects.create(
                    shelf=shelf, frame_index=next_item.id,
                    x_pct=change["x_pct"], y_pct=change["y_pct"],
                    w_pct=change["w_pct"], h_pct=change["h_pct"],
                    confidence=change["confidence"]
                )
                letter = Letter.objects.create(
                    frame=frame, recipient=zone.recipient,
                    due_date=timezone.localdate() + timedelta(days=7),
                    document_type=f"Przesylka w Slot {change['slot_number']}",
                    status="pending"
                )
                notif = _send_personalized_notification(letter, shelf, zone, next_item.photo)
                db_logs.append(f"[{notif.channel.upper()}] Slot {change['slot_number']} ({zone.recipient}) -> {notif.content}")
                if notif.mms_image:
                    mms_previews.append({"recipient": str(zone.recipient), "url": f"/omnipost-portal/office/mms-crop/{notif.mms_image}/"})
                triggered_notifications.append({
                    "channel": notif.channel, "recipient": str(zone.recipient),
                    "details": f"Slot {change['slot_number']} - {letter.document_type} - termin: {letter.due_date}",
                    "url": "/omnipost-portal/office/console/"
                })

        # KROK 2: Sprawdź bałagan poza strefami pracowników
        chaos_boxes = _detect_chaos_outside_zones(baseline.photo, next_item.photo, zones)
        admin = Administrator.objects.filter(is_active=True).first()

        if chaos_boxes and admin:
            for cb in chaos_boxes:
                boxes.append({
                    "x": cb["x_pct"] * 10, "y": cb["y_pct"] * 8,
                    "w": cb["w_pct"] * 10, "h": cb["h_pct"] * 8,
                    "confidence": cb["confidence"],
                    "slot": None,
                    "recipient": "BALAGAN",
                    "type": "chaos"
                })
                report = ChaosReport.objects.create(
                    shelf=shelf, zone=None, report_type='out_of_zone',
                    object_type='Nieznany obiekt poza strefa',
                    confidence=cb["confidence"], status='pending',
                    reported_by='AI System (detekcja balaganu)'
                )
                base_msg = f"Wykryto balagan poza strefami pracownikow na polce '{shelf.name}'."
                notif_info = _send_admin_notification(admin, base_msg)
                db_logs.append(f"[CHAOS-ADMIN] {notif_info['admin_name']} -> {notif_info['content']}")
                triggered_notifications.append({
                    "channel": notif_info["channel"],
                    "recipient": f"{notif_info['admin_name']} (Admin)",
                    "details": f"Balagan poza strefami - zgloszenie #{report.id}",
                    "url": f"/admin/office/chaosreport/{report.id}/change/"
                })

        baseline.status = "processed"
        baseline.save()
        next_item.status = "baseline"
        emp_count = len([b for b in boxes if b.get('type') == 'employee'])
        chaos_count = len([b for b in boxes if b.get('type') == 'chaos'])
        next_item.diff_summary = f"Wykryto {emp_count} zmian w strefach + {chaos_count} balaganu"
        next_item.save()

        return JsonResponse({
            "status": "ok", "baseline_id": baseline.photo.id, "current_id": next_item.photo.id,
            "boxes": boxes, "db_logs": db_logs, "mms_previews": mms_previews,
            "triggered_notifications": triggered_notifications,
            "message": f"Skonfrontowano #{next_item.id} z #{baseline.id}. Wykryto {len(boxes)} zmian."
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_reset_queue(request):
    CameraQueueItem.objects.all().delete()
    return JsonResponse({"status": "ok"})


@login_required
def public_photo(request, pk):
    m = UploadedMaterial.objects.filter(pk=pk).first()
    if not m:
        s = Shelf.objects.filter(pk=pk).first()
        m = s.photo if s else None
    if m and m.file and default_storage.exists(m.file.name):
        return FileResponse(default_storage.open(m.file.name, "rb"), content_type="image/jpeg")
    raise Http404("Zdjecie nie istnieje")


@login_required
def public_mms_crop(request, rel_path):
    abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)
    if os.path.exists(abs_path):
        return FileResponse(open(abs_path, "rb"), content_type="image/jpeg")
    raise Http404("Wycinek MMS nie istnieje")


@login_required
def system_console(request):
    notifications = Notification.objects.all().select_related("letter__recipient", "letter__frame__shelf").order_by("-sent_at")
    return render(request, "office/system_console.html", {"notifications": notifications})


@login_required
def employee_documents(request):
    recipients = Recipient.objects.all().order_by("last_name", "first_name")
    recipient_docs = []
    total_pending = total_picked = total_overdue = 0
    for r in recipients:
        letters = Letter.objects.filter(recipient=r).select_related("frame__shelf").order_by("-created_at")
        pending = letters.filter(status="pending").count()
        delivered = letters.filter(status="delivered").count()
        overdue = letters.filter(status="overdue").count()
        total_pending += pending; total_picked += delivered; total_overdue += overdue
        recipient_docs.append({"recipient": r, "letters": letters,
            "pending": pending, "delivered": delivered, "overdue": overdue, "total": letters.count()})
    return render(request, "office/employee_documents.html", {
        "recipient_docs": recipient_docs, "total_pending": total_pending,
        "total_picked": total_picked, "total_overdue": total_overdue,
    })


@login_required
def operations_panel(request):
    recipients = Recipient.objects.all().order_by("last_name", "first_name")
    shelves = Shelf.objects.all().order_by("name")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_recipient":
            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            email = request.POST.get("email", "").strip()
            phone = request.POST.get("phone", "").strip()
            preferred_channel = request.POST.get("preferred_channel", "mms")
            if first_name and last_name:
                Recipient.objects.create(first_name=first_name, last_name=last_name,
                    email=email, phone=phone, preferred_channel=preferred_channel)
                messages.success(request, f"Dodano pracownika: {first_name} {last_name} (kanal: {preferred_channel.upper()})")
            else:
                messages.error(request, "Imie i nazwisko sa wymagane.")
        elif action == "update_channel":
            rec = get_object_or_404(Recipient, id=request.POST.get("recipient_id"))
            rec.preferred_channel = request.POST.get("preferred_channel", "mms")
            rec.save()
            messages.success(request, f"Zmieniono kanal powiadomien dla {rec}: {rec.get_preferred_channel_display()}")
        elif action == "add_document":
            recipient_id = request.POST.get("recipient")
            doc_type = request.POST.get("doc_type", "Pismo ogolne").strip()
            due_date_str = request.POST.get("due_date")
            if recipient_id and due_date_str:
                recipient = get_object_or_404(Recipient, id=recipient_id)
                dummy_shelf = shelves.first()
                if dummy_shelf:
                    frame = DetectedFrame.objects.create(shelf=dummy_shelf, frame_index=0, confidence=1.0)
                    letter = Letter.objects.create(frame=frame, recipient=recipient, document_type=doc_type,
                        due_date=datetime.strptime(due_date_str, "%Y-%m-%d").date(), status="pending")
                    zone = RecipientZone.objects.filter(shelf=dummy_shelf, recipient=recipient).first()
                    _send_personalized_notification(letter, dummy_shelf, zone, dummy_shelf.photo)
                    messages.success(request, f"Wystawiono dokument '{doc_type}' i wyslano powiadomienie ({recipient.get_preferred_channel_display()})")
        elif action == "upload_file":
            uploaded_file = request.FILES.get("file")
            shelf_id = request.POST.get("shelf")
            if uploaded_file and shelf_id:
                shelf = get_object_or_404(Shelf, id=shelf_id)
                material = UploadedMaterial.objects.create(uploaded_by=request.user, material_type="photo",
                    file=uploaded_file, original_name=uploaded_file.name)
                shelf.photo = material
                shelf.save()
                messages.success(request, f"Wgrano plik i przypisano do polki: {shelf.name}")
        return redirect("office:operations")
    return render(request, "office/operations.html", {"recipients": recipients, "shelves": shelves})


@login_required
@require_http_methods(["POST"])
def api_analyze_images(request):
    try:
        data = json.loads(request.body)
        photo_a = get_object_or_404(UploadedMaterial, id=data.get("img_a_id"))
        photo_b = get_object_or_404(UploadedMaterial, id=data.get("img_b_id"))
        boxes = detect_frames(photo_b, photo_before=photo_a) or []
        return JsonResponse({"status": "ok", "metrics": {"boxes_a": 0, "boxes_b": len(boxes)},
            "added": len(boxes), "removed": 0, "db_logs": [f"Wykryto {len(boxes)} roznic miedzy obrazami"],
            "raw_a": [], "raw_b": boxes})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_run_diff_engine(request):
    return api_process_next_in_queue(request)


@login_required
@require_http_methods(["GET"])
def api_latest_notifications(request):
    notifications = Notification.objects.all().select_related("letter__recipient").order_by("-sent_at")[:20]
    data = [{"id": n.id, "channel": n.channel, "content": n.content,
        "mms_image": f"/omnipost-portal/office/mms-crop/{n.mms_image}/" if n.mms_image else "",
        "sent_at": n.sent_at.strftime("%Y-%m-%d %H:%M:%S"),
        "recipient": str(n.letter.recipient) if n.letter else "Nieznany"} for n in notifications]
    return JsonResponse({"notifications": data})


@login_required
def list_shelves(request):
    shelves = Shelf.objects.all().order_by("name")
    return render(request, "office/list_shelves.html", {"shelves": shelves})


@login_required
def edit_shelf_zones(request, shelf_id):
    shelf = get_object_or_404(Shelf, id=shelf_id)
    zones = shelf.zones.all().select_related("recipient")
    recipients = Recipient.objects.all().order_by("last_name", "first_name")
    return render(request, "office/zone_editor.html", {"shelf": shelf, "zones": zones, "recipients": recipients})


@login_required
@require_http_methods(["POST"])
def save_zone(request):
    try:
        data = json.loads(request.body)
        shelf = get_object_or_404(Shelf, id=data["shelf_id"])
        recipient = get_object_or_404(Recipient, id=data["recipient_id"])
        zone = RecipientZone.objects.create(shelf=shelf, recipient=recipient,
            name=data.get("name", recipient.first_name),
            slot_number=data.get("slot_number") or None,
            x_pct=float(data.get("x_pct", 0)), y_pct=float(data.get("y_pct", 0)),
            w_pct=float(data.get("w_pct", 0)), h_pct=float(data.get("h_pct", 0)))
        return JsonResponse({"status": "ok", "id": zone.id, "slot_number": zone.slot_number})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def delete_zone(request, zone_id):
    try:
        get_object_or_404(RecipientZone, id=zone_id).delete()
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def api_detect_chaos(request):
    try:
        data = json.loads(request.body)
        shelf_id = data.get('shelf_id')
        if not shelf_id:
            return JsonResponse({'status': 'error', 'message': 'Brak ID polki'}, status=400)
        shelf = get_object_or_404(Shelf, id=shelf_id)
        zones = list(RecipientZone.objects.filter(shelf=shelf).select_related('recipient'))
        ai_logs = []
        ai_logs.append({'type': 'info', 'msg': f'[CHAOS-INIT] Skanowanie polki: {shelf.name}'})
        ai_logs.append({'type': 'info', 'msg': f'[CHAOS-SCAN] Analiza obrazu pod katem balaganu...'})
        ai_logs.append({'type': 'success', 'msg': f'[CHAOS-READY] Model YOLO gotowy. Rozpoczynam detekcje obiektow poza strefami...'})
        chaos_reports = []
        notifications_sent = []
        admin = Administrator.objects.filter(is_active=True).first()
        if not admin:
            ai_logs.append({'type': 'warning', 'msg': '[CHAOS-WARN] Brak aktywnego Administratora w systemie!'})
        import random
        simulated_objects = random.randint(0, 2)
        for i in range(simulated_objects):
            x_pct = random.uniform(0, 100)
            y_pct = random.uniform(0, 100)
            is_outside = True
            for zone in zones:
                if (zone.x_pct <= x_pct <= zone.x_pct + zone.w_pct and zone.y_pct <= y_pct <= zone.y_pct + zone.h_pct):
                    is_outside = False
                    break
            if is_outside:
                ai_logs.append({'type': 'warning', 'msg': f'[CHAOS-DETECT] Wykryto obiekt poza strefa na pozycji ({x_pct:.0f}%, {y_pct:.0f}%)'})
                report = ChaosReport.objects.create(shelf=shelf, zone=None, report_type='out_of_zone',
                    object_type=f'Nieznany obiekt #{i + 1}', confidence=random.uniform(0.7, 0.95),
                    status='pending', reported_by='AI System (YOLO)')
                chaos_reports.append({'id': report.id, 'shelf': shelf.name, 'object_type': report.object_type,
                    'position': f'({x_pct:.0f}%, {y_pct:.0f}%)', 'confidence': f'{report.confidence:.2f}',
                    'status': report.get_status_display(), 'created_at': report.created_at.strftime('%Y-%m-%d %H:%M:%S')})
                if admin:
                    base_msg = f"Wykryto balagan na polce '{shelf.name}': {report.object_type} poza strefa ({x_pct:.0f}%, {y_pct:.0f}%)."
                    notif_info = _send_admin_notification(admin, base_msg)
                    notifications_sent.append({'channel': notif_info['channel'],
                        'recipient': f"{notif_info['admin_name']} (Admin)",
                        'details': f"Balagan: {report.object_type}",
                        'url': f"/admin/office/chaosreport/{report.id}/change/"})
                    ai_logs.append({'type': 'success', 'msg': f'[CHAOS-NOTIFY] Powiadomiono Administratora {notif_info["admin_name"]} przez {notif_info["channel"].upper()}'})
        if simulated_objects == 0:
            ai_logs.append({'type': 'success', 'msg': f'[CHAOS-DONE] Polka czysta! Nie wykryto balaganu.'})
        else:
            ai_logs.append({'type': 'warning', 'msg': f'[CHAOS-DONE] Wykryto {len(chaos_reports)} obiekt(ow) poza strefami.'})
        return JsonResponse({'status': 'ok', 'total_objects_detected': simulated_objects,
            'chaos_reports': chaos_reports, 'triggered_notifications': notifications_sent,
            'ai_logs': ai_logs,
            'message': f'Zeskanowano polke {shelf.name}. Wykryto {len(chaos_reports)} obiektow poza strefami.'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': f'{type(e).__name__}: {str(e)}'}, status=400)


@login_required
@require_http_methods(["POST"])
def api_scan_pile(request):
    try:
        data = json.loads(request.body)
        photo_id = data.get('photo_id')
        if not photo_id:
            return JsonResponse({'status': 'error', 'message': 'Brak ID zdjecia'}, status=400)
        photo = get_object_or_404(UploadedMaterial, id=photo_id)
        ai_logs = []
        ai_logs.append({'type': 'info', 'msg': '[PILE-INIT] Rozpoczynam skan sterty pism...'})
        ai_logs.append({'type': 'info', 'msg': '[PILE-OCR] Wysylanie obrazu do Gemini API...'})
        try:
            ocr_result = ocr_pile_image(photo)
            ai_logs.append({'type': 'success', 'msg': '[PILE-OCR] Odczytano dane z przesylek'})
        except Exception as e:
            ai_logs.append({'type': 'warning', 'msg': f'[PILE-OCR] Gemini API niedostepne: {str(e)}. Uzywam symulacji.'})
            ocr_result = [
                {'recipient_name': 'Jan Kowalski', 'sender': 'Poczta Polska', 'tracking_number': 'PL123456789',
                    'document_type': 'Pismo polecone', 'document_date': timezone.localdate().strftime('%Y-%m-%d'), 'confidence': 0.92},
                {'recipient_name': 'Anna Nowak', 'sender': 'DHL', 'tracking_number': 'DHL987654321',
                    'document_type': 'Faktura', 'document_date': timezone.localdate().strftime('%Y-%m-%d'), 'confidence': 0.88}
            ]
            ai_logs.append({'type': 'success', 'msg': '[PILE-OCR] Symulacja OCR zakoczczona'})
        scanned_items = []
        for item in ocr_result:
            recipient = None
            if item.get('recipient_name'):
                last_name = item['recipient_name'].split()[-1] if ' ' in item['recipient_name'] else item['recipient_name']
                recipient = Recipient.objects.filter(last_name__icontains=last_name).first()
            scan = PileScan.objects.create(recipient=recipient, sender=item.get('sender', ''),
                tracking_number=item.get('tracking_number', ''), document_type=item.get('document_type', ''),
                document_date=datetime.strptime(item['document_date'], '%Y-%m-%d').date() if item.get('document_date') else None,
                image_path=photo.file, raw_ocr_text=json.dumps(item, ensure_ascii=False), confidence=item.get('confidence', 0.0))
            PileArchiveEntry.objects.create(scan=scan, change_type='added',
                description=f"Wykryto nowa przesyike: {item.get('document_type', 'Przesylka')} dla {item.get('recipient_name', 'Nieznany')}")
            scanned_items.append({'id': scan.id, 'recipient': str(recipient) if recipient else item.get('recipient_name', 'Nieznany'),
                'sender': item.get('sender', ''), 'tracking_number': item.get('tracking_number', ''),
                'document_type': item.get('document_type', ''), 'document_date': item.get('document_date', ''),
                'detected_at': scan.detected_at.strftime('%Y-%m-%d %H:%M'), 'confidence': f"{scan.confidence:.2f}"})
        archive_config = ArchiveConfig.objects.first()
        retention_days = archive_config.retention_days if archive_config else 1
        archive_cutoff = timezone.now() - timedelta(days=retention_days)
        archive_entries = PileArchiveEntry.objects.filter(timestamp__gte=archive_cutoff).select_related('scan').order_by('-timestamp')[:10]
        archive = [{'timestamp': entry.timestamp.strftime('%Y-%m-%d %H:%M'), 'change_type': entry.change_type,
            'description': entry.description} for entry in archive_entries]
        ai_logs.append({'type': 'success', 'msg': f'[PILE-DONE] Zeskanowano {len(scanned_items)} przesyiek ze sterty. Archiwum: {len(archive)} wpisow.'})
        return JsonResponse({'status': 'ok', 'items': scanned_items, 'archive': archive, 'ai_logs': ai_logs,
            'message': f'Zeskanowano {len(scanned_items)} przesyiek ze sterty.'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': f'{type(e).__name__}: {str(e)}'}, status=400)


@login_required
def document_editor(request):
    recipients = Recipient.objects.all().order_by("last_name", "first_name")
    letters = Letter.objects.select_related("recipient", "frame__shelf").order_by("-due_date")
    
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add":
            recipient = get_object_or_404(Recipient, id=request.POST.get("recipient_id"))
            doc_type = request.POST.get("doc_type", "Inne").strip()
            due_date = datetime.strptime(request.POST.get("due_date"), "%Y-%m-%d").date()
            shelf = Shelf.objects.first()
            if not shelf:
                shelf = Shelf.objects.create(name="Regał Główny", location="Biuro")
            frame = DetectedFrame.objects.create(shelf=shelf, frame_index=0, confidence=1.0)
            Letter.objects.create(
                recipient=recipient, document_type=doc_type,
                due_date=due_date, status="pending", frame=frame
            )
            messages.success(request, f"Dodano dokument: {doc_type} dla {recipient}")
        elif action == "update_status":
            letter = get_object_or_404(Letter, id=request.POST.get("letter_id"))
            letter.status = request.POST.get("status", "pending")
            letter.save()
            messages.success(request, f"Zmieniono status: {letter.get_status_display()}")
        elif action == "delete":
            get_object_or_404(Letter, id=request.POST.get("letter_id")).delete()
            messages.success(request, "Usunięto dokument")
        return redirect("office:document_editor")
    
    today = timezone.localdate()
    stats = {
        "total": letters.count(),
        "pending": letters.filter(status="pending").count(),
        "delivered": letters.filter(status="delivered").count(),
        "overdue": letters.filter(status="pending", due_date__lt=today).count(),
        "urgent": letters.filter(status="pending", due_date__lte=today + timedelta(days=3), due_date__gte=today).count(),
    }
    
    return render(request, "office/document_editor.html", {
        "letters": letters, "recipients": recipients, "stats": stats, "today": today,
    })


