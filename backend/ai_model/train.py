"""
Smart Civic Guardian - (re)train the civic-issue image classifier.

HOW IT WORKS (transfer learning)
  1. MobileNetV2 (pre-trained on ImageNet, frozen) turns every photo into 1280 numbers.
  2. A small classifier "head" is trained on those numbers to pick one of the 4 categories.
  3. Only the head is saved to model/civic_classifier.npz  (the big backbone never changes).

RE-TRAIN WHEN YOU ADD PHOTOS
  - Put new photos into  dataset/<Category>/   (jpg / jpeg / png), then run:
        python train.py
  - Folder names = category names:  Pothole, Water_Leakage, Electricity_Issue, Garbage
  - Takes about 1-3 minutes on a normal laptop. No GPU needed.

Needs:  pip install numpy pillow scikit-learn
"""
import os, sys, json, random, time
import numpy as np
from PIL import Image, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import backbone  # noqa: E402

DATASET = os.path.join(HERE, "dataset")
OUT_DIR = os.path.join(HERE, "model")
CLASSES = ["Garbage", "Pothole", "Water_Leakage", "Electricity_Issue"]
DISPLAY = {"Garbage": "Garbage", "Pothole": "Pothole",
           "Water_Leakage": "Water Leakage", "Electricity_Issue": "Electricity Issue"}
EXT = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
SEED = 42
VIEWS_PER_PHOTO = 14          # augmented views made from each photo
rng = random.Random(SEED)
nrng = np.random.RandomState(SEED)


# ------------------------------------------------------------------ augmentation
def augment(img):
    img = img.convert("RGB")
    w, h = img.size
    area = w * h * rng.uniform(0.45, 1.0)
    ratio = rng.uniform(3 / 4, 4 / 3)
    cw = int(min(w, (area * ratio) ** 0.5)); ch = int(min(h, (area / ratio) ** 0.5))
    x0 = rng.randint(0, w - cw); y0 = rng.randint(0, h - ch)
    img = img.crop((x0, y0, x0 + cw, y0 + ch))
    if rng.random() < 0.5:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if rng.random() < 0.4:
        img = img.rotate(rng.uniform(-12, 12), resample=Image.BILINEAR, expand=False)
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.75, 1.25))
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.75, 1.25))
    img = ImageEnhance.Color(img).enhance(rng.uniform(0.7, 1.3))
    return img


def is_studio_photo(img):
    """TrashNet-style photo: object on a plain bright background."""
    a = np.asarray(img.convert("RGB").resize((64, 64)), dtype=np.float32)
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    return border.mean() > 150 and border.std(axis=0).mean() < 30


def composite_on_scene(obj_img, scene_imgs):
    """Cut the object out of its plain background and paste it onto a real street/scene photo.
    Stops the model from learning 'white background = garbage'."""
    from scipy import ndimage as ndi
    a = np.asarray(obj_img.convert("RGB").resize((256, 256)), dtype=np.float32)
    border = np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3),
                             a[:, :6].reshape(-1, 3), a[:, -6:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    mask = np.abs(a - bg).max(axis=2) > 32
    mask = ndi.binary_closing(mask, iterations=2)
    mask = ndi.binary_fill_holes(mask)
    mask = ndi.binary_opening(mask, iterations=2)
    if mask.sum() < 800:
        return None
    ys, xs = np.where(mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    obj = Image.fromarray(a.astype(np.uint8)[y0:y1, x0:x1])
    m = Image.fromarray((mask[y0:y1, x0:x1] * 255).astype(np.uint8))
    scene = rng.choice(scene_imgs).convert("RGB")
    scene = augment(scene).resize((384, 384))
    scale = rng.uniform(0.35, 0.8) * 384 / max(obj.size)
    nw, nh = max(8, int(obj.size[0] * scale)), max(8, int(obj.size[1] * scale))
    obj, m = obj.resize((nw, nh)), m.resize((nw, nh))
    px, py = rng.randint(0, 384 - nw), rng.randint(0, 384 - nh)
    scene.paste(obj, (px, py), m)
    return scene


# ------------------------------------------------------------------ data
def list_images():
    items = []
    for c in CLASSES:
        d = os.path.join(DATASET, c)
        if not os.path.isdir(d):
            sys.exit(f"Missing folder: {d}")
        for f in sorted(os.listdir(d)):
            if f.lower().endswith(EXT):
                items.append((os.path.join(d, f), c))
    return items


def build_features(items):
    scenes = []
    for p, c in items:
        if c != "Garbage":
            scenes.append(Image.open(p).convert("RGB"))
    X, y, src, kind = [], [], [], []
    t0 = time.time()
    for i, (p, c) in enumerate(items):
        img = Image.open(p).convert("RGB")
        img.thumbnail((640, 640))
        label = CLASSES.index(c)
        # view 0 = clean photo, view 1 = mirrored, rest = random augmentations
        X.append(backbone.features(backbone.preprocess(img))); y.append(label); src.append(i); kind.append(0)
        X.append(backbone.features(backbone.preprocess(img.transpose(Image.FLIP_LEFT_RIGHT)))); y.append(label); src.append(i); kind.append(1)
        for _ in range(VIEWS_PER_PHOTO):
            X.append(backbone.features(backbone.preprocess(augment(img)))); y.append(label); src.append(i); kind.append(2)
        if c == "Garbage" and is_studio_photo(img) and scenes:
            made = 0
            for _ in range(8):
                comp = composite_on_scene(img, scenes)
                if comp is not None:
                    X.append(backbone.features(backbone.preprocess(comp))); y.append(label); src.append(i); kind.append(3); made += 1
        if (i + 1) % 20 == 0:
            print(f"  features {i + 1}/{len(items)}  ({time.time() - t0:.0f}s)", flush=True)
    return np.array(X, np.float32), np.array(y), np.array(src), np.array(kind)


def prep(X):
    X = np.sqrt(np.maximum(X, 0))                       # tame the big activations
    return X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-8)


def groups_for(items, X, src, kind):
    """Photos that look almost identical (e.g. same pothole twice) must be held out together."""
    n = len(items)
    F = np.zeros((n, X.shape[1]), np.float32)
    for i in range(n):
        F[i] = prep(X[(src == i) & (kind == 0)])[0]
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    sim = F @ F.T
    for i in range(n):
        for j in range(i + 1, n):
            if items[i][1] == items[j][1] and sim[i, j] > 0.93:
                parent[find(i)] = find(j)
    return np.array([find(i) for i in range(n)])


def fit_head(Xtr, ytr, C):
    from sklearn.linear_model import LogisticRegression
    clf = LogisticRegression(C=C, max_iter=3000, class_weight="balanced")
    clf.fit(prep(Xtr), ytr)
    return clf


def cross_validate(items, X, y, src, kind, C):
    """Leave-one-photo-group-out test: the model never sees the photo (or its twins) it is tested on."""
    grp = groups_for(items, X, src, kind)
    labels = np.array([CLASSES.index(c) for _, c in items])
    user_groups = sorted({g for g, l in zip(grp, labels) if l != 0})
    garb_idx = [i for i, l in enumerate(labels) if l == 0]
    rng2 = random.Random(1); rng2.shuffle(garb_idx)
    fold_of = {}
    for k, g in enumerate(user_groups):
        for i in np.where(grp == g)[0]:
            fold_of[int(i)] = k
    for k, i in enumerate(garb_idx):
        fold_of[i] = k % len(user_groups)
    pred_all, true_all = [], []
    wrong = []
    for k in range(len(user_groups)):
        test_imgs = [i for i, f in fold_of.items() if f == k]
        tr_mask = np.array([fold_of[int(s)] != k for s in src])
        clf = fit_head(X[tr_mask], y[tr_mask], C)
        for i in test_imgs:
            xs = X[(src == i) & (kind <= 1)]                  # clean + mirrored view
            p = clf.predict_proba(prep(xs)).mean(axis=0)
            pred_all.append(int(p.argmax())); true_all.append(int(labels[i]))
            if p.argmax() != labels[i]:
                wrong.append((os.path.basename(items[i][0]), CLASSES[labels[i]], CLASSES[int(p.argmax())], float(p.max())))
    return np.array(true_all), np.array(pred_all), wrong


def main():
    items = list_images()
    counts = {c: sum(1 for _, k in items if k == c) for c in CLASSES}
    print("Photos found:", counts)
    for c, n in counts.items():
        if n < 5:
            sys.exit(f"Need at least 5 photos in dataset/{c} (found {n}); 20+ is much better.")
    print("Extracting MobileNetV2 features (this is the slow step)...")
    X, y, src, kind = build_features(items)
    print("Total training views:", len(y))

    from sklearn.metrics import confusion_matrix, f1_score
    best = None
    print("\nChoosing the best setting with leave-one-photo-out testing...")
    for C in (0.3, 1.0, 3.0, 10.0):
        t, p, wrong = cross_validate(items, X, y, src, kind, C)
        acc = float((t == p).mean()); f1 = float(f1_score(t, p, average="macro"))
        print(f"  C={C:<5} accuracy={acc:.3f}  macro-F1={f1:.3f}")
        if best is None or f1 > best[0]:
            best = (f1, C, acc, t, p, wrong)
    f1, C, acc, t, p, wrong = best
    cm = confusion_matrix(t, p, labels=range(len(CLASSES)))
    print(f"\nBest C={C}  held-out accuracy={acc:.1%}  macro-F1={f1:.3f}")
    print("Confusion matrix (rows = true, cols = predicted):", [DISPLAY[c] for c in CLASSES])
    print(cm)
    if wrong:
        print("Mistakes on unseen photos:")
        for w in wrong:
            print("  ", w)

    clf = fit_head(X, y, C)
    os.makedirs(OUT_DIR, exist_ok=True)
    np.savez(os.path.join(OUT_DIR, "civic_classifier.npz"),
             coef=clf.coef_.astype(np.float32), intercept=clf.intercept_.astype(np.float32))
    json.dump({"classes": [DISPLAY[c] for c in CLASSES]}, open(os.path.join(OUT_DIR, "labels.json"), "w"))
    report = {"photos_per_class": counts, "training_views": int(len(y)), "C": C,
              "heldout_accuracy": acc, "macro_f1": f1,
              "confusion_matrix": cm.tolist(), "class_order": [DISPLAY[c] for c in CLASSES],
              "mistakes": [list(w) for w in wrong]}
    json.dump(report, open(os.path.join(OUT_DIR, "training_report.json"), "w"), indent=2)
    print("\nSaved model/civic_classifier.npz, model/labels.json, model/training_report.json")


if __name__ == "__main__":
    main()
