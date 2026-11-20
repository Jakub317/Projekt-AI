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
    Letter, Notification, DetectionConfig, CameraQueueItem
)
from .detection import detect_frames, crop_zone_for_mms


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

    return Notification.objects.create(
        letter=letter,
        channel=channel,
        content=content,
        mms_image=mms_rel_path
    )


@login_required
def demo_office(request):
    if not Recipient.objects.exists():
        Recipient.objects.create(first_name="Eryk", last_name="Kowalski", phone="+48123456789", preferred_channel="mms")
    shelf = Shelf.objects.first() or Shelf.objects.create(name="Regał Główny", location="Biuro")
    config, _ = DetectionConfig.objects.get_or_create(id=1)

    all_photos = UploadedMaterial.objects.filter(material_type="photo").order_by("-id")
    baseline = CameraQueueItem.objects.filter(shelf=shelf, status="baseline").order_by("-id").first()
    pending_queue = CameraQueueItem.objects.filter(shelf=shelf, status="pending").order_by("id")
    history_queue = CameraQueueItem.objects.filter(shelf=shelf, status="processed").order_by("-id")[:5]
    recent_notifications = Notification.objects.select_related("letter__recipient").order_by("-sent_at")[:8]

    return render(request, "office/demo.html", {
        "shelf": shelf,
        "config": config,
        "all_photos": all_photos,
        "baseline": baseline,
        "pending_queue": pending_queue,
        "history_queue": history_queue,
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
        item = CameraQueueItem.objects.create(
            shelf=shelf,
            photo=photo,
            status=status,
            diff_summary="Ustawiono jako pierwsze zdjęcie bazowe" if status == "baseline" else "Oczekuje na konfrontację z bazą"
        )
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

        boxes = detect_frames(next_item.photo, photo_before=baseline.photo) or []
        zones = list(shelf.zones.select_related("recipient").all())
        db_logs = []
        mms_previews = []

        for box in boxes:
            x_pct = box["x"] / 10.0 if box["x"] > 100 else float(box["x"])
            y_pct = box["y"] / 10.0 if box["y"] > 100 else float(box["y"])
            w_pct = box["w"] / 10.0 if box["w"] > 100 else float(box["w"])
            h_pct = box["h"] / 10.0 if box["h"] > 100 else float(box["h"])

            frame = DetectedFrame.objects.create(
                shelf=shelf, frame_index=next_item.id,
                x_pct=x_pct, y_pct=y_pct, w_pct=w_pct, h_pct=h_pct,
                confidence=box.get("confidence", 0.9)
            )
            cx, cy = x_pct + w_pct / 2.0, y_pct + h_pct / 2.0
            default_zone = next(iter(zones), None)
            matched_zone = next(
                (z for z in zones if z.x_pct <= cx <= (z.x_pct + z.w_pct) and z.y_pct <= cy <= (z.y_pct + z.h_pct)),
                default_zone
            )
            rec = matched_zone.recipient if matched_zone else Recipient.objects.first()
            if rec:
                letter = Letter.objects.create(
                    frame=frame, recipient=rec,
                    due_date=timezone.localdate() + timedelta(days=7),
                    document_type="Nowa przesyłka", status="pending"
                )
                notif = _send_personalized_notification(letter, shelf, matched_zone, next_item.photo)
                db_logs.append(f"[{notif.channel.upper()}] {rec} -> {notif.content}")
                if notif.mms_image:
                    mms_previews.append({"recipient": str(rec), "url": f"/omnipost-portal/office/mms-crop/{notif.mms_image}/"})

        baseline.status = "processed"
        baseline.save()

        next_item.status = "baseline"
        next_item.diff_summary = f"Wykryto {len(boxes)} zmian względem poprzedniego (#{baseline.id})"
        next_item.save()

        return JsonResponse({
            "status": "ok",
            "baseline_id": baseline.photo.id,
            "current_id": next_item.photo.id,
            "boxes": boxes,
            "db_logs": db_logs,
            "mms_previews": mms_previews,
            "message": f"Skonfrontowano #{next_item.id} z #{baseline.id}. Zdjęcie #{next_item.id} jest teraz nową bazą!"
        })
    except Exception as e:
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
    raise Http404("Zdjęcie nie istnieje")


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
        total_pending += pending
        total_picked += delivered
        total_overdue += overdue
        recipient_docs.append({
            "recipient": r, "letters": letters,
            "pending": pending, "delivered": delivered, "overdue": overdue,
            "total": letters.count()
        })
    return render(request, "office/employee_documents.html", {
        "recipient_docs": recipient_docs,
        "total_pending": total_pending, "total_picked": total_picked, "total_overdue": total_overdue,
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
                Recipient.objects.create(
                    first_name=first_name, last_name=last_name,
                    email=email, phone=phone, preferred_channel=preferred_channel
                )
                messages.success(request, f"Dodano pracownika: {first_name} {last_name} (kanał: {preferred_channel.upper()})")
            else:
                messages.error(request, "Imię i nazwisko są wymagane.")
        elif action == "update_channel":
            rec = get_object_or_404(Recipient, id=request.POST.get("recipient_id"))
            rec.preferred_channel = request.POST.get("preferred_channel", "mms")
            rec.save()
            messages.success(request, f"Zmieniono kanał powiadomień dla {rec}: {rec.get_preferred_channel_display()}")
        elif action == "add_document":
            recipient_id = request.POST.get("recipient")
            doc_type = request.POST.get("doc_type", "Pismo ogólne").strip()
            due_date_str = request.POST.get("due_date")
            if recipient_id and due_date_str:
                recipient = get_object_or_404(Recipient, id=recipient_id)
                dummy_shelf = shelves.first()
                if dummy_shelf:
                    frame = DetectedFrame.objects.create(shelf=dummy_shelf, frame_index=0, confidence=1.0)
                    letter = Letter.objects.create(
                        frame=frame, recipient=recipient, document_type=doc_type,
                        due_date=datetime.strptime(due_date_str, "%Y-%m-%d").date(), status="pending"
                    )
                    zone = RecipientZone.objects.filter(shelf=dummy_shelf, recipient=recipient).first()
                    _send_personalized_notification(letter, dummy_shelf, zone, dummy_shelf.photo)
                    messages.success(request, f"Wystawiono dokument '{doc_type}' i wysłano powiadomienie ({recipient.get_preferred_channel_display()})")
        elif action == "upload_file":
            uploaded_file = request.FILES.get("file")
            shelf_id = request.POST.get("shelf")
            if uploaded_file and shelf_id:
                shelf = get_object_or_404(Shelf, id=shelf_id)
                material = UploadedMaterial.objects.create(
                    uploaded_by=request.user, material_type="photo",
                    file=uploaded_file, original_name=uploaded_file.name
                )
                shelf.photo = material
                shelf.save()
                messages.success(request, f"Wgrano plik i przypisano do półki: {shelf.name}")
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
        return JsonResponse({
            "status": "ok",
            "metrics": {"boxes_a": 0, "boxes_b": len(boxes)},
            "added": len(boxes), "removed": 0,
            "db_logs": [f"Wykryto {len(boxes)} różnic między obrazami"],
            "raw_a": [], "raw_b": boxes
        })
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
    data = [{
        "id": n.id,
        "channel": n.channel,
        "content": n.content,
        "mms_image": f"/omnipost-portal/office/mms-crop/{n.mms_image}/" if n.mms_image else "",
        "sent_at": n.sent_at.strftime("%Y-%m-%d %H:%M:%S"),
        "recipient": str(n.letter.recipient) if n.letter else "Nieznany"
    } for n in notifications]
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
        zone = RecipientZone.objects.create(
            shelf=shelf, recipient=recipient,
            name=data.get("name", recipient.first_name),
            x_pct=float(data.get("x_pct", 0)),
            y_pct=float(data.get("y_pct", 0)),
            w_pct=float(data.get("w_pct", 0)),
            h_pct=float(data.get("h_pct", 0))
        )
        return JsonResponse({"status": "ok", "id": zone.id})
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
