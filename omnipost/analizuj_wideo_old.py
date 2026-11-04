from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from datetime import datetime

import cv2
from ultralytics import YOLO


def box_center(box):
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def box_size(box):
    x1, y1, x2, y2 = box
    return max(1.0, x2 - x1), max(1.0, y2 - y1)


def similar(a, b, frame_diag, distance_limit):
    ax, ay = box_center(a)
    bx, by = box_center(b)
    distance = math.hypot(ax - bx, ay - by) / frame_diag
    if distance <= distance_limit:
        return True

    # Dodatkowe kryterium: nakładanie się prostokątów (IoU).
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - intersection
    iou = intersection / union if union > 0 else 0
    return iou >= 0.15


def fmt_time(seconds):
    total_ms = int(seconds * 1000)
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) / 1000
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def main():
    parser = argparse.ArgumentParser(
        description="Wykrywa zmiany liczby i położenia kartek na półce w nagraniu wideo."
    )
    parser.add_argument("--video", "-v", default="videos/nagranie.mp4",
                        help="Ścieżka do filmu, domyślnie videos/nagranie.mp4")
    parser.add_argument("--model", "-m", default="model/best.pt",
                        help="Ścieżka do modelu best.pt, domyślnie model/best.pt")
    parser.add_argument("--output", "-o", default="results",
                        help="Folder wynikowy, domyślnie results")
    parser.add_argument("--conf", type=float, default=0.45,
                        help="Próg pewności YOLO, domyślnie 0.25")
    parser.add_argument("--every", type=int, default=5,
                        help="Analizuj co ile klatek (domyślnie 5)")
    parser.add_argument("--confirm", type=int, default=3,
                        help="Ile kolejnych analiz potwierdza zmianę (domyślnie 3)")
    parser.add_argument("--distance", type=float, default=0.045,
                        help="Próg dopasowania położenia względem przekątnej obrazu")
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parent
    video_path = (project_dir / args.video).resolve()
    model_path = (project_dir / args.model).resolve()
    output_dir = (project_dir / args.output).resolve()

    if not model_path.is_file():
        raise FileNotFoundError(f"Nie znaleziono modelu: {model_path}")
    if not video_path.is_file():
        raise FileNotFoundError(f"Nie znaleziono filmu: {video_path}")
    if args.every < 1 or args.confirm < 1:
        raise ValueError("--every i --confirm muszą być większe lub równe 1")

    output_dir.mkdir(parents=True, exist_ok=True)
    events_dir = output_dir / "events"
    events_dir.mkdir(exist_ok=True)

    annotated_path = output_dir / "annotated_video.mp4"
    csv_path = output_dir / "raport.csv"

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Nie można otworzyć filmu: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_diag = math.hypot(width, height)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(annotated_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError("Nie udało się utworzyć pliku wynikowego MP4.")

    print("=== ANALIZA WIDEO - WYKRYWANIE ZMIAN NA POLCE ===")
    print(f"Film: {video_path}")
    print(f"Model: {model_path}")
    print(f"Rozdzielczosc: {width}x{height}, FPS: {fps:.2f}")
    print("Pierwszy analizowany obraz będzie punktem odniesienia.")
    print("Zmiany zostaną zapisane po potwierdzeniu w kolejnych analizach.")

    model = YOLO(str(model_path))

    # Stabilny stan półki. Pierwsza analizowana klatka jest tylko bazą,
    # więc kartki widoczne od początku filmu nie są zgłaszane jako nowe.
    stable = []
    pending_additions = []
    event_rows = []
    frame_index = 0
    analyzed = 0
    event_number = 0
    last_frame = None
    baseline_ready = False
    latest_boxes = []
    latest_confs = []

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            should_analyze = (frame_index % args.every == 0)
            if should_analyze:
                analyzed += 1
                timestamp = frame_index / fps
                result = model.predict(
                    source=frame,
                    conf=args.conf,
                    verbose=False
                )[0]

                boxes = []
                confs = []
                if result.boxes is not None:
                    for item in result.boxes:
                        coords = item.xyxy[0].cpu().tolist()
                        boxes.append(tuple(float(v) for v in coords))
                        confs.append(float(item.conf[0].cpu()))

                latest_boxes = boxes
                latest_confs = confs

                if not baseline_ready:
                    stable = [
                        {"box": b, "conf": c, "missing": 0}
                        for b, c in zip(boxes, confs)
                    ]
                    baseline_ready = True
                    print(f"Utworzono punkt odniesienia: {len(stable)} kartek.")
                else:
                    matched_stable = set()
                    unmatched_detections = []

                    # Dopasuj bieżące wykrycia do kartek już znanych.
                    for det_index, det_box in enumerate(boxes):
                        candidates = []
                        for stable_index, item in enumerate(stable):
                            if stable_index in matched_stable:
                                continue
                            if similar(item["box"], det_box, frame_diag, args.distance):
                                old_cx, old_cy = box_center(item["box"])
                                new_cx, new_cy = box_center(det_box)
                                dist = math.hypot(old_cx-new_cx, old_cy-new_cy)
                                candidates.append((dist, stable_index))
                        if candidates:
                            _, best_index = min(candidates)
                            matched_stable.add(best_index)
                            stable[best_index]["box"] = det_box
                            stable[best_index]["conf"] = confs[det_index]
                            stable[best_index]["missing"] = 0
                        else:
                            unmatched_detections.append((det_box, confs[det_index]))

                    # Potwierdzanie zniknięcia kartki.
                    removed_indices = []
                    for stable_index, item in enumerate(stable):
                        if stable_index not in matched_stable:
                            item["missing"] += 1
                            if item["missing"] >= args.confirm:
                                event_number += 1
                                event_rows.append({
                                    "id": event_number,
                                    "typ": "USUNIĘCIE",
                                    "czas_sekundy": round(timestamp, 3),
                                    "czas_filmu": fmt_time(timestamp),
                                    "pewnosc": round(item["conf"], 4),
                                    "x1": round(item["box"][0], 1),
                                    "y1": round(item["box"][1], 1),
                                    "x2": round(item["box"][2], 1),
                                    "y2": round(item["box"][3], 1),
                                })
                                stem = f"zdarzenie_{event_number:04d}_usuniecie"
                                if last_frame is not None:
                                    cv2.imwrite(str(events_dir / f"{stem}_przed.jpg"), last_frame)
                                cv2.imwrite(str(events_dir / f"{stem}_po.jpg"), frame)
                                removed_indices.append(stable_index)
                                print(f"[{fmt_time(timestamp)}] USUNIĘCIE kartki")
                    for idx in reversed(removed_indices):
                        stable.pop(idx)

                    # Potwierdzanie pojawienia się nowej kartki.
                    updated_pending = []
                    used_pending = set()
                    for det_box, det_conf in unmatched_detections:
                        best = None
                        for p_idx, pending in enumerate(pending_additions):
                            if p_idx in used_pending:
                                continue
                            if similar(pending["box"], det_box, frame_diag, args.distance):
                                old_cx, old_cy = box_center(pending["box"])
                                new_cx, new_cy = box_center(det_box)
                                dist = math.hypot(old_cx-new_cx, old_cy-new_cy)
                                if best is None or dist < best[0]:
                                    best = (dist, p_idx)
                        if best is not None:
                            _, p_idx = best
                            used_pending.add(p_idx)
                            pending = pending_additions[p_idx]
                            pending["box"] = det_box
                            pending["conf"] = det_conf
                            pending["count"] += 1
                            updated_pending.append(pending)
                        else:
                            updated_pending.append({
                                "box": det_box,
                                "conf": det_conf,
                                "count": 1,
                            })

                    # Zdarzenia dodania są zapisywane po wymaganej liczbie
                    # kolejnych analiz, aby ograniczyć fałszywe alarmy.
                    still_pending = []
                    for pending in updated_pending:
                        if pending["count"] >= args.confirm:
                            event_number += 1
                            b = pending["box"]
                            c = pending["conf"]
                            event_rows.append({
                                "id": event_number,
                                "typ": "DODANIE",
                                "czas_sekundy": round(timestamp, 3),
                                "czas_filmu": fmt_time(timestamp),
                                "pewnosc": round(c, 4),
                                "x1": round(b[0], 1),
                                "y1": round(b[1], 1),
                                "x2": round(b[2], 1),
                                "y2": round(b[3], 1),
                            })
                            stem = f"zdarzenie_{event_number:04d}_dodanie"
                            if last_frame is not None:
                                cv2.imwrite(str(events_dir / f"{stem}_przed.jpg"), last_frame)
                            cv2.imwrite(str(events_dir / f"{stem}_po.jpg"), frame)
                            stable.append({"box": b, "conf": c, "missing": 0})
                            print(f"[{fmt_time(timestamp)}] DODANIE kartki")
                        else:
                            still_pending.append(pending)
                    pending_additions = still_pending

            # Zapisuj cały film z ostatnimi wynikami detekcji.
            annotated = frame.copy()
            for box, conf in zip(latest_boxes, latest_confs):
                x1, y1, x2, y2 = map(int, box)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 220, 0), 2)
                cv2.putText(
                    annotated, f"kartka {conf:.2f}", (x1, max(20, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 0), 2
                )
            writer.write(annotated)
            last_frame = frame.copy()
            frame_index += 1

            if frame_index % max(1, int(fps * 10)) == 0:
                percent = (frame_index / frame_count * 100) if frame_count else 0
                print(f"Postep: {percent:.1f}%")

    finally:
        cap.release()
        writer.release()

    fields = [
        "id", "typ", "czas_sekundy", "czas_filmu", "pewnosc",
        "x1", "y1", "x2", "y2"
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        csv_writer = csv.DictWriter(f, fieldnames=fields)
        csv_writer.writeheader()
        csv_writer.writerows(event_rows)

    print("\n=== GOTOWE ===")
    print(f"Przeanalizowane klatki: {analyzed}")
    print(f"Liczba zarejestrowanych zmian: {len(event_rows)}")
    print(f"Film z wykryciami: {annotated_path}")
    print(f"Raport: {csv_path}")
    print(f"Zdjecia zdarzen: {events_dir}")


if __name__ == "__main__":
    main()
