# Алгоритмы обработки изображений. Только numpy: всё написано вручную.
import numpy as np

# ядра лапласиана (сумма коэффициентов = 0)
LAPLACE_4 = np.array([[0, 1, 0],
                      [1, -4, 1],
                      [0, 1, 0]], dtype=np.float64)
LAPLACE_8 = np.array([[1, 1, 1],
                      [1, -8, 1],
                      [1, 1, 1]], dtype=np.float64)

def to_gray(rgb):
    a = np.asarray(rgb, dtype=np.float64)
    if a.ndim == 2:
        return a
    return 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]

def to_uint8(a):
    return np.clip(np.rint(a), 0, 255).astype(np.uint8)

# СВЁРТКА И ГАУССОВО РАЗМЫТИЕ
def convolve(img, kernel):
    kh, kw = kernel.shape
    ph, pw = kh // 2, kw // 2
    H, W = img.shape[:2]
    pad = [(ph, ph), (pw, pw)] + [(0, 0)] * (img.ndim - 2)
    p = np.pad(img, pad, mode="edge")
    out = np.zeros(img.shape, dtype=np.float64)
    for dy in range(kh):
        for dx in range(kw):
            c = kernel[dy, dx]
            if c != 0:
                out += c * p[dy:dy + H, dx:dx + W]
    return out

def gaussian_kernel_1d(sigma):
    r = max(1, int(3 * sigma + 0.5))
    x = np.arange(-r, r + 1, dtype=np.float64)
    k = np.exp(-x * x / (2 * sigma * sigma))
    return k / k.sum()

def gaussian_blur(img, sigma):
    k = gaussian_kernel_1d(sigma)
    return convolve(convolve(img, k[None, :]), k[:, None])

# ВЫСОКОЧАСТОТНЫЕ ФИЛЬТРЫ (повышение резкости)
def laplacian_sharpen(img, kernel, amount):
    lap = convolve(img, kernel)
    return np.clip(img - amount * lap, 0, 255)

def unsharp_mask(img, sigma, amount):
    blurred = gaussian_blur(img, sigma)
    return np.clip(img + amount * (img - blurred), 0, 255)

def laplacian_view(gray, kernel):
    return to_uint8(128 + 2 * convolve(gray, kernel))

def sharpness(gray):
    return float(convolve(gray, LAPLACE_4).var())

def psnr(a, b):
    mse = np.mean((np.asarray(a, np.float64) - np.asarray(b, np.float64)) ** 2)
    if mse == 0:
        return float("inf")
    return 10 * np.log10(255.0 ** 2 / mse)

# ПОРОГОВАЯ ОБРАБОТКА
def _integral(a):
    s = np.zeros((a.shape[0] + 1, a.shape[1] + 1))
    s[1:, 1:] = a.cumsum(0).cumsum(1)
    return s

def local_mean_std(gray, w):
    if w % 2 == 0:
        w += 1
    H, W = gray.shape
    r = w // 2
    p = np.pad(gray, r, mode="edge")
    s1, s2 = _integral(p), _integral(p * p)

    def box(s):
        return (s[w:w + H, w:w + W] - s[0:H, w:w + W]
                - s[w:w + H, 0:W] + s[0:H, 0:W])

    n = w * w
    mean = box(s1) / n
    var = box(s2) / n - mean * mean
    return mean, np.where(var < 1e-3, 0.0, np.sqrt(var))

def niblack_threshold(gray, w, k):
    m, s = local_mean_std(gray, w)
    return m + k * s

def sauvola_threshold(gray, w, k, R=128.0):
    m, s = local_mean_std(gray, w)
    return m * (1 + k * (s / R - 1))

def otsu_threshold(gray_u8):
    hist = np.bincount(gray_u8.ravel(), minlength=256).astype(np.float64)
    p = hist / hist.sum()
    omega = np.cumsum(p)
    mu = np.cumsum(p * np.arange(256))
    mu_t = mu[-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        sb = (mu_t * omega - mu) ** 2 / (omega * (1 - omega))
    sb = np.nan_to_num(sb)
    return float(np.argmax(sb))

def binarize(gray, T):
    return np.where(gray > T - 1e-6, 255, 0).astype(np.uint8)

def seg_metrics(result, gt):
    pred = result == 0
    true = gt < 128
    tp = int(np.sum(pred & true))
    fp = int(np.sum(pred & ~true))
    fn = int(np.sum(~pred & true))
    tn = int(np.sum(~pred & ~true))
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    acc = (tp + tn) / (tp + fp + fn + tn)
    return prec, rec, f1, acc