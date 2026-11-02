"""
Evaluate the model on an independent, unseen image folder.

Expected layout:
  held_out_dataset/
    Garbage/
    Pothole/
    Water_Leakage/
    Electricity_Issue/

Exact duplicate files of training images are rejected so they cannot inflate
the independent test score.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from PIL import Image, UnidentifiedImageError

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from predict import predict

CLASSES = ["Garbage", "Pothole", "Water_Leakage", "Electricity_Issue"]
DISPLAY = {
    "Garbage": "Garbage",
    "Pothole": "Pothole",
    "Water_Leakage": "Water Leakage",
    "Electricity_Issue": "Electricity Issue",
}
EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
TRAIN_DIR = Path(HERE) / "dataset"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Evaluate on independent civic issue photos.")
    parser.add_argument("--dataset", required=True, help="Folder containing one folder per class.")
    parser.add_argument("--output", default="external_evaluation_report.json")
    args = parser.parse_args()

    test_root = Path(args.dataset).expanduser().resolve()
    if not test_root.is_dir():
        raise SystemExit("Test dataset folder not found: " + str(test_root))
    if test_root == TRAIN_DIR.resolve():
        raise SystemExit("The training dataset cannot be used as an independent test set.")

    training_hashes = set()
    for class_name in CLASSES:
        folder = TRAIN_DIR / class_name
        if folder.exists():
            for path in folder.rglob("*"):
                if path.is_file() and path.suffix.lower() in EXTENSIONS:
                    training_hashes.add(sha256(path))

    y_true, y_pred = [], []
    mistakes, duplicates, unreadable = [], [], []

    for class_name in CLASSES:
        folder = test_root / class_name
        if not folder.is_dir():
            raise SystemExit("Missing test class folder: " + str(folder))
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
                continue
            if sha256(path) in training_hashes:
                duplicates.append(str(path))
                continue
            try:
                with Image.open(path) as image:
                    image.verify()
                result = predict(str(path))
            except (OSError, UnidentifiedImageError, ValueError) as exc:
                unreadable.append({"file": str(path), "error": str(exc)})
                continue

            actual = CLASSES.index(class_name)
            predicted_name = result.get("category")
            if predicted_name not in DISPLAY.values():
                predicted = -1
                predicted_display = "Unknown"
            else:
                predicted = next(
                    i for i, name in enumerate(CLASSES)
                    if DISPLAY[name] == predicted_name
                )
                predicted_display = predicted_name

            y_true.append(actual)
            y_pred.append(predicted)
            if predicted != actual:
                mistakes.append({
                    "file": str(path.relative_to(test_root)).replace(os.sep, "/"),
                    "actual": DISPLAY[class_name],
                    "predicted": predicted_display,
                    "model_confidence": result.get("confidence"),
                    "reliable": result.get("reliable"),
                })

    if duplicates:
        raise SystemExit(
            "Independent evaluation stopped: "
            + str(len(duplicates)) + " exact training duplicate(s) found. "
            + "Remove them first. First duplicate: " + duplicates[0]
        )
    if not y_true:
        raise SystemExit("No readable, non-duplicate test images found.")

    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        precision_recall_fscore_support,
    )
    labels = list(range(len(CLASSES)))
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    report = {
        "test_dataset": str(test_root),
        "test_images": len(y_true),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_precision": round(float(precision.mean()), 4),
        "macro_recall": round(float(recall.mean()), 4),
        "macro_f1": round(float(f1.mean()), 4),
        "per_class_metrics": {
            DISPLAY[class_name]: {
                "precision": round(float(precision[index]), 4),
                "recall": round(float(recall[index]), 4),
                "f1": round(float(f1[index]), 4),
                "support": int(support[index]),
            }
            for index, class_name in enumerate(CLASSES)
        },
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        "mistakes": mistakes,
        "unreadable_images": unreadable,
        "exact_training_duplicates": 0,
    }

    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("\nSaved independent evaluation report to:", output.resolve())


if __name__ == "__main__":
    main()
