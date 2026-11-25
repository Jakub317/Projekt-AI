def detect_frames(photo_after, photo_before=None):
    from .models import DetectionConfig
    config = DetectionConfig.objects.first()
    # Używaj Gemini TYLKO gdy tryb to 'apn' I jest klucz API
    use_gemini = (config and config.mode == "apn" and os.getenv("GOOGLE_API_KEY"))
    if use_gemini:
        return detect_via_apn(photo_after, config, photo_before=photo_before)
    return detect_local_diff(photo_before, photo_after)
