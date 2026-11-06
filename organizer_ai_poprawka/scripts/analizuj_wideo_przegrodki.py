from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import cv2
from ultralytics import YOLO


# Wstepne obszary 8 przegródek dopasowane do przeslanego nagrania 1080x1920.
# Wspolrzedne sa znormalizowane (0.0-1.0), wiec skrypt dziala tez przy
# innej rozdzielczosci, o ile kadr i polozenie kamery pozostana takie same.
# Kolejnosc: od lewej do prawej. W razie potrzeby zmien wartosci w tym pliku.
DEFAULT_ROIS = [
    {"id": "1", "x1": 0.0000, "y1": 0.360, "x2": 0.1111, "y2": 0.665},
    {"id": "2", "x1": 0.1111, "y1": 0.360, "x2": 0.2176, "y2": 0.665},
    {"id": "3", "x1": 0.2176, "y1": 0.360, "x2": 0.3565, "y2": 0.665},
    {"id": "4", "x1": 0.3565, "y1": 0.360, "x2": 0.4722, "y2": 0.665},
    {"id": "5", "x1": 0.4722, "y1": 0.360, "x2": 0.6389, "y2": 0.665},
    {"id": "6", "x1": 0.6389, "y1": 0.360, "x2": 0.7639, "y2": 0.665},
    {"id": "7", "x1": 0.7639, "y1": 0.360, "x2": 0.8981, "y2": 0.665},
    {"id": "8", "x1": 0.8981, "y1": 0.360, "x2": 1.0000, "y2": 0.665},
]


def load_rois(path: Path | None):
    if path is None or not path.exists():
        return DEFAULT_ROIS
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if len(data) != 8:
        raise ValueError("Plik ROI musi zawierac dokladnie 8 przegródek.")
    return data


def pixel_roi(roi, width, height):
    return (
        int(roi["x1"] * width),
        int(roi["y1"] * height),
        int(roi["x2"] * width),
        int(roi["y2"] * height),
    )


def motion_ratio(previous, current):
    """Szacuje ruch w ROI. To wskazowka zasloniecia, nie pewny detektor dloni."""
    if previous is None:
        return 0.0
    a = cv2.cvtColor(previous, cv2.COLOR_BGR2GRAY)
    b = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
    a = cv2.GaussianBlur(a, (5, 5), 0)
    b = cv2.GaussianBlur(b, (5, 5), 0)
    diff = cv2.absdiff(a, b)
    _, mask = cv2.threshold(diff, 24, 255, cv2.THRESH_BINARY)
    return cv2.countNonZero(mask) / mask.size if mask.size else 0.0


def fmt_time(seconds):
    ms = int(seconds * 1000)
    return f"{ms // 3600000:02d}:{(ms // 60000) % 60:02d}:{(ms % 60000) / 1000:06.3f}"


def main():
    parser = argparse.ArgumentParser(
        description="Analiza zmian kartek w 8 stalych przegrodkach."
    )
    parser.add_argument("--video", "-v", default="videos/nagranie.mp4")
    parser.add_argument("--model", "-m", default="model/best.pt")
    parser.add_argument("--output", "-o", default="results_przegrodki")
    parser.add_argument("--roi-config", default="rois.json",
                        help="Opcjonalny plik JSON z granicami przegródek.")
    parser.add_argument("--conf", type=float, default=0.45)
    parser.add_argument("--every", type=int, default=5)
    parser.add_argument("--confirm", type=int, default=4,
                        help="Liczba kolejnych analiz potwierdzajacych zmiane.")
    parser.add_argument("--motion-threshold", type=float, default=0.055,
                        help="Prog ruchu w ROI; domyslnie 0.055 (5.5%% pikseli).")
    parser.add_argument("--motion-hold", type=int, default=8,
                        help="Ile analiz po wykryciu ruchu traktowac ROI jako zasloniete.")
    parser.add_argument("--show-rois", action="store_true",
                        help="Zapisuje pierwsza klatke z narysowanymi ROI i konczy.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    video_path = (root / args.video).resolve()
    model_path = (root / args.model).resolve()
    output_dir = (root / args.output).resolve()
    roi_path = (root / args.roi_config).resolve()

    if not video_path.is_file():
        raise FileNotFoundError(f"Nie znaleziono filmu: {video_path}")
    if not model_path.is_file():
        raise FileNotFoundError(f"Nie znaleziono modelu: {model_path}")
    if args.every < 1 or args.confirm < 1 or args.motion_hold < 0:
        raise ValueError("--every i --confirm musza byc >= 1, a --motion-hold >= 0")

    rois = load_rois(roi_path if roi_path.exists() else None)
    output_dir.mkdir(parents=True, exist_ok=True)
    events_dir = output_dir / "events"
    events_dir.mkdir(exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Nie mozna otworzyc filmu: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    first_ok, first_frame = cap.read()
    if not first_ok:
        cap.release()
        raise RuntimeError("Film nie zawiera klatek.")
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    roi_pixels = [pixel_roi(r, width, height) for r in rois]
    if args.show_rois:
        preview = first_frame.copy()
        for roi, (x1, y1, x2, y2) in zip(rois, roi_pixels):
            cv2.rectangle(preview, (x1, y1), (x2, y2), (0, 255, 255), 3)
            cv2.putText(preview, f"PRZEGRODKA {roi['id']}", (x1 + 4, y1 + 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
            cv2.putText(preview, f"PRZEGRODKA {roi['id']}", (x1 + 4, y1 + 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.imwrite(str(output_dir / "kalibracja_roi.jpg"), preview)
        cap.release()
        print(f"Zapisano podglad ROI: {output_dir / 'kalibracja_roi.jpg'}")
        print("Sprawdz, czy kazdy prostokat obejmuje wnetrze jednej przegródki.")
        return

    model = YOLO(str(model_path))
    annotated_path = output_dir / "annotated_video.mp4"
    csv_path = output_dir / "raport.csv"
    writer = cv2.VideoWriter(
        str(annotated_path),
        cv2.VideoWriter_fourcc(*"avc1"),
        fps,
        (width, height)
    )

    if not writer.isOpened():
        writer = cv2.VideoWriter(
            str(annotated_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (width, height)
        )
    if not writer.isOpened():
        cap.release()
        raise RuntimeError("Nie udalo sie utworzyc wyjsciowego MP4.")

    # Stan kazdej przegródki. Punkt odniesienia ustalamy na pierwszej analizowanej klatce.
    states = {
        r["id"]: {
            "occupied": None, "pending": None, "count": 0,
            "motion_left": 0, "previous_crop": None
        } for r in rois
    }
    baseline_ready = False
    events = []
    frame_index = 0
    analyzed = 0
    event_id = 0
    last_frame = first_frame.copy()
    latest_boxes = []
    latest_confs = []
    latest_roi_motion = {}

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            if frame_index % args.every == 0:
                analyzed += 1
                timestamp = frame_index / fps
                result = model.predict(frame, conf=args.conf, verbose=False)[0]
                boxes, confs = [], []
                if result.boxes is not None:
                    for item in result.boxes:
                        boxes.append(tuple(float(v) for v in item.xyxy[0].cpu().tolist()))
                        confs.append(float(item.conf[0].cpu()))
                latest_boxes, latest_confs = boxes, confs

                for roi, (x1, y1, x2, y2) in zip(rois, roi_pixels):
                    rid = roi["id"]
                    state = states[rid]
                    crop = frame[y1:y2, x1:x2]
                    ratio = motion_ratio(state["previous_crop"], crop)
                    state["previous_crop"] = crop.copy()

                    if ratio >= args.motion_threshold:
                        state["motion_left"] = args.motion_hold
                    elif state["motion_left"] > 0:
                        state["motion_left"] -= 1
                    occluded = state["motion_left"] > 0
                    latest_roi_motion[rid] = (ratio, occluded)

                    # Kartka przypisana do przegródki, jesli srodek detekcji lezy w jej ROI.
                    detected = False
                    for box in boxes:
                        cx = (box[0] + box[2]) / 2
                        cy = (box[1] + box[3]) / 2
                        if x1 <= cx <= x2 and y1 <= cy <= y2:
                            detected = True
                            break

                    if not baseline_ready:
                        state["occupied"] = detected
                        continue

                    # Podczas ruchu/mozliwego zasloniecia nie zmieniamy stanu i zerujemy
                    # licznik potwierdzania. To ogranicza falszywe usuniecia przy sieganiu reka.
                    if occluded:
                        state["pending"] = None
                        state["count"] = 0
                        continue

                    if detected == state["occupied"]:
                        state["pending"] = None
                        state["count"] = 0
                        continue

                    if state["pending"] == detected:
                        state["count"] += 1
                    else:
                        state["pending"] = detected
                        state["count"] = 1

                    if state["count"] >= args.confirm:
                        event_id += 1
                        event_type = "DODANIE" if detected else "USUNIECIE"
                        event = {
                            "id": event_id,
                            "przegrodka": rid,
                            "typ": event_type,
                            "czas_sekundy": round(timestamp, 3),
                            "czas_filmu": fmt_time(timestamp),
                        }
                        events.append(event)
                        stem = f"zdarzenie_{event_id:04d}_{event_type.lower()}_przegrodka_{rid}"
                        cv2.imwrite(str(events_dir / f"{stem}_po.jpg"), frame)
                        cv2.imwrite(str(events_dir / f"{stem}_wycinek.jpg"), crop)
                        print(f"[{fmt_time(timestamp)}] Przegrodka {rid}: {event_type}")
                        state["occupied"] = detected
                        state["pending"] = None
                        state["count"] = 0

                baseline_ready = True

            # Rysowanie: zolty ROI = chwilowy ruch/zasloniecie, zielony = stabilny.
            annotated = frame.copy()
            for roi, (x1, y1, x2, y2) in zip(rois, roi_pixels):
                rid = roi["id"]
                ratio, occluded = latest_roi_motion.get(rid, (0.0, False))
                color = (0, 220, 255) if occluded else (0, 180, 0)
                st = states[rid]
                label = f"{rid}: {'ZASLONIETA' if occluded else ('ZAJETA' if st['occupied'] else 'PUSTA')}"
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                cv2.putText(annotated, label, (x1 + 3, max(22, y1 + 22)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 2)
            for box, conf in zip(latest_boxes, latest_confs):
                bx1, by1, bx2, by2 = map(int, box)
                cv2.rectangle(annotated, (bx1, by1), (bx2, by2), (255, 80, 0), 2)
                cv2.putText(annotated, f"kartka {conf:.2f}", (bx1, max(20, by1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 80, 0), 2)
            writer.write(annotated)
            last_frame = frame.copy()
            frame_index += 1

            if frame_index % max(1, int(fps * 10)) == 0:
                pct = frame_index / frame_count * 100 if frame_count else 0
                print(f"Postep: {pct:.1f}%")

    finally:
        cap.release()
        writer.release()

    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        fields = ["id", "przegrodka", "typ", "czas_sekundy", "czas_filmu"]
        out = csv.DictWriter(f, fieldnames=fields)
        out.writeheader()
        out.writerows(events)

    print("\n=== GOTOWE ===")
    print(f"Analizowane klatki: {analyzed}")
    print(f"Zarejestrowane zmiany: {len(events)}")
    print(f"Wideo: {annotated_path}")
    print(f"Raport CSV: {csv_path}")
    print(f"Zdarzenia: {events_dir}")
    print("\nUWAGA: wykrywanie zasloniecia bazuje na ruchu obrazu. Gdy reka pozostaje nieruchomo")
    print("przez dluzszy czas, program moze jej nie rozpoznac. Do pelnej pewnosci potrzebny")
    print("bedzie osobny detektor reki lub dodatkowa klasa 'reka' w modelu.")


if __name__ == "__main__":
    main()
