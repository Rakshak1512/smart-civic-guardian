# Smart Civic Guardian – AI Model (ai_model)

Classifies a citizen's photo into: **Garbage, Pothole, Water Leakage, Electricity Issue**
and returns `{category, confidence, priority}`.

Model = MobileNetV2 (ImageNet pre-trained, frozen) + a classifier head trained on your photos + TrashNet garbage photos.
Runs on plain `numpy + pillow` – no TensorFlow / PyTorch install needed.

## Files
| File | What it is |
|---|---|
| `predict.py` | **The only file your Flask app imports.** `predict(image_path)` |
| `backbone.py` | MobileNetV2 feature extractor (pure NumPy) |
| `model/mobilenetv2_imagenet.npz` | pre-trained MobileNetV2 weights (do not edit) |
| `model/civic_classifier.npz`, `model/labels.json` | the trained head (your 4 categories) |
| `model/training_report.json` | accuracy / confusion matrix from training |
| `train.py` | re-train after you add more photos |
| `dataset/` | photos used for training (one folder per category) |
| `sample_test_images/` | 4 photos for a quick smoke test |

## Quick test (before touching the website)
```
cd ai_model
python predict.py sample_test_images/pothole.jpg
```

## Output
```python
{"category": "Pothole", "confidence": 0.9260, "priority": "Medium",
 "reliable": True, "probabilities": {...}}
```
Settings (top of `predict.py`): `CONFIDENCE_AS_PERCENT`, `MIN_RELIABLE_CONFIDENCE`, `BASE_PRIORITY`.

## Re-train with more photos (recommended!)
1. Add photos to `dataset/<Category>/` (jpg/png). Real street-garbage photos matter most.
2. `pip install scikit-learn`
3. `python train.py`   (about 4 minutes; prints accuracy and rewrites `model/civic_classifier.npz`)
4. Restart Flask.
