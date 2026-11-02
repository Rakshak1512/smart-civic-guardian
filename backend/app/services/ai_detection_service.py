"""Image-based civic issue classification.

Uses the shipped MobileNetV2 feature extractor and trained civic classifier.
No random, filename, or colour-based guesses are made when the model is not
available; callers receive an explicit low-confidence result instead.
"""
from __future__ import annotations

import os
import tempfile

from PIL import Image, UnidentifiedImageError

try:
    from ai_model.predict import predict as _civic_predict
except Exception as exc:  # import errors are surfaced as an unavailable model
    _civic_predict = None
    _MODEL_IMPORT_ERROR = str(exc)
else:
    _MODEL_IMPORT_ERROR = None

CATEGORIES = ("Garbage", "Water Leakage", "Electricity Issue", "Pothole")


def detect_category(image_path=None, user_selected_category=None, image_file=None):
    """Classify an uploaded image path or file-like object.

    The citizen-selected category is deliberately *not* treated as an AI
    prediction. It is returned separately as the manual category, so the UI
    can show the model's independent result and let the citizen choose.
    """
    temp_path = None
    path = image_path
    try:
        if image_file is not None:
            stream = image_file.stream if hasattr(image_file, "stream") else image_file
            stream.seek(0)
            suffix = os.path.splitext(getattr(image_file, "filename", "upload.jpg"))[1] or ".jpg"
            with tempfile.NamedTemporaryFile(prefix="scg-ai-", suffix=suffix, delete=False) as tmp:
                tmp.write(stream.read())
                temp_path = tmp.name
            stream.seek(0)
            path = temp_path
        if not path or not os.path.isfile(path):
            return _unavailable(user_selected_category, "The uploaded image could not be read by the analyser.")
        if _civic_predict is None:
            return _unavailable(user_selected_category, "The trained image model could not be loaded on the server.")

        # Validate/decode once before model inference. Reject non-image files.
        with Image.open(path) as image:
            image.verify()
        prediction = _civic_predict(path)
        category = prediction.get("category")
        confidence = float(prediction.get("confidence", 0.0))
        if category not in CATEGORIES or not 0 <= confidence <= 1:
            return _unavailable(user_selected_category, "The image model returned an invalid result.")
        prediction["category"] = category
        prediction["confidence"] = round(confidence, 4)
        prediction["priority"] = prediction.get("priority") or _calculate_base_priority(category, confidence)
        prediction["reliable"] = bool(prediction.get("reliable", confidence >= 0.65))
        prediction["manual_category"] = user_selected_category if user_selected_category in CATEGORIES else None
        prediction["analyzer_status"] = "ok"
        prediction["message"] = (
            "Image analysed successfully. Review the AI suggestion and confirm or change the category."
            if prediction["reliable"] else
            "The image is unclear to the model. Please verify the suggestion or choose the correct category manually."
        )
        return prediction
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        return _unavailable(user_selected_category, "The uploaded file is not a valid readable image.")
    except Exception:
        return _unavailable(user_selected_category, "Image analysis failed. Please select the category manually and try again.")
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass


def _unavailable(manual_category, message):
    return {
        "category": None,
        "confidence": 0.0,
        "priority": _calculate_base_priority(manual_category, 0.0) if manual_category in CATEGORIES else "Medium",
        "reliable": False,
        "manual_category": manual_category if manual_category in CATEGORIES else None,
        "analyzer_status": "unavailable",
        "message": message,
    }


def _calculate_base_priority(category, confidence):
    if category == "Electricity Issue":
        return "High"
    if category == "Pothole" and confidence >= 0.65:
        return "High"
    if confidence >= 0.60:
        return "Medium"
    return "Low"
