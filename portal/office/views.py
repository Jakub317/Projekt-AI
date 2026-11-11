import datetime
import requests
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages
from django.http import FileResponse, Http404
from django.core.files.storage import default_storage
from submissions.models import UploadedMaterial
from .models import Shelf, Recipient, DetectedFrame, Letter, Notification
from .detection import detect_frames


def _ensure_demo_data():
    if Recipient.objects.exists():
        return
    names = [("Anna","Kowalska"),("Jan","Nowak"),("Katarzyna","Wiśniewska"),
             ("Piotr","Zieliński"),("Marek","Lewandowski")]
    for fn, ln in names:
        Recipient.objects.create(first_name=fn, last_name=ln,
                                 email=f"{fn.lower()}@example.com",
                                 phone="+48 600 000 000")
    for i in range(3):
        Shelf.objects.create(name=f"Półka {chr(65+i)}", location="Magazyn A")


def _check_overdue():
    today = timezone.localdate()
    for letter in Letter.objects.filter(status="pending", due_date__lt=today):
        letter.status = "overdue"
        letter.save(update_fields=["status"])
        if not letter.notification_sent:
            Notification.objects.create(
                letter=letter, channel="sms",
                content=f"Pismo dla {letter.recipient} jest przeterminowane (termin: {letter.due_date})."
            )
            letter.notification_sent = True
            letter.save(update_fields=["notification_sent"])


def demo_office(request):
    _ensure_demo_data()
    if request.method == "POST":
        shelf = Shelf.objects.order_by("?").first()
        if shelf:
            frames = detect_frames(shelf.photo)
            recipients = list(Recipient.objects.all())
            for idx, f in enumerate(frames):
                frame = DetectedFrame.objects.create(
                    shelf=shelf, frame_index=idx,
                    x=f["x"], y=f["y"], w=f["w"], h=f["h"], confidence=f["confidence"]
                )
                rec = recipients[idx % len(recipients)] if recipients else None
                if rec:
                    Letter.objects.create(
                        frame=frame, recipient=rec,
                        due_date=timezone.localdate() + datetime.timedelta(days=7)
                    )
    _check_overdue()
    return render(request, "office/demo.html", {
        "shelves": Shelf.objects.prefetch_related("frames").all(),
        "letters": Letter.objects.select_related("frame__shelf", "recipient").all(),
        "recipients": Recipient.objects.all(),
        "stats": {
            "total": Letter.objects.count(),
            "pending": Letter.objects.filter(status="pending").count(),
            "delivered": Letter.objects.filter(status="delivered").count(),
            "overdue": Letter.objects.filter(status="overdue").count(),
        },
        "notifications": Notification.objects.order_by("-sent_at")[:10],
        "all_photos": UploadedMaterial.objects.filter(material_type="photo").order_by("-uploaded_at"),
    })


def public_photo(request, pk):
    m = UploadedMaterial.objects.filter(pk=pk, material_type="photo", status="accepted").first()
    if not m or not default_storage.exists(m.file.name):
        raise Http404()
    return FileResponse(
        default_storage.open(m.file.name, "rb"),
        content_type=m.mime_type or "image/jpeg",
    )


def upload_model(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return redirect("submissions:login")
        
    if request.method == "POST" and request.FILES.get("model_file"):
        file = request.FILES["model_file"]
        if not file.name.endswith(".pt"):
            messages.error(request, "Plik musi mieć rozszerzenie .pt")
            return redirect("office:demo")
            
        save_path = "/var/www/yolo-service/models/best.pt"
        try:
            with open(save_path, "wb+") as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            # Poinformuj serwis YOLO
            requests.post("http://127.0.0.1:9000/reload", timeout=10)
            messages.success(request, "Model YOLO został pomyślnie wgrany i załadowany!")
        except Exception as e:
            messages.warning(request, f"Plik zapisany, ale serwis YOLO nie odpowiedział: {e}")
            
    return redirect("office:demo")


# --- API do symulacji wysyłki SMS ---
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import random
import datetime
from django.utils import timezone

@csrf_exempt
def api_simulate_sms(request):
    if request.method == "POST":
        recipients = list(Recipient.objects.all())
        if not recipients:
            return JsonResponse({"error": "Brak pracowników w bazie"}, status=400)
            
        recipient = random.choice(recipients)
        shelf = Shelf.objects.order_by("?").first()
        
        # Tworzymy pismo (jeśli mamy półkę)
        due_date = timezone.localdate() + datetime.timedelta(days=7)
        if shelf:
            frame = DetectedFrame.objects.create(
                shelf=shelf, frame_index=99, 
                x=random.randint(0,100), y=random.randint(0,100), 
                w=50, h=50, confidence=0.99
            )
            doc_types = ["Pismo urzędowe", "Faktura VAT", "Korespondencja", "Paczka kurierska", "Pismo sądowe"]
            descs = ["Wezwanie do zapłaty zaległości.", "Faktura za usługi za poprzedni miesiąc.", "Umowa ramowa do podpisania.", "Wymagane potwierdzenie odbioru.", "Zawiadomienie o terminie rozprawy."]
            idx = random.randint(0, 4)
            letter = Letter.objects.create(
                frame=frame, recipient=recipient, due_date=due_date, status="pending",
                document_type=doc_types[idx], description=descs[idx]
            )
            # Tworzymy wpis w bazie o wysłanym SMS-ie
            content = f"Cześć {recipient.first_name}, na półce {shelf.name} czeka na Ciebie nowe pismo. Termin odbioru: {due_date}."
            Notification.objects.create(letter=letter, channel="sms", content=content)
        else:
            content = f"Cześć {recipient.first_name}, masz nowe pismo, ale nie ma jeszcze przypisanej półki."

        return JsonResponse({
            "status": "ok",
            "recipient": f"{recipient.first_name} {recipient.last_name}",
            "phone": recipient.phone or "+48 000 000 000",
            "shelf": shelf.name if shelf else "Brak",
            "content": content
        })
    return JsonResponse({"error": "Method not allowed"}, status=405)

from django.db.models import Count, Q, F, ExpressionWrapper, fields
from datetime import timedelta

def predict_office_stats():
    recipients = Recipient.objects.all()
    predictions = []
    
    for r in recipients:
        letters = r.letters.all()
        total = letters.count()
        
        if total == 0:
            continue
            
        delivered = letters.filter(status="delivered")
        delivered_count = delivered.count()
        overdue_count = letters.filter(status="overdue").count()
        
        # Średni czas odbioru (w dniach)
        avg_days = 0
        if delivered_count > 0:
            # Obliczamy różnicę między datą wystawienia a dostarczenia
            total_days = 0
            for l in delivered:
                if l.delivered_at and l.created_at:
                    delta = l.delivered_at - l.created_at
                    total_days += delta.days
            avg_days = round(total_days / delivered_count, 1)
        
        # Prosta predykcja ryzyka
        risk_level = "Niskie"
        risk_color = "#2a2"
        if overdue_count > 0 and overdue_count / total > 0.3:
            risk_level = "Wysokie"
            risk_color = "#c22"
        elif avg_days > 5.0:
            risk_level = "Średnie"
            risk_color = "#c90"
            
        # Sprawdzamy aktualnie oczekujące pisma
        pending = letters.filter(status="pending")
        late_pending = 0
        for p in pending:
            # Jeśli termin mija dzisiaj lub jutro, a pracownik ma średnio > 5 dni zwłoki
            if p.due_date <= timezone.localdate() + timedelta(days=2) and avg_days > 4:
                late_pending += 1

        predictions.append({
            "name": str(r),
            "total": total,
            "delivered": delivered_count,
            "overdue": overdue_count,
            "avg_days": avg_days,
            "risk_level": risk_level,
            "risk_color": risk_color,
            "late_pending": late_pending,
            "reliability": max(0, 100 - (overdue_count * 20) - int(avg_days * 5))
        })
        
    # Sortujemy od najbardziej ryzykownych
    predictions.sort(key=lambda x: x["reliability"])
    return predictions
