# Start: trenowanie modelu wykrywającego kartki

## 1. Zainstaluj Python i biblioteki

W terminalu, w tym folderze, uruchom:

```bash
python -m pip install ultralytics pandas matplotlib pyyaml
```

Jeśli komputer nie ma karty graficznej NVIDIA, trening może działać na CPU, ale wolniej.

## 2. Przygotuj zdjęcia i oznaczenia

Utwórz strukturę:

```text
dataset/
  data.yaml
  images/
    train/
    val/
  labels/
    train/
    val/
```

- `images/train` — zdjęcia do nauki.
- `images/val` — osobne zdjęcia do sprawdzania jakości w trakcie treningu.
- `labels/train` i `labels/val` — pliki `.txt` z ramkami dla odpowiednich zdjęć.

Oznacz zdjęcia w narzędziu do anotacji, np. CVAT, Label Studio albo Roboflow, wybierając eksport w formacie YOLO Detection. Każda widoczna kartka powinna mieć ramkę. Zasady oznaczania muszą być konsekwentne.

Przykład pliku `abc.txt` dla `abc.jpg`:

```text
0 0.51 0.44 0.20 0.65
0 0.72 0.50 0.13 0.60
```

To tylko przykład formatu, nie prawdziwe etykiety dla Twojego zdjęcia. Wartości to: `klasa x_środek y_środek szerokość wysokość`, wszystkie względem rozmiaru zdjęcia i w zakresie 0–1.

W `dataset/data.yaml` zostaw jedną klasę `kartka`. Jeśli używasz innych ścieżek, popraw je w tym pliku.

## 3. Uruchom trening

Z poziomu folderu projektu:

```bash
python train_compare.py --data dataset/data.yaml --epochs 50
```

Na próbę możesz użyć `--epochs 10`. Model startowy `yolo11n.pt` zostanie pobrany automatycznie przez Ultralytics, jeśli jest dostępny internet.

## 4. Gdzie są wyniki?

Skrypt zapisuje wyniki w `runs/organizer/trening/`, między innymi:

- `results.csv` — metryki walidacyjne po każdej epoce;
- `porownanie_epok.csv` — porównanie po 1, 10, 20 i 50 epokach (o ile zostały wykonane);
- pliki PNG z wykresami metryk;
- `weights/` — wagi modelu, w tym `best.pt`, `last.pt` oraz checkpointy z kolejnych epok, jeśli zapis się powiódł.

Ultralytics może nazwać/organizować katalogi nieco inaczej w zależności od wersji i konfiguracji.

## 5. Jak rozumieć metryki?

- **Precision** — jaka część wykryć modelu była poprawna. Niska wartość często oznacza fałszywe wykrycia.
- **Recall** — jaką część rzeczywistych kartek model znalazł. Niska wartość oznacza, że pomija kartki.
- **mAP50** — miara jakości detekcji przy kryterium IoU 0.50.
- **mAP50-95** — bardziej wymagająca średnia jakości detekcji dla różnych progów IoU.

Wartości są zwykle w zakresie 0–1; większe jest lepsze. Nie porównuj jedynie wyników na zdjęciach treningowych — oceniaj na walidacji i, na końcu, na osobnym zbiorze testowym.

## 6. Ważne, żeby porównanie było uczciwe

- Nie zmieniaj zdjęć walidacyjnych pomiędzy eksperymentami.
- Nie dziel klatek z tego samego filmu losowo między trening i walidację — podobne klatki mogą zawyżyć wynik. Lepiej przeznaczyć całe nagrania do osobnych zbiorów.
- Zacznij od kilkudziesięciu lub kilkuset różnorodnych, dobrze oznaczonych zdjęć, jeśli możesz je zebrać. Kilka zdjęć to za mało do wiarygodnej oceny.
- Epoka 1 i epoka 10 to etapy jednego treningu, nie niezależne modele. `results.csv` pokazuje, jak metryki zmieniały się w trakcie tego samego treningu.
- Liczba wykrytych ramek nie zawsze równa się liczbie kartek: kartka może zostać pominięta albo wykryta kilka razy. Dlatego trzeba ocenić również jakość ramek.

## 7. Testowanie na nowym zdjęciu

Po treningu:

```bash
yolo predict model=runs/organizer/trening/weights/best.pt source=moje_zdjecie.jpg save=True
```

Sprawdź obraz wynikowy w folderze utworzonym przez YOLO. Zwróć uwagę na pominięte kartki i fałszywe ramki.
