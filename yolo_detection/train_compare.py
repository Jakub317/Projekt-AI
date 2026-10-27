"""
Trening YOLO i porównanie wyników po 1, 10, 20 i 50 epokach.

Instalacja:
    pip install ultralytics pandas matplotlib pyyaml

Uruchomienie:
    python train_compare.py --data dataset/data.yaml --epochs 50

Wyniki Ultralytics zapisuje w runs/organizer/trening/.
Skrypt tworzy też porownanie_epok.csv i wykresy metryk.
"""
import argparse
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="dataset/data.yaml",
                        help="Ścieżka do pliku data.yaml")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--model", default="yolo11n.pt",
                        help="Model startowy, np. yolo11n.pt")
    parser.add_argument("--device", default=None,
                        help="Np. cpu, 0 (pierwsza karta NVIDIA); domyślnie auto")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(
            f"Nie znaleziono {data_path}. Najpierw przygotuj dataset/data.yaml "
            "według instrukcji w README."
        )

    model = YOLO(args.model)
    train_args = dict(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        project="runs/organizer",
        name="trening",
        exist_ok=True,
        save=True,
        save_period=1,       # zapis checkpointu po każdej epoce
        plots=True,
        verbose=True,
    )
    if args.device:
        train_args["device"] = args.device

    model.train(**train_args)

    run_dir = Path("runs/organizer/trening")
    csv_path = run_dir / "results.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Nie znaleziono {csv_path}; sprawdź folder wyników treningu."
        )

    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    # Wiersz 0 to wynik po pierwszej epoce, wiersz 9 po dziesiątej itd.
    wanted = [1, 10, 20, 50, args.epochs]
    wanted = sorted(set(e for e in wanted if 1 <= e <= len(df)))
    rows = []
    metric_cols = [
        "metrics/precision(B)",
        "metrics/recall(B)",
        "metrics/mAP50(B)",
        "metrics/mAP50-95(B)",
    ]

    for epoch_num in wanted:
        row = df.iloc[epoch_num - 1]
        item = {"epoka": epoch_num}
        for col in metric_cols:
            if col in df.columns:
                item[col.replace("metrics/", "").replace("(B)", "")] = float(row[col])
        rows.append(item)

    summary = pd.DataFrame(rows)
    summary_path = run_dir / "porownanie_epok.csv"
    summary.to_csv(summary_path, index=False)

    # Wykresy wszystkich metryk dostępnych w results.csv.
    plot_cols = [c for c in metric_cols if c in df.columns]
    if plot_cols:
        x = range(1, len(df) + 1)
        for col in plot_cols:
            plt.figure()
            plt.plot(x, df[col])
            plt.xlabel("Epoka")
            plt.ylabel(col)
            plt.title(f"Zmiana {col} w czasie treningu")
            plt.grid(True)
            out = run_dir / (col.replace("/", "_").replace("(", "").replace(")", "") + ".png")
            plt.tight_layout()
            plt.savefig(out, dpi=150)
            plt.close()

    print("\nPorównanie wyników walidacji:")
    print(summary.to_string(index=False))
    print(f"\nTabela: {summary_path}")
    print(f"Pełne logi i wykresy: {run_dir.resolve()}")
    print("\nUwaga: wyniki walidacji mierzą działanie na zbiorze walidacyjnym,")
    print("a nie gwarantowaną skuteczność na nowych zdjęciach z produkcji.")


if __name__ == "__main__":
    main()
