from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import UploadedMaterial
import shutil
import requests

@receiver(post_save, sender=UploadedMaterial)
def route_accepted_material(sender, instance, **kwargs):
    if instance.status != "accepted":
        return

    # 1. OBSŁUGA MODELU YOLO (.pt)
    if instance.material_type == "model" and instance.file.name.endswith(".pt"):
        dest = "/var/www/yolo-service/models/best.pt"
        try:
            with instance.file.open('rb') as src, open(dest, 'wb') as dst:
                shutil.copyfileobj(src, dst)
            requests.post("http://127.0.0.1:9000/reload", timeout=10)
            print(f"SUKCES: Wdrożono nowy model YOLO z pliku {instance.original_name}")
        except Exception as e:
            print(f"BŁĄD: Nie udało się wdrożyć modelu YOLO: {e}")

    # 2. OBSŁUGA ZDJĘCIA (Photo)
    elif instance.material_type == "photo":
        from office.models import Shelf
        # Sprawdzamy, czy to zdjęcie jest już przypisane do jakiejś półki
        if not instance.shelves.exists():
            # Tworzymy nową półkę dedykowaną dla tego zdjęcia
            Shelf.objects.create(
                name=f"Półka - {instance.original_name}",
                location="Wgrane przez studenta",
                photo=instance
            )
            print(f"SUKCES: Zdjęcie {instance.original_name} przypisane do nowej półki.")
