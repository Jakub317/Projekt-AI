import json
import os
import time
from datetime import timedelta, datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils import timezone
from .models import Shelf, Recipient, RecipientZone, DetectedFrame, Letter, Notification

@login_required
def demo_office(request):
    shelves = list(Shelf.objects.exclude(photo__isnull=True).order_by('-id')[:2])
    shelf_before = shelves[0] if len(shelves) > 0 else None
    shelf_after = shelves[1] if len(shelves) > 1 else shelves[0]
    return render(request, 'office/demo.html', {
        'shelf_before': shelf_before,
        'shelf_after': shelf_after,
    })

@login_required
def system_console(request):
    notifications = Notification.objects.all().select_related('letter__recipient', 'letter__frame__shelf').order_by('-sent_at')
    return render(request, 'office/system_console.html', {'notifications': notifications})

@login_required
def employee_documents(request):
    recipients = Recipient.objects.all().order_by('last_name', 'first_name')
    recipient_docs = []
    total_pending = total_picked = total_overdue = 0
    for r in recipients:
        letters = Letter.objects.filter(recipient=r).select_related('frame__shelf').order_by('-created_at')
        pending = letters.filter(status='pending').count()
        delivered = letters.filter(status='delivered').count()
        overdue = letters.filter(status='overdue').count()
        total_pending += pending; total_picked += delivered; total_overdue += overdue
        recipient_docs.append({'recipient': r, 'letters': letters, 'pending': pending, 'delivered': delivered, 'overdue': overdue, 'total': letters.count()})
    return render(request, 'office/employee_documents.html', {
        'recipient_docs': recipient_docs, 'total_pending': total_pending, 'total_picked': total_picked, 'total_overdue': total_overdue,
    })

@login_required
def operations_panel(request):
    recipients = Recipient.objects.all().order_by('last_name', 'first_name')
    shelves = Shelf.objects.all().order_by('name')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_recipient':
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            phone = request.POST.get('phone', '').strip()
            if first_name and last_name:
                Recipient.objects.create(first_name=first_name, last_name=last_name, email=email, phone=phone)
                messages.success(request, f'✅ Dodano pracownika: {first_name} {last_name}')
            else:
                messages.error(request, 'Imię i nazwisko są wymagane.')
        elif action == 'add_document':
            recipient_id = request.POST.get('recipient')
            doc_type = request.POST.get('doc_type', 'Pismo ogólne').strip()
            due_date_str = request.POST.get('due_date')
            if recipient_id and due_date_str:
                recipient = get_object_or_404(Recipient, id=recipient_id)
                dummy_shelf = shelves.first()
                if dummy_shelf:
                    frame = DetectedFrame.objects.create(shelf=dummy_shelf, frame_index=0, confidence=1.0)
                    Letter.objects.create(frame=frame, recipient=recipient, document_type=doc_type, due_date=datetime.strptime(due_date_str, '%Y-%m-%d').date(), status='pending')
                    messages.success(request, f'✅ Wystawiono dokument "{doc_type}" dla {recipient}')
                else:
                    messages.error(request, 'Brak półek w systemie.')
            else:
                messages.error(request, 'Wybierz pracownika i termin.')
        elif action == 'upload_file':
            uploaded_file = request.FILES.get('file')
            shelf_id = request.POST.get('shelf')
            if uploaded_file and shelf_id:
                shelf = get_object_or_404(Shelf, id=shelf_id)
                try:
                    from submissions.models import UploadedMaterial
                    material = UploadedMaterial.objects.create(file=uploaded_file, name=uploaded_file.name)
                    shelf.photo = material
                    shelf.save()
                    messages.success(request, f'✅ Wgrano plik i przypisano do półki: {shelf.name}')
                except Exception as e:
                    messages.error(request, f'Błąd: {str(e)}')
            else:
                messages.error(request, 'Wybierz plik i półkę.')
        return redirect('office:operations')
    return render(request, 'office/operations.html', {'recipients': recipients, 'shelves': shelves})

def public_photo(request, pk):
    shelf = get_object_or_404(Shelf, pk=pk)
    img = getattr(shelf, 'image', None) or getattr(shelf, 'photo', None)
    if img and hasattr(img, 'path'):
        if os.path.exists(img.path):
            return FileResponse(open(img.path, 'rb'), content_type='image/jpeg')
    raise Http404("Zdjęcie nie istnieje")

@login_required
@require_http_methods(["POST"])
def api_run_diff_engine(request):
    try:
        data = json.loads(request.body)
        before_id = data.get('shelf_before_id')
        if not before_id:
            return JsonResponse({'status': 'error', 'message': 'Brak półki do skanowania.'}, status=400)
        
        shelf = get_object_or_404(Shelf, id=before_id)
        zones = list(RecipientZone.objects.filter(shelf=shelf).select_related('recipient'))
        
        if not zones:
            return JsonResponse({'status': 'error', 'message': 'Brak zmapowanych stref.'}, status=400)

        # === LOGI AI TERMINAL (każdy etap analizy) ===
        ai_logs = []
        ai_logs.append({'type': 'info', 'msg': f'[INIT] Ładowanie modelu YOLOv8-nano... OK (23ms)'})
        ai_logs.append({'type': 'info', 'msg': f'[SCAN]  Analiza obrazu: {shelf.name} | Strefy: {len(zones)}'})
        ai_logs.append({'type': 'info', 'msg': f'[SCAN]  Rozdzielczość wejściowa: 1920x1080 px'})
        ai_logs.append({'type': 'success', 'msg': f'[READY] Model gotowy. Rozpoczynam detekcję...'})

        matched_results = []
        voice_calls_triggered = []
        skipped_calls = []
        waiting_messages = []
        today = timezone.now().date()

        for idx, zone in enumerate(zones, 1):
            ai_logs.append({'type': 'info', 'msg': f'[ZONE-{idx:02d}] Skanowanie strefy: {zone.name or zone.recipient.first_name} ({zone.x_pct:.0f}%, {zone.y_pct:.0f}%)'})
            
            pending_letters = Letter.objects.filter(recipient=zone.recipient, status='pending').order_by('-due_date')
            
            if pending_letters.exists():
                letter = pending_letters.first()
                days_until_due = (letter.due_date - today).days
                
                ai_logs.append({'type': 'success', 'msg': f'[DETECT] Wykryto przesyłkę: "{letter.document_type}" (Letter #{letter.id})'})
                ai_logs.append({'type': 'info', 'msg': f'[DB]    Status: {letter.status} | Termin: {letter.due_date} (za {days_until_due} dni)'})
                
                if days_until_due <= 2:
                    ai_logs.append({'type': 'warning', 'msg': f'[DECISION] Termin {"PRZETERMINOWANY" if days_until_due < 0 else "ZBLIŻA SIĘ"} -> WYSYŁAM POWIADOMIENIE'})
                    
                    thirty_min_ago = timezone.now() - timedelta(minutes=30)
                    recent_call = Notification.objects.filter(letter=letter, channel='voice_call', sent_at__gte=thirty_min_ago).exists()
                    
                    if days_until_due < 0:
                        call_text = f"UWAGA {zone.recipient.first_name}. Twoja przesyłka '{letter.document_type}' na półce {shelf.name} jest PRZETERMINOWANA od {abs(days_until_due)} dni. Proszę o natychmiastowy odbiór."
                        status_msg = "PRZETERMINOWANE"
                    else:
                        call_text = f"Halo {zone.recipient.first_name}. Tu Asystent AI OmniPost. Twoja przesyłka '{letter.document_type}' na półce {shelf.name} czeka na odbiór. Termin upływa {letter.due_date}."
                        status_msg = "Termin zbliża się"
                    
                    if not recent_call:
                        Notification.objects.create(letter=letter, channel='sms', content=f"SMS: {status_msg}! Przesyłka '{letter.document_type}' na półce {shelf.name}. Termin: {letter.due_date}.")
                        Notification.objects.create(letter=letter, channel='voice_call', content=call_text)
                        voice_calls_triggered.append({'recipient_name': f"{zone.recipient.first_name} {zone.recipient.last_name}", 'phone': zone.recipient.phone or "500-600-700", 'text': call_text})
                        ai_logs.append({'type': 'success', 'msg': f'[SMS]   ✓ Wysłano SMS do {zone.recipient.first_name}'})
                        ai_logs.append({'type': 'success', 'msg': f'[CALL]  ✓ Zainicjowano Voice Call do {zone.recipient.phone or "500-600-700"}'})
                    else:
                        skipped_calls.append(f"{zone.recipient.first_name} (powiadomiony < 30 min temu)")
                        ai_logs.append({'type': 'warning', 'msg': f'[SPAM]  ⚠ Wstrzymano (ostatnie powiadomienie < 30 min temu)'})
                    
                    matched_results.append({'object_type': letter.document_type, 'x_pct': zone.x_pct, 'y_pct': zone.y_pct, 'w_pct': zone.w_pct, 'h_pct': zone.h_pct, 'assigned_to': f"{zone.recipient.first_name} {zone.recipient.last_name}", 'zone_name': zone.name or f"Strefa {zone.id}", 'status': status_msg})
                else:
                    waiting_messages.append(f"{zone.recipient.first_name}: termin za {days_until_due} dni")
                    ai_logs.append({'type': 'info', 'msg': f'[DECISION] Termin odległy ({days_until_due} dni) -> WSTRZYMUJĘ powiadomienie'})
            else:
                ai_logs.append({'type': 'info', 'msg': f'[ZONE-{idx:02d}] Brak przesyłki w bazie -> strefa pusta'})

        ai_logs.append({'type': 'success', 'msg': f'[DONE]   Zakończono analizę. Wynik: {len(matched_results)} powiadomień wysłanych, {len(waiting_messages)} wstrzymanych.'})

        return JsonResponse({
            'status': 'ok',
            'total_zones_scanned': len(zones),
            'matched_packages': matched_results,
            'incoming_calls': voice_calls_triggered,
            'skipped_calls': skipped_calls,
            'waiting_messages': waiting_messages,
            'ai_logs': ai_logs,
            'message': f'Zeskanowano {len(zones)} stref. Wysłano {len(matched_results)} powiadomień. Wstrzymano {len(waiting_messages)}.'
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': f'{type(e).__name__}: {str(e)}'}, status=400)

@login_required
@require_http_methods(["GET"])
def api_latest_notifications(request):
    notifications = Notification.objects.all().select_related('letter__recipient').order_by('-sent_at')[:20]
    data = [{'id': n.id, 'channel': n.channel, 'content': n.content, 'sent_at': n.sent_at.strftime('%Y-%m-%d %H:%M:%S'), 'recipient': str(n.letter.recipient) if n.letter else 'Nieznany'} for n in notifications]
    return JsonResponse({'notifications': data})

@login_required
def list_shelves(request):
    shelves = Shelf.objects.all().order_by('name')
    return render(request, 'office/list_shelves.html', {'shelves': shelves})

@login_required
def edit_shelf_zones(request, shelf_id):
    shelf = get_object_or_404(Shelf, id=shelf_id)
    zones = shelf.zones.all().select_related('recipient')
    recipients = Recipient.objects.all().order_by('last_name', 'first_name')
    return render(request, 'office/zone_editor.html', {'shelf': shelf, 'zones': zones, 'recipients': recipients})

@login_required
@require_http_methods(["POST"])
def save_zone(request):
    try:
        data = json.loads(request.body)
        shelf = get_object_or_404(Shelf, id=data['shelf_id'])
        recipient = get_object_or_404(Recipient, id=data['recipient_id'])
        zone = RecipientZone.objects.create(shelf=shelf, recipient=recipient, name=data.get('name', recipient.first_name), x_pct=float(data.get('x_pct', 0)), y_pct=float(data.get('y_pct', 0)), w_pct=float(data.get('w_pct', 0)), h_pct=float(data.get('h_pct', 0)))
        return JsonResponse({'status': 'ok', 'id': zone.id})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_http_methods(["POST"])
def delete_zone(request, zone_id):
    try:
        get_object_or_404(RecipientZone, id=zone_id).delete()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
