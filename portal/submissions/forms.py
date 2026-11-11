import os

from django import forms
from django.core.exceptions import ValidationError

from .models import UploadedMaterial

MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 25 MB

ALLOWED_BY_TYPE = {
    "photo": {".jpg", ".jpeg", ".png", ".webp"},
    "code": {".py", ".cpp", ".h", ".hpp", ".java", ".js", ".html", ".css", ".txt", ".csv"},
    "archive": {".zip"},
    "model": {".zip", ".pkl", ".h5", ".pt", ".onnx"},
    "other": {".pdf", ".txt", ".csv", ".zip"},
}


class MaterialUploadForm(forms.ModelForm):
    class Meta:
        model = UploadedMaterial
        fields = ("material_type", "file", "note")
        widgets = {
            "note": forms.Textarea(attrs={"rows": 3, "placeholder": "Opcjonalny opis (max 500 znaków)"}),
        }

    def clean_note(self):
        note = self.cleaned_data.get("note", "")
        if len(note) > 500:
            raise ValidationError("Opis może mieć maksymalnie 500 znaków.")
        return note

    def clean_file(self):
        f = self.cleaned_data["file"]
        if f.size > MAX_UPLOAD_SIZE:
            raise ValidationError(f"Plik jest za duży ({f.size // (1024*1024)} MB). Limit: 25 MB.")
        ext = os.path.splitext(f.name)[1].lower()
        if not ext:
            raise ValidationError("Plik musi mieć rozszerzenie.")
        return f

    def clean(self):
        cleaned = super().clean()
        f = cleaned.get("file")
        material_type = cleaned.get("material_type")
        if not f or not material_type:
            return cleaned
        ext = os.path.splitext(f.name)[1].lower()
        allowed = ALLOWED_BY_TYPE.get(material_type, set())
        if ext not in allowed:
            raise ValidationError(
                f"Rozszerzenie {ext} nie jest dozwolone dla typu '{material_type}'. "
                f"Dozwolone: {', '.join(sorted(allowed)) or 'brak'}."
            )
        return cleaned
