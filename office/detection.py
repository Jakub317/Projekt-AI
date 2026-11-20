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

PROXY_BASE = "http://192.168.65.254:8899/v1beta"


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
    parsed = json.loads(text_out)
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


def detect_via_apn(photo_after, config, photo_before=None):
    token = (config.apn_token or "").strip()
    if not token:
        raise RuntimeError("Brak klucza API (Token APN)!")

    parts = [{
        "text": (
            "Porównaj dwa zdjęcia regału (PRZED i PO). Znajdź NOWE kartki lub koperty na drugim zdjęciu. "
            "Zwróć wyłącznie JSON: {\"boxes\": [{\"x\": 100, \"y\": 200, \"w\": 150, \"h\": 120, \"confidence\": 0.95}]} "
            "w układzie 1000x800."
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

    models_to_try = ["gemini-flash-lite-latest", "gemini-flash-latest"]
    last_err = ""

    for model_name in models_to_try:
        url = f"{PROXY_BASE}/models/{model_name}:generateContent?key={token}"
        try:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw_resp = json.loads(resp.read().decode("utf-8"))
                text_out = raw_resp["candidates"]["content"]["parts"]["text"]
                return _parse_gemini_boxes(text_out)
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")[:180]
            last_err = f"HTTP {e.code} ({model_name}): {err_msg}"
            if e.code == 503:
                time.sleep(1.5)
                continue
            raise RuntimeError(last_err)
        except Exception as e:
            last_err = f"Błąd ({model_name}): {str(e)}"
            continue

    raise RuntimeError(last_err)


def detect_frames(photo_after, photo_before=None):
    from .models import DetectionConfig
    config = DetectionConfig.objects.first()
    if config and config.mode == "apn":
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
