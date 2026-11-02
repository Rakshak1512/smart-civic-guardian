"""
Leakage-resistant training for Smart Civic Guardian's civic image classifier.

Validation groups exact and near-duplicate photos before splitting. All
augmentations from a photo remain in that photo's training fold. Cross-image
synthetic composites are disabled because they can leak validation scenes.
"""
from __future__ import annotations
import hashlib
import json
import os
import random
import sys
import time
from collections import Counter

import numpy as np
from PIL import Image, ImageEnhance, UnidentifiedImageError

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import backbone  # noqa: E402

DATASET = os.path.join(HERE, "dataset")
OUT_DIR = os.path.join(HERE, "model")
CLASSIFIER_PATH = os.path.join(OUT_DIR, "civic_classifier.npz")
LABELS_PATH = os.path.join(OUT_DIR, "labels.json")
REPORT_PATH = os.path.join(OUT_DIR, "training_report.json")

CLASSES = ["Garbage", "Pothole", "Water_Leakage", "Electricity_Issue"]
DISPLAY = {
    "Garbage": "Garbage",
    "Pothole": "Pothole",
    "Water_Leakage": "Water Leakage",
    "Electricity_Issue": "Electricity Issue",
}
EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
SEED = 42
VIEWS_PER_PHOTO = 10
MAX_FOLDS = 5
PHASH_MAX_DISTANCE = 4
C_VALUES = (0.1, 0.3, 1.0, 3.0)
rng = random.Random(SEED)


def augment(img):
    """Use modest variation without routinely cropping away the civic issue."""
    img = img.convert("RGB")
    width, height = img.size
    area = width * height * rng.uniform(0.70, 1.0)
    ratio = rng.uniform(0.85, 1.18)
    crop_w = max(1, min(width, int((area * ratio) ** 0.5)))
    crop_h = max(1, min(height, int((area / ratio) ** 0.5)))
    left = rng.randint(0, max(0, width - crop_w))
    top = rng.randint(0, max(0, height - crop_h))
    img = img.crop((left, top, left + crop_w, top + crop_h))
    if rng.random() < 0.5:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if rng.random() < 0.35:
        img = img.rotate(rng.uniform(-8, 8), resample=Image.Resampling.BILINEAR)
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.82, 1.18))
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.82, 1.18))
    img = ImageEnhance.Color(img).enhance(rng.uniform(0.85, 1.15))
    return img


def list_images():
    """Collect readable images and fail early on undersized classes."""
    items = []
    for class_name in CLASSES:
        folder = os.path.join(DATASET, class_name)
        if not os.path.isdir(folder):
            raise SystemExit("Missing dataset folder: " + folder)
        paths = []
        for filename in sorted(os.listdir(folder)):
            if not filename.lower().endswith(EXTENSIONS):
                continue
            path = os.path.join(folder, filename)
            try:
                with Image.open(path) as image:
                    image.verify()
            except (OSError, UnidentifiedImageError, ValueError) as exc:
                print("Skipping unreadable image:", path, "-", exc, flush=True)
                continue
            paths.append(path)
        if len(paths) < 5:
            raise SystemExit(
                "Need at least 5 readable originals in dataset/"
                + class_name + "; found " + str(len(paths))
            )
        items.extend((path, class_name) for path in paths)
    return items


def dct_basis(size=32):
    positions = np.arange(size, dtype=np.float32)
    frequencies = np.arange(size, dtype=np.float32)[:, None]
    basis = np.cos((np.pi / size) * (positions[None, :] + 0.5) * frequencies)
    basis[0] *= np.sqrt(1.0 / size)
    basis[1:] *= np.sqrt(2.0 / size)
    return basis


_DCT32 = dct_basis(32)


def image_fingerprints(items):
    """Return exact and perceptual hashes for duplicate grouping."""
    exact_hashes = []
    perceptual_hashes = []
    for path, _ in items:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        exact_hashes.append(digest.hexdigest())
        with Image.open(path) as image:
            gray = image.convert("L").resize((32, 32), Image.Resampling.LANCZOS)
            pixels = np.asarray(gray, dtype=np.float32)
        low = (_DCT32 @ pixels @ _DCT32.T)[:8, :8].reshape(-1)
        bits = low > np.median(low[1:])
        perceptual_hashes.append(np.packbits(bits).tobytes())
    return exact_hashes, perceptual_hashes


def groups_for(items):
    """
    Group exact and very-near duplicates across all labels, including mislabeled
    copies. Duplicate-like photos cannot be split between train and validation.
    """
    exact_hashes, perceptual_hashes = image_fingerprints(items)
    parent = list(range(len(items)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first, second):
        root_a, root_b = find(first), find(second)
        if root_a != root_b:
            parent[root_b] = root_a

    def hamming(first, second):
        return sum((a ^ b).bit_count() for a, b in zip(first, second))

    for first in range(len(items)):
        for second in range(first + 1, len(items)):
            if (exact_hashes[first] == exact_hashes[second]
                    or hamming(perceptual_hashes[first], perceptual_hashes[second])
                    <= PHASH_MAX_DISTANCE):
                union(first, second)

    roots = [find(index) for index in range(len(items))]
    duplicates = len(items) - len(set(roots))
    first_label = {}
    conflicts = set()
    for index, root in enumerate(roots):
        current = items[index][1]
        previous = first_label.setdefault(root, current)
        if previous != current:
            conflicts.add(root)
    if conflicts:
        print(
            "WARNING: duplicate-like photos have conflicting labels in "
            + str(len(conflicts)) + " group(s). Review those labels.",
            flush=True,
        )
    return np.asarray(roots, dtype=np.int64), duplicates


def build_features(items):
    """
    Extract original, mirrored and per-photo augmented features.
    The source index is retained so each photo's views stay in one fold.
    No other dataset photo is used to synthesize a training image.
    """
    features, targets, sources, kinds = [], [], [], []
    started = time.time()
    for index, (path, class_name) in enumerate(items):
        with Image.open(path) as source:
            image = source.convert("RGB")
        image.thumbnail((640, 640))
        label = CLASSES.index(class_name)
        views = [
            (image, 0),
            (image.transpose(Image.Transpose.FLIP_LEFT_RIGHT), 1),
        ]
        views.extend((augment(image), 2) for _ in range(VIEWS_PER_PHOTO))
        for view, kind in views:
            features.append(backbone.features(backbone.preprocess(view)))
            targets.append(label)
            sources.append(index)
            kinds.append(kind)
        if (index + 1) % 10 == 0 or index + 1 == len(items):
            print(
                "Extracted " + str(index + 1) + "/" + str(len(items))
                + " originals (" + str(round(time.time() - started)) + "s)",
                flush=True,
            )
    return (
        np.asarray(features, dtype=np.float32),
        np.asarray(targets, dtype=np.int64),
        np.asarray(sources, dtype=np.int64),
        np.asarray(kinds, dtype=np.int8),
    )


def prep(features):
    features = np.sqrt(np.maximum(features, 0))
    return features / (np.linalg.norm(features, axis=1, keepdims=True) + 1e-8)


def make_folds(items, groups):
    """Use stratified group folds and reject any remaining group overlap."""
    from sklearn.model_selection import StratifiedGroupKFold

    labels = np.asarray([CLASSES.index(class_name) for _, class_name in items])
    group_counts = {
        class_name: len(set(groups[labels == index].tolist()))
        for index, class_name in enumerate(CLASSES)
    }
    n_splits = min(MAX_FOLDS, min(group_counts.values()))
    if n_splits < 2:
        raise SystemExit(
            "Not enough independent photo groups for grouped validation. "
            "Add more distinct photos to each category."
        )

    splitter = StratifiedGroupKFold(
        n_splits=n_splits, shuffle=True, random_state=SEED
    )
    folds = list(splitter.split(np.zeros(len(labels)), labels, groups))
    for number, (train_indices, validation_indices) in enumerate(folds, start=1):
        if len(set(labels[train_indices].tolist())) != len(CLASSES):
            raise SystemExit(
                "Fold " + str(number) + " is missing a training class. "
                "Add more independent images or resolve duplicate groups."
            )
        overlap = set(groups[train_indices].tolist()) & set(groups[validation_indices].tolist())
        if overlap:
            raise RuntimeError("Duplicate group leakage detected in fold " + str(number))
    return labels, folds, group_counts


def fit_head(features, targets, c_value):
    from sklearn.linear_model import LogisticRegression
    classifier = LogisticRegression(
        C=c_value,
        max_iter=4000,
        class_weight="balanced",
        solver="lbfgs",
        random_state=SEED,
    )
    classifier.fit(prep(features), targets)
    return classifier


def cross_validate(items, features, targets, source_indices, kinds,
                   labels, folds, c_value):
    """Produce one out-of-fold prediction for each original photograph."""
    prediction = np.full(len(items), -1, dtype=np.int64)
    confidence = np.zeros(len(items), dtype=np.float32)
    fold_scores = []

    for number, (train_indices, validation_indices) in enumerate(folds, start=1):
        train_mask = np.isin(source_indices, train_indices)
        classifier = fit_head(features[train_mask], targets[train_mask])
        for image_index in validation_indices:
            # Validation uses only original and mirrored versions.
            mask = (source_indices == image_index) & (kinds <= 1)
            per_view = classifier.predict_proba(prep(features[mask]))
            probabilities = per_view.mean(axis=0)
            full_probabilities = np.zeros(len(CLASSES), dtype=np.float64)
            full_probabilities[classifier.classes_.astype(int)] = probabilities
            predicted = int(np.argmax(full_probabilities))
            prediction[image_index] = predicted
            confidence[image_index] = float(full_probabilities[predicted])

        accuracy = float(np.mean(prediction[validation_indices] == labels[validation_indices]))
        fold_scores.append({
            "fold": number,
            "validation_photos": int(len(validation_indices)),
            "accuracy": round(accuracy, 4),
        })
        print(
            "C=" + str(c_value) + " fold " + str(number) + "/"
            + str(len(folds)) + " accuracy=" + str(round(accuracy, 4)),
            flush=True,
        )

    if np.any(prediction < 0):
        raise RuntimeError("Some photos did not receive an out-of-fold prediction.")
    return prediction, confidence, fold_scores


def summarize_metrics(labels, predictions):
    from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

    precision, recall, f1, support = precision_recall_fscore_support(
        labels,
        predictions,
        labels=list(range(len(CLASSES))),
        zero_division=0,
    )
    per_class = {}
    for index, class_name in enumerate(CLASSES):
        per_class[DISPLAY[class_name]] = {
            "precision": round(float(precision[index]), 4),
            "recall": round(float(recall[index]), 4),
            "f1": round(float(f1[index]), 4),
            "support": int(support[index]),
        }
    return {
        "accuracy": round(float(np.mean(labels == predictions)), 4),
        "macro_f1": round(float(np.mean(f1)), 4),
        "per_class": per_class,
        "confusion_matrix": confusion_matrix(
            labels, predictions, labels=list(range(len(CLASSES)))
        ).tolist(),
    }


def save_artifacts(classifier, report):
    """Write temporary files first so failed training keeps the old model."""
    os.makedirs(OUT_DIR, exist_ok=True)
    classifier_tmp = CLASSIFIER_PATH + ".tmp"
    labels_tmp = LABELS_PATH + ".tmp"
    report_tmp = REPORT_PATH + ".tmp"

    with open(classifier_tmp, "wb") as handle:
        np.savez(
            handle,
            coef=classifier.coef_.astype(np.float32),
            intercept=classifier.intercept_.astype(np.float32),
        )
    with open(labels_tmp, "w", encoding="utf-8") as handle:
        json.dump({"classes": [DISPLAY[name] for name in CLASSES]}, handle, indent=2)
        handle.write("\n")
    with open(report_tmp, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")

    os.replace(classifier_tmp, CLASSIFIER_PATH)
    os.replace(labels_tmp, LABELS_PATH)
    os.replace(report_tmp, REPORT_PATH)


def main():
    items = list_images()
    counts = dict(Counter(class_name for _, class_name in items))
    print("Original photos by class:", counts, flush=True)

    smallest, largest = min(counts.values()), max(counts.values())
    if largest > smallest * 5:
        print(
            "WARNING: class imbalance ratio is "
            + str(round(largest / smallest, 2))
            + ":1. Balanced class weights are enabled, but collecting more "
            "real photographs for smaller classes is strongly recommended.",
            flush=True,
        )

    groups, duplicate_count = groups_for(items)
    labels, folds, group_counts = make_folds(items, groups)
    print(
        "Grouped validation: " + str(len(folds)) + " folds; "
        + str(duplicate_count) + " duplicate/near-duplicate links grouped.",
        flush=True,
    )

    print("Extracting MobileNetV2 features...", flush=True)
    features, targets, source_indices, kinds = build_features(items)
    print("Training views:", len(targets), flush=True)

    best = None
    for c_value in C_VALUES:
        predictions, confidence, fold_scores = cross_validate(
            items, features, targets, source_indices, kinds,
            labels, folds, c_value,
        )
        metrics = summarize_metrics(labels, predictions)
        print(
            "C=" + str(c_value)
            + " grouped-CV accuracy=" + str(metrics["accuracy"])
            + " macro-F1=" + str(metrics["macro_f1"]),
            flush=True,
        )
        if best is None or metrics["macro_f1"] > best["metrics"]["macro_f1"]:
            best = {
                "c_value": c_value,
                "metrics": metrics,
                "predictions": predictions,
                "confidence": confidence,
                "fold_scores": fold_scores,
            }

    # Final production model is fitted on every available original photograph.
    final_classifier = fit_head(features, targets, best["c_value"])
    mistakes = []
    for index, (path, actual) in enumerate(items):
        predicted = int(best["predictions"][index])
        if predicted != int(labels[index]):
            mistakes.append({
                "file": os.path.relpath(path, DATASET).replace(os.sep, "/"),
                "actual": DISPLAY[actual],
                "predicted": DISPLAY[CLASSES[predicted]],
                "predicted_probability": round(float(best["confidence"][index]), 4),
            })

    report = {
        "photos_per_class": counts,
        "total_original_photos": len(items),
        "unique_duplicate_groups": len(set(groups.tolist())),
        "duplicate_or_near_duplicate_links": duplicate_count,
        "training_views": int(len(targets)),
        "validation_method": "StratifiedGroupKFold with exact and perceptual near-duplicate grouping",
        "validation_folds": len(folds),
        "group_count_per_class": group_counts,
        "cross_image_synthetic_augmentation": False,
        "selected_C": best["c_value"],
        "heldout_accuracy": best["metrics"]["accuracy"],
        "macro_f1": best["metrics"]["macro_f1"],
        "per_class_metrics": best["metrics"]["per_class"],
        "confusion_matrix": best["metrics"]["confusion_matrix"],
        "fold_metrics": best["fold_scores"],
        "class_order": [DISPLAY[name] for name in CLASSES],
        "mistakes": mistakes,
        "evaluation_note": (
            "Grouped cross-validation on the checked-in training dataset. "
            "Use evaluate.py with a separate unseen real-world test set for an "
            "independent final accuracy measurement."
        ),
    }
    save_artifacts(final_classifier, report)

    print("\nSelected C:", best["c_value"])
    print("Leakage-resistant grouped CV accuracy:", best["metrics"]["accuracy"])
    print("Leakage-resistant grouped CV macro-F1:", best["metrics"]["macro_f1"])
    print("Per-class metrics:", json.dumps(best["metrics"]["per_class"], indent=2))
    print("Updated model weights and training_report.json successfully.", flush=True)


if __name__ == "__main__":
    main()
