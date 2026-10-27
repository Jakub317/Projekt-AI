from pathlib import Path
from ultralytics import YOLO

# Folder, w którym znajduje się ten skrypt
PROJECT_DIR = Path(__file__).resolve().parent

# Ścieżki względne względem folderu projektu
MODEL_PATH = PROJECT_DIR / "runs" / "organizer" / "trening" / "weights" / "best.pt"
IMAGES_PATH = PROJECT_DIR / "dataset" / "images" / "val"
OUTPUT_DIR = PROJECT_DIR / "predicts"

# Sprawdź, czy wymagane pliki i foldery istnieją
if not MODEL_PATH.is_file():
    raise FileNotFoundError(
        f"Nie znaleziono modelu: {MODEL_PATH}\n"
        "Najpierw uruchom trening albo popraw ścieżkę do best.pt."
    )

if not IMAGES_PATH.is_dir():
    raise FileNotFoundError(
        f"Nie znaleziono folderu ze zdjęciami: {IMAGES_PATH}"
    )

# Wczytaj model
model = YOLO(str(MODEL_PATH))

# Wykonaj predykcję i zapisz obrazy z ramkami
wyniki = model.predict(
    source=str(IMAGES_PATH),
    save=True,
    conf=0.25,
    project=str(OUTPUT_DIR),
    name="moje_testy",
    exist_ok=True
)

# Wyświetl wyniki
for wynik in wyniki:
    print(f"{wynik.path} | Wykryte kartki: {len(wynik.boxes)}")

print(f"\nWyniki zapisano w: {OUTPUT_DIR / 'moje_testy'}")
