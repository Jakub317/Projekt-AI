import base64
import io
import json
import os
import random
import time
import urllib.error
import urllib.request
from PIL import Image, ImageChops, ImageStat
from django.conf import settings
from django.core.files.storage import default_storage

# Prawdziwy adres Google Gemini API
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def detect_local_diff(photo_before, photo_after):
    """
    Fallback: Detekcja różnic z wyrównywaniem perspektywy na podstawie fiducial markers.
    (Używana tylko gdy nie ma zdefiniowanych stref w bazie).
    """
    try:
        import cv2
        import numpy as np
        
        if photo_before and photo_after and default_storage.exists(photo_before.file.name) and default_storage.exists(photo_after.file.name):
            img_a = Image.open(default_storage.open(photo_before.file.name, "rb")).convert("RGB").resize((1000, 800))
            img_b = Image.open(default_storage.open(photo_after.file.name, "rb")).convert("RGB").resize((1000, 800))
            
            img_a_cv = cv2.cvtColor(np.array(img_a), cv2.COLOR_RGB2BGR)
            img_b_cv = cv2.cvtColor(np.array(img_b), cv2.COLOR_RGB2BGR)
            
            markers_a = find_fiducial_markers(img_a_cv)
            markers_b = find_fiducial_markers(img_b_cv)
            
            if markers_a and markers_b and len(markers_a) >= 3 and len(markers_b) >= 3:
                pts_a = np.float32([m['center'] for m in markers_a[:4]])
                pts_b = np.float32([m['center'] for m in markers_b[:4]])
                
                M = cv2.getPerspectiveTransform(pts_b, pts_a)
                img_b_aligned = cv2.warpPerspective(img_b_cv, M, (img_b_cv.shape[1], img_b_cv.shape[0]))
                
                img_b_aligned_rgb = cv2.cvtColor(img_b_aligned, cv2.COLOR_BGR2RGB)
                img_b_aligned_pil = Image.fromarray(img_b_aligned_rgb)
                
                diff = ImageChops.difference(img_a, img_b_aligned_pil).convert("L")
            else:
                diff = ImageChops.difference(img_a, img_b).convert("L")
            
            boxes = []
            for col in range(1, 19):
                x0 = col * 50
                crop = diff.crop((x0, 120, x0 + 46, 680))
                mean_diff = ImageStat.Stat(crop).mean[0]
                if mean_diff > 7.5:
                    boxes.append({
                        "x": x0 + 4, "y": 130, "w": 38, "h": 540,
                        "confidence": min(0.99, round(0.65 + (mean_diff / 120.0), 2)),
                    })
            return boxes[:14]
    except ImportError:
        pass
    except Exception as e:
        print(f"[ERROR] Detekcja z wyrównywaniem nie powiodła się: {e}")
    return []


def detect_zone_changes(photo_before, photo_after, zones):
    """
    NOWA FUNKCJA: Porównuje TYLKO zdefiniowane strefy (RecipientZone) między dwoma zdjęciami.
    Zwraca listę zmian z slot_number i recipient.
    """
    try:
        if not photo_before or not photo_after:
            return []
        
        if not default_storage.exists(photo_before.file.name) or not default_storage.exists(photo_after.file.name):
            return []
        
        img_a = Image.open(default_storage.open(photo_before.file.name, "rb")).convert("RGB")
        img_b = Image.open(default_storage.open(photo_after.file.name, "rb")).convert("RGB")
        
        width_a, height_a = img_a.size
        
        changes = []
        
        for zone in zones:
            if not zone.slot_number:
                continue  # Pomiń strefy bez slot_number
            
            # Oblicz współrzędne strefy w pikselach
            x1 = int((zone.x_pct / 100.0) * width_a)
            y1 = int((zone.y_pct / 100.0) * height_a)
            x2 = int(((zone.x_pct + zone.w_pct) / 100.0) * width_a)
            y2 = int(((zone.y_pct + zone.h_pct) / 100.0) * height_a)
            
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(width_a, x2)
            y2 = min(height_a, y2)
            
            if x2 <= x1 or y2 <= y1:
                continue
            
            # Wytnij strefę z obu zdjęć
            crop_a = img_a.crop((x1, y1, x2, y2))
            crop_b = img_b.crop((x1, y1, x2, y2))
            
            # Porównaj różnice
            diff = ImageChops.difference(crop_a, crop_b).convert("L")
            mean_diff = ImageStat.Stat(diff).mean[0]
            
            # Jeśli różnica > próg, wykryto zmianę
            if mean_diff > 10.0:
                changes.append({
                    "slot_number": zone.slot_number,
                    "recipient": str(zone.recipient) if zone.recipient else "Nieprzypisany",
                    "recipient_id": zone.recipient.id if zone.recipient else None,
                    "zone_name": zone.name or f"Slot {zone.slot_number}",
                    "x_pct": zone.x_pct,
                    "y_pct": zone.y_pct,
                    "w_pct": zone.w_pct,
                    "h_pct": zone.h_pct,
                    "confidence": min(0.99, round(0.70 + (mean_diff / 150.0), 2)),
                    "mean_diff": mean_diff
                })
        
        return changes
    except Exception as e:
        print(f"[ERROR] detect_zone_changes: {e}")
        return []


def find_fiducial_markers(img_cv):
    import cv2
    import numpy as np
    
    hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)
    lower_red1 = np.array([0, 100, 100])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 100, 100])
    upper_red2 = np.array([180, 255, 255])
    
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = mask1 + mask2
    
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    markers = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if 50 < area < 2000:
            M = cv2.moments(cnt)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                markers.append({'center': (cx, cy), 'area': area})
    
    if len(markers) >= 4:
        markers.sort(key=lambda m: (m['center'][1], m['center'][0]))
        top_two = sorted(markers[:2], key=lambda m: m['center'][0])
        bottom_two = sorted(markers[-2:], key=lambda m: m['center'][0])
        markers = top_two + bottom_two
    
    return markers


def _encode_image_b64(photo):
    if not photo or not default_storage.exists(photo.file.name):
        return None
    img = Image.open(default_storage.open(photo.file.name, "rb")).convert("RGB")
    img.thumbnail((640, 640))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _parse_gemini_boxes(text_out):
    try:
        clean_text = text_out.strip()
        if clean_text.startswith("```json"): clean_text = clean_text[7:]
        if clean_text.startswith("```"): clean_text = clean_text[3:]
        if clean_text.endswith("```"): clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        parsed = json.loads(clean_text)
        raw_list = parsed if isinstance(parsed, list) else parsed.get("boxes", [])
        out = []
        
        for item in raw_list:
            if isinstance(item, dict) and "x" in item:
                out.append({"x": int(item.get("x", 0)), "y": int(item.get("y", 0)),
                            "w": int(item.get("w", 100)), "h": int(item.get("h", 100)),
                            "confidence": float(item.get("confidence", 0.92))})
            elif isinstance(item, dict) and "box_2d" in item and len(item["box_2d"]) == 4:
                ymin, xmin, ymax, xmax = item["box_2d"]
                out.append({"x": int(xmin), "y": int(ymin * 0.8), "w": int(xmax - xmin),
                            "h": int((ymax - ymin) * 0.8), "confidence": 0.92})
            elif isinstance(item, list) and len(item) == 4:
                ymin, xmin, ymax, xmax = item
                out.append({"x": int(xmin), "y": int(ymin * 0.8), "w": int(xmax - xmin),
                            "h": int((ymax - ymin) * 0.8), "confidence": 0.90})
        return out
    except json.JSONDecodeError as e:
        print(f"=== DEBUG GEMINI JSON ERROR ===\nBłąd: {e}\nTekst: {text_out}\n===============================")
        return []
    except Exception as e:
        print(f"=== DEBUG GEMINI UNEXPECTED ERROR ===\nBłąd: {e}\n=====================================")
        return []


def detect_via_apn(photo_after, config, photo_before=None):
    token = os.getenv("GOOGLE_API_KEY") or (config.apn_token or "").strip()
    if not token:
        raise RuntimeError("Brak klucza API! Dodaj GOOGLE_API_KEY do pliku .env.")

    parts = [{"text": "Porównaj dwa zdjęcia regału. Znajdź NOWE kartki lub koperty. Zwróć wyłącznie JSON: {\"boxes\": [{\"x\": 100, \"y\": 200, \"w\": 150, \"h\": 120, \"confidence\": 0.95}]}. Jeśli brak, zwróć {\"boxes\": []}."}]

    b64_a = _encode_image_b64(photo_before)
    if b64_a: parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64_a}})

    b64_b = _encode_image_b64(photo_after)
    if b64_b: parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64_b}})

    payload = json.dumps({"contents": [{"parts": parts}], "generationConfig": {"response_mime_type": "application/json"}}).encode("utf-8")

    models_to_try = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
    last_err = ""
    
    for model_name in models_to_try:
        url = f"{GEMINI_BASE_URL}/models/{model_name}:generateContent?key={token}"
        try:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw_resp = json.loads(resp.read().decode("utf-8"))
                candidates = raw_resp.get("candidates", [])
                if not candidates: raise RuntimeError("Brak kandydatów w odpowiedzi API")
                
                parts_resp = candidates[0].get("content", {}).get("parts", [])
                if not parts_resp: raise RuntimeError("Brak części w odpowiedzi API")
                    
                return _parse_gemini_boxes(parts_resp[0].get("text", ""))
                
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code} ({model_name}): {e.read().decode('utf-8', errors='ignore')[:180]}"
            if e.code in (503, 429):
                time.sleep(3.0)
                continue
            raise RuntimeError(last_err)
        except Exception as e:
            last_err = f"Błąd ({model_name}): {str(e)}"
            continue

    print(f"[GEMINI] Wszystkie próby nieudane: {last_err}. Przechodzę do lokalnej detekcji.")
    return detect_local_diff(photo_before, photo_after)


def detect_frames(photo_after, photo_before=None):
    from .models import DetectionConfig
    config = DetectionConfig.objects.first()
    use_gemini = (config and config.mode == "apn")
    
    if use_gemini:
        return detect_via_apn(photo_after, config, photo_before=photo_before)
    return detect_local_diff(photo_before, photo_after)


def crop_zone_for_mms(photo, zone):
    if not photo or not zone or not default_storage.exists(photo.file.name):
        return ""
    try:
        img = Image.open(default_storage.open(photo.file.name, "rb")).convert("RGB")
        w, h = img.size
        left = max(0, int((zone.x_pct / 100.0) * w))
        top = max(0, int((zone.y_pct / 100.0) * h))
        right = min(w, int(((zone.x_pct + zone.w_pct) / 100.0) * w))
        bottom = min(h, int(((zone.y_pct + zone.h_pct) / 100.0) * h))
        if right <= left or bottom <= top:
            return ""
        cropped = img.crop((left, top, right, bottom))
        rel_dir = "mms_crops"
        abs_dir = os.path.join(settings.MEDIA_ROOT, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)
        filename = f"mms_z{zone.id}_p{photo.id}_{random.randint(1000,9999)}.jpg"
        cropped.save(os.path.join(abs_dir, filename), format="JPEG", quality=88)
        return f"{rel_dir}/{filename}"
    except Exception:
        return ""


def ocr_pile_image(photo):
    token = os.getenv("GOOGLE_API_KEY")
    if not token:
        raise Exception("Brak klucza GOOGLE_API_KEY w zmiennych środowiskowych (.env)")

    b64_img = _encode_image_b64(photo)
    if not b64_img:
        raise Exception("Nie można odczytać lub zakodować zdjęcia")

    prompt = (
        "Przeanalizuj zdjęcie sterty pism/przesyłek. "
        "Dla KAŻDEJ widocznej przesyłki wyciągnij następujące dane i zwróć je w formacie JSON: "
        "{\"items\": [{\"recipient_name\": \"Imię Nazwisko\", \"sender\": \"Nadawca\", \"tracking_number\": \"Numer przesyłki\", \"document_type\": \"Typ dokumentu\", \"document_date\": \"RRRR-MM-DD\", \"confidence\": 0.95}]}. "
        "Jeśli brak przesyłek, zwróć {\"items\": []}. Zwróć TYLKO poprawny JSON."
    )

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }).encode("utf-8")

    model_name = "gemini-1.5-flash"
    url = f"{GEMINI_BASE_URL}/models/{model_name}:generateContent?key={token}"
    
    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw_resp = json.loads(resp.read().decode("utf-8"))
            candidates = raw_resp.get("candidates", [])
            if not candidates: raise RuntimeError("Brak kandydatów w odpowiedzi API")
            
            parts_resp = candidates[0].get("content", {}).get("parts", [])
            if not parts_resp: raise RuntimeError("Brak części w odpowiedzi API")
                
            text_out = parts_resp[0].get("text", "").strip()
            
            if text_out.startswith("```json"): text_out = text_out[7:]
            if text_out.startswith("```"): text_out = text_out[3:]
            if text_out.endswith("```"): text_out = text_out[:-3]
            text_out = text_out.strip()
            
            parsed = json.loads(text_out)
            return parsed.get("items", [])
            
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', errors='ignore')[:180]}")
    except Exception as e:
        raise RuntimeError(f"Błąd OCR: {str(e)}")

