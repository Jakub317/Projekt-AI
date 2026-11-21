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

# POPRAWKA 1: Prawdziwy adres Google Gemini API zamiast martwego proxy
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def detect_local_diff(photo_before, photo_after):
    try:
        if photo_before and photo_after and default_storage.exists(photo_before.file.name) and default_storage.exists(photo_after.file.name):
            img_a = Image.open(default_storage.open(photo_before.file.name, "rb")).convert("RGB").resize((1000, 800))
            img_b = Image.open(default_storage.open(photo_after.file.name, "rb")).convert("RGB").resize((1000, 800))
            diff = ImageChops.difference(img_a, img_b).convert("L")
            boxes = []
            for col in range(1, 19):
                x0 = col * 50
                crop = diff.crop((x0, 120, x0 + 46, 680))
                mean_diff = ImageStat.Stat(crop).mean[0]
                if mean_diff > 7.5:
                    boxes.append({
                        "x": x0 + 4,
                        "y": 130,
                        "w": 38,
                        "h": 540,
                        "confidence": min(0.99, round(0.65 + (mean_diff / 120.0), 2)),
                    })
            return boxes[:14]
    except Exception:
        pass
    return []


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
        # 1. Wyczyść tekst z ewentualnych znaczników markdown
        clean_text = text_out.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        # 2. Spróbuj sparsować wyczyszczony tekst
        parsed = json.loads(clean_text)
        raw_list = parsed if isinstance(parsed, list) else parsed.get("boxes", [])
        out = []
        
        for item in raw_list:
            if isinstance(item, dict) and "x" in item:
                out.append({
                    "x": int(item.get("x", 0)),
                    "y": int(item.get("y", 0)),
                    "w": int(item.get("w", 100)),
                    "h": int(item.get("h", 100)),
                    "confidence": float(item.get("confidence", 0.92)),
                })
            elif isinstance(item, dict) and "box_2d" in item and len(item["box_2d"]) == 4:
                ymin, xmin, ymax, xmax = item["box_2d"]
                out.append({
                    "x": int(xmin),
                    "y": int(ymin * 0.8),
                    "w": int(xmax - xmin),
                    "h": int((ymax - ymin) * 0.8),
                    "confidence": 0.92,
                })
            elif isinstance(item, list) and len(item) == 4:
                ymin, xmin, ymax, xmax = item
                out.append({
                    "x": int(xmin),
                    "y": int(ymin * 0.8),
                    "w": int(xmax - xmin),
                    "h": int((ymax - ymin) * 0.8),
                    "confidence": 0.90,
                })
        return out
        
    except json.JSONDecodeError as e:
        # TO JEST KLUCZOWE: wypisze nam dokładnie, co zwróciło API, zamiast wysypywać serwer
        print(f"=== DEBUG GEMINI JSON ERROR ===")
        print(f"Błąd parsowania: {e}")
        print(f"Surowy tekst od API: {text_out}")
        print(f"===============================")
        return []
    except Exception as e:
        print(f"=== DEBUG GEMINI UNEXPECTED ERROR ===")
        print(f"Błąd: {e}")
        print(f"=====================================")
        return []
def detect_via_apn(photo_after, config, photo_before=None):
    # POPRAWKA 2: Najpierw sprawdzamy .env, potem bazę danych (dla kompatybilności)
    token = os.getenv("GOOGLE_API_KEY") or (config.apn_token or "").strip()
    if not token:
        raise RuntimeError("Brak klucza API! Dodaj GOOGLE_API_KEY do pliku .env lub ustaw Token APN w panelu admina.")

    parts = [{
        "text": (
            "Porównaj dwa zdjęcia regału (PRZED i PO). Znajdź NOWE kartki lub koperty na drugim zdjęciu. "
            "Zwróć wyłącznie JSON: {\"boxes\": [{\"x\": 100, \"y\": 200, \"w\": 150, \"h\": 120, \"confidence\": 0.95}]} "
            "w układzie 1000x800. Jeśli nie ma żadnych nowych obiektów, zwróć {\"boxes\": []}."
        )
    }]

    b64_a = _encode_image_b64(photo_before)
    if b64_a:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64_a}})

    b64_b = _encode_image_b64(photo_after)
    if b64_b:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64_b}})

    payload = json.dumps({
        "contents": [{"parts": parts}],
        "generationConfig": {"response_mime_type": "application/json"}
    }).encode("utf-8")

            # Jedyny aktualnie działający model (listopad 2026)
    models_to_try = ["gemini-3.8-flash"]
    last_err = ""
    max_retries = 3  # Więcej prób przy przeciążeniu

    for attempt in range(max_retries):
        for model_name in models_to_try:
            url = f"{GEMINI_BASE_URL}/models/{model_name}:generateContent?key={token}"
            try:
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=90) as resp:
                    raw_resp = json.loads(resp.read().decode("utf-8"))
                    candidates = raw_resp.get("candidates", [])
                    if not candidates:
                        raise RuntimeError("Brak kandydatów w odpowiedzi API")
                    
                    parts_resp = candidates[0].get("content", {}).get("parts", [])
                    if not parts_resp:
                        raise RuntimeError("Brak części w odpowiedzi API")
                        
                    text_out = parts_resp[0].get("text", "")
                    return _parse_gemini_boxes(text_out)
                    
            except urllib.error.HTTPError as e:
                err_msg = e.read().decode("utf-8", errors="ignore")[:180]
                last_err = f"HTTP {e.code} ({model_name}): {err_msg}"
                
                # Przy 503 (przeciążenie) lub 429 (rate limit) - czekamy i próbujemy ponownie
                if e.code in (503, 429):
                    wait_time = 3 * (attempt + 1)  # 3s, 6s, 9s - rosnąco
                    print(f"[GEMINI] Serwer przeciążony, czekam {wait_time}s przed próbą #{attempt+2}...")
                    time.sleep(wait_time)
                    break  # Wyjdź z wewnętrznej pętli, aby powtórzyć zewnętrzną
                raise RuntimeError(last_err)
                
            except Exception as e:
                last_err = f"Błąd ({model_name}): {str(e)}"
                continue

    # Jeśli wszystkie próby się nie powiodły, zwracamy pusty wynik zamiast wysypywać aplikację
    print(f"[GEMINI] Wszystkie próby nieudane: {last_err}. Przechodzę do lokalnej detekcji.")
    return detect_local_diff(photo_before, photo_after)
    last_err = ""

    for model_name in models_to_try:
        # POPRAWKA 3: Używamy prawdziwego URL Google zamiast PROXY_BASE
        url = f"{GEMINI_BASE_URL}/models/{model_name}:generateContent?key={token}"
        try:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw_resp = json.loads(resp.read().decode("utf-8"))
                # Bezpieczne wyciąganie tekstu z odpowiedzi Gemini
                candidates = raw_resp.get("candidates", [])
                if not candidates:
                    raise RuntimeError("Brak kandydatów w odpowiedzi API")
                
                parts_resp = candidates[0].get("content", {}).get("parts", [])
                if not parts_resp:
                    raise RuntimeError("Brak części w odpowiedzi API")
                    
                text_out = parts_resp[0].get("text", "")
                return _parse_gemini_boxes(text_out)
                
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")[:180]
            last_err = f"HTTP {e.code} ({model_name}): {err_msg}"
            if e.code == 503 or e.code == 429: # 429 = za dużo zapytań
                time.sleep(2.0)
                continue
            raise RuntimeError(last_err)
        except Exception as e:
            last_err = f"Błąd ({model_name}): {str(e)}"
            continue

    raise RuntimeError(f"Nie udało się połączyć z Gemini: {last_err}")


def detect_frames(photo_after, photo_before=None):
    from .models import DetectionConfig
    config = DetectionConfig.objects.first()
    
    # Jeśli w bazie jest ustawiony tryb "apn" LUB mamy klucz w .env, używamy Gemini
    use_gemini = (config and config.mode == "apn") or os.getenv("GOOGLE_API_KEY")
    
    if use_gemini:
        return detect_via_apn(photo_after, config, photo_before=photo_before)
    
    # Fallback do lokalnej detekcji różnic pikseli, jeśli nie ma klucza API
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