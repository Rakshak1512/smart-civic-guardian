"""
MobileNetV2 (ImageNet-pretrained) feature extractor - pure NumPy + Pillow.
No TensorFlow / PyTorch needed. Output: 1280-number feature vector per image.
"""
import os
import numpy as np
from PIL import Image

_HERE = os.path.dirname(os.path.abspath(__file__))
_WEIGHTS = os.path.join(_HERE, "model", "mobilenetv2_imagenet.npz")
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
_W = None


def _load():
    global _W
    if _W is None:
        z = np.load(_WEIGHTS)
        _W = {k: z[k] for k in z.files}
    return _W


def preprocess(img, size=224):
    """PIL image -> float32 array (224,224,3), ImageNet normalised (resize 256, centre crop 224)."""
    img = img.convert("RGB")
    w, h = img.size
    s = 256 / min(w, h)
    img = img.resize((max(256, round(w * s)), max(256, round(h * s))), Image.BILINEAR)
    w, h = img.size
    l, t = (w - size) // 2, (h - size) // 2
    img = img.crop((l, t, l + size, t + size))
    a = np.asarray(img, dtype=np.float32) / 255.0
    return (a - _MEAN) / _STD


def _relu6(x):
    return np.minimum(np.maximum(x, 0.0), 6.0)


def _pw(x, w, b):  # 1x1 conv : x (H,W,C) , w (O,C,1,1)
    h, wd, c = x.shape
    return (x.reshape(-1, c) @ w.reshape(w.shape[0], c).T + b).reshape(h, wd, -1)


def _dw(x, w, b, stride):  # depthwise 3x3, pad 1
    h, wd, c = x.shape
    p = np.pad(x, ((1, 1), (1, 1), (0, 0)))
    oh, ow = (h - 1) // stride + 1, (wd - 1) // stride + 1
    k = w.reshape(c, 3, 3)
    out = np.zeros((oh, ow, c), dtype=np.float32)
    for i in range(3):
        for j in range(3):
            out += p[i:i + stride * oh:stride, j:j + stride * ow:stride, :] * k[:, i, j]
    return out + b


def _stem(x, w, b):  # 3x3 conv stride 2 pad 1, 3->32
    p = np.pad(x, ((1, 1), (1, 1), (0, 0)))
    oh, ow = x.shape[0] // 2, x.shape[1] // 2
    cols = [p[i:i + 2 * oh:2, j:j + 2 * ow:2, :] for i in range(3) for j in range(3)]
    cols = np.concatenate(cols, axis=2).reshape(oh * ow, 27)          # order (i,j,c)
    wm = w.transpose(2, 3, 1, 0).reshape(27, -1)                        # (kh,kw,cin,cout)
    return (cols @ wm + b).reshape(oh, ow, -1)


def features(x):
    """x: (224,224,3) normalised -> (1280,) global-average-pooled feature vector."""
    W = _load()
    x = _relu6(_stem(x, W["stem_w"], W["stem_b"]))
    for idx, expand, stride, res in W["meta"]:
        idx = int(idx)
        inp = x
        if expand:
            x = _relu6(_pw(x, W[f"b{idx}_ex_w"], W[f"b{idx}_ex_b"]))
        x = _relu6(_dw(x, W[f"b{idx}_dw_w"], W[f"b{idx}_dw_b"], int(stride)))
        x = _pw(x, W[f"b{idx}_pw_w"], W[f"b{idx}_pw_b"])
        if res:
            x = x + inp
    x = _relu6(_pw(x, W["head_w"], W["head_b"]))
    return x.mean(axis=(0, 1))


def imagenet_logits(feat):
    W = _load()
    return W["imagenet_fc_w"] @ feat + W["imagenet_fc_b"]


def extract(path_or_img, flip=False):
    img = Image.open(path_or_img) if isinstance(path_or_img, (str, os.PathLike)) else path_or_img
    if flip:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    return features(preprocess(img))
