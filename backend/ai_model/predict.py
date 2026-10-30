"""
Smart Civic Guardian - AI image analysis.

    from ai_model.predict import predict
    result = predict("path/to/photo.jpg")
    # {'category': 'Pothole', 'confidence': 0.97, 'priority': 'Medium', ...}

Needs only:  numpy, pillow   (no TensorFlow / PyTorch)
"""
import os
import json
import numpy as np
from PIL import Image

try:                                   # works as a package (ai_model.predict) ...
    from . import backbone
except ImportError:                    # ... and as a plain script (python predict.py photo.jpg)
    import backbone

HERE = os.path.dirname(os.path.abspath(__file__))
CLASSIFIER = os.path.join(HERE, "model", "civic_classifier.npz")
LABELS = os.path.join(HERE, "model", "labels.json")

# ---- easy-to-edit settings -------------------------------------------------
CONFIDENCE_AS_PERCENT = False   # False -> 0.9731   True -> 97.31
MIN_RELIABLE_CONFIDENCE = 0.65  # below this the result is flagged "reliable": False
# Base priority for each category (change these if your guide wants different levels)
BASE_PRIORITY = {
    "Electricity Issue": "High",    # live wires / transformers are a safety hazard
    "Water Leakage": "Medium",
    "Pothole": "Medium",
    "Garbage": "Low",
}
# -----------------------------------------------------------------------------

_head = None
_classes = None


def _load():
    global _head, _classes
    if _head is None:
        z = np.load(CLASSIFIER)
        _head = (z["coef"], z["intercept"])
        _classes = json.load(open(LABELS))["classes"]
    return _head, _classes


def _prep(x):                         # must match train.py
    x = np.sqrt(np.maximum(x, 0))
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-8)


def _softmax(z):
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


def get_priority(category, confidence):
    prio = BASE_PRIORITY.get(category, "Medium")
    if confidence < MIN_RELIABLE_CONFIDENCE and prio == "High":
        prio = "Medium"               # not sure what it is -> don't raise a High alarm
    return prio


def predict(image_path):
    """Analyse one photo. Returns a dict: category, confidence, priority (+ extras)."""
    (coef, intercept), classes = _load()
    img = Image.open(image_path)
    img.thumbnail((640, 640))
    feats = np.stack([backbone.features(backbone.preprocess(img)),
                      backbone.features(backbone.preprocess(img.transpose(Image.FLIP_LEFT_RIGHT)))])
    probs = np.mean([_softmax(_prep(f) @ coef.T + intercept) for f in feats], axis=0)
    k = int(probs.argmax())
    category, conf = classes[k], float(probs[k])
    return {
        "category": category,
        "confidence": round(conf * 100, 2) if CONFIDENCE_AS_PERCENT else round(conf, 4),
        "priority": get_priority(category, conf),
        "reliable": conf >= MIN_RELIABLE_CONFIDENCE,
        "probabilities": {c: round(float(p), 4) for c, p in zip(classes, probs)},
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        sys.exit("Usage: python predict.py <photo.jpg> [more photos...]")
    for p in sys.argv[1:]:
        print(p, "->", json.dumps(predict(p), indent=2))
