import argparse
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from ultralytics import YOLO

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="dataset/data.yaml")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(f"Nie znaleziono {data_path}.")

    model = YOLO(args.model)
    train_args = dict(
        data=str(data_path), epochs=args.epochs, imgsz=args.imgsz,
        batch=args.batch, project="runs/organizer", name="trening",
        exist_ok=True, save=True, save_period=1, plots=True, verbose=True,
    )
    if args.device: train_args["device"] = args.device

    model.train(**train_args)
    
    run_dir = Path("runs/organizer/trening")
    csv_path = run_dir / "results.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        df.columns = [c.strip() for c in df.columns]

if __name__ == "__main__":
    main()
