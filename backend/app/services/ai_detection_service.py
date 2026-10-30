"""
AI Issue Detection Service
---------------------------
Analyzes an uploaded complaint photo and suggests a category, a confidence
score, and a priority level.

This module is intentionally modular:
  - `detect_category()` is the single entry point used by the rest of the app.
  - Right now it uses a LOCAL FALLBACK heuristic (no paid API required), based
    on simple image statistics (average colour / brightness / edge density)
    which correlate loosely with the four supported categories.
  - To plug in a real trained ML model or a paid API later, simply replace
    the body of `detect_category()` (or `_local_fallback_detect()`) while
    keeping the same return format:
        {"category": str, "confidence": float, "priority": str}

Supported categories: Garbage, Water Leakage, Electricity Issue, Pothole
"""

import os
import random
try:
    from ai_model.predict import predict as _civic_predict
except Exception:
    _civic_predict = None


CATEGORIES = ["Garbage", "Water Leakage", "Electricity Issue", "Pothole"]

# Keywords that (if present in filename) nudge the fallback detector -
# purely a demo convenience, not required for the algorithm to work.
_FILENAME_HINTS = {
    "garbage": "Garbage", "trash": "Garbage", "waste": "Garbage",
    "water": "Water Leakage", "leak": "Water Leakage", "pipe": "Water Leakage",
    "electric": "Electricity Issue", "wire": "Electricity Issue", "pole": "Electricity Issue",
    "pothole": "Pothole", "road": "Pothole", "crack": "Pothole",
}


def detect_category(image_path, user_selected_category=None):
    """
    Main entry point. Returns a dict:
      {"category": <str>, "confidence": <float 0-1>, "priority": <Low/Medium/High>}
    Uses the trained MobileNetV2 model first; falls back to the old heuristic.
    """
    result = None

    # 1) Trained AI model (ai_model folder)
    if _civic_predict is not None and image_path and os.path.exists(image_path):
        try:
            r = _civic_predict(image_path)
            result = {"category": r["category"], "confidence": r["confidence"]}
        except Exception as e:
            print("AI model failed, using fallback:", e)

    # 2) Old local heuristic (unchanged) if the model is missing or failed
    if result is None:
        try:
            result = _local_fallback_detect(image_path)
        except Exception:
            # Never let AI detection break complaint submission.
            result = {"category": user_selected_category or "Garbage", "confidence": 0.4}

    result["priority"] = _calculate_base_priority(result["category"], result["confidence"])
    return result

def _local_fallback_detect(image_path):
    """
    Local, dependency-light heuristic detector.
    Uses basic pixel statistics via Pillow if available; otherwise falls
    back to a filename-hint / weighted-random guess so the app still works
    even without image libraries installed.
    """
    filename = os.path.basename(image_path).lower() if image_path else ""

    for hint, category in _FILENAME_HINTS.items():
        if hint in filename:
            return {"category": category, "confidence": round(random.uniform(0.75, 0.93), 2)}

    try:
        from PIL import Image

        with Image.open(image_path) as img:
            img = img.convert("RGB").resize((64, 64))
            pixels = list(img.getdata())
            n = len(pixels)
            avg_r = sum(p[0] for p in pixels) / n
            avg_g = sum(p[1] for p in pixels) / n
            avg_b = sum(p[2] for p in pixels) / n
            brightness = (avg_r + avg_g + avg_b) / 3

        # Simple colour-based heuristic (demo-grade, not a trained model):
        #  - Greyish/dark + low brightness  -> Pothole (asphalt)
        #  - Blue-dominant                  -> Water Leakage
        #  - Brown/mixed dull tones         -> Garbage
        #  - Very bright / high contrast    -> Electricity Issue
        if avg_b > avg_r and avg_b > avg_g:
            category = "Water Leakage"
            confidence = round(0.65 + (avg_b - max(avg_r, avg_g)) / 255, 2)
        elif brightness < 90:
            category = "Pothole"
            confidence = round(0.6 + (90 - brightness) / 200, 2)
        elif brightness > 180:
            category = "Electricity Issue"
            confidence = round(0.55 + (brightness - 180) / 200, 2)
        else:
            category = "Garbage"
            confidence = round(0.55 + random.uniform(0, 0.15), 2)

        confidence = max(0.4, min(confidence, 0.95))
        return {"category": category, "confidence": confidence}

    except Exception:
        # Pillow not installed or image unreadable — weighted random fallback
        category = random.choice(CATEGORIES)
        return {"category": category, "confidence": round(random.uniform(0.4, 0.6), 2)}


def _calculate_base_priority(category, confidence):
    """A starting priority suggestion based purely on category + AI confidence.
    Final priority may later be raised by the duplicate-detection service
    when multiple citizens report the same issue."""
    high_risk_categories = {"Electricity Issue", "Pothole"}
    if category in high_risk_categories and confidence >= 0.7:
        return "High"
    if confidence >= 0.6:
        return "Medium"
    return "Low"
