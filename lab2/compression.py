# RLE (байтовый уровень, схема из лекции)
# Формат потока:
#  байт < 192            - литерал (одиночный байт)
#  байт >= 192 (11xxxxxx) - счётчик: длина = (байт & 63) + 1  (1..64), следом идёт повторяемый байт
import struct
import numpy as np
import processing as ip

MAGIC = b"RLE1"
HEADER = struct.Struct("<4sIIBB")
MAX_RUN = 64
ESC = 0xC0
# 11000000

MODES = [
    ("gray", "Градации серого, 8 бит"),
    ("bw", "Чёрно-белое (порог Оцу), значения 0/255"),
    ("rgb", "RGB, пиксели подряд (RGBRGB…)"),
    ("rgb_planar", "RGB, по плоскостям (RR…GG…BB…)"),
]

def prepare(rgb, mode):
    rgb = np.asarray(rgb, np.uint8)
    if mode in ("gray", "bw"):
        g = ip.to_uint8(ip.to_gray(rgb))
        if mode == "bw":
            g = ip.binarize(g, ip.otsu_threshold(g))
        return g, False
    return rgb, mode == "rgb_planar"

def count_runs(data):
    d = np.asarray(data, np.uint8).ravel()
    return 0 if d.size == 0 else 1 + int(np.count_nonzero(d[1:] != d[:-1]))

# кодер
def rle_encode(data):
    d = np.ascontiguousarray(data, dtype=np.uint8).ravel()
    n = d.size
    if n == 0:
        return b""

# 1. границы серий одинаковых байт
    starts = np.concatenate(([0], np.flatnonzero(d[1:] != d[:-1]) + 1))
    lengths = np.diff(np.append(starts, n))
    values = d[starts]

# 2. серии длиннее 64 режем на куски по 64
    chunks = (lengths + MAX_RUN - 1) // MAX_RUN
    run_idx = np.repeat(np.arange(starts.size), chunks)
    first = np.cumsum(chunks) - chunks
    j = np.arange(run_idx.size) - np.repeat(first, chunks)
    cnt = np.minimum(MAX_RUN, lengths[run_idx] - MAX_RUN * j)
    val = values[run_idx]

# 3. литерал только для одиночного байта < 192, остальное - пара (счётчик, байт)
    literal = (cnt == 1) & (val < ESC)
    size = np.where(literal, 1, 2)
    pos = np.cumsum(size) - size
    out = np.empty(int(size.sum()), np.uint8)
    out[pos[literal]] = val[literal]
    e = ~literal
    out[pos[e]] = ESC | (cnt[e] - 1)
    out[pos[e] + 1] = val[e]
    return out.tobytes()

# декодер
def rle_decode(code, expected=None):
    b = np.frombuffer(code, dtype=np.uint8)
    n = b.size
    if n == 0:
        return np.empty(0, np.uint8)
    idx = np.arange(n)
    hi = b >= ESC
    prev_hi = np.concatenate(([False], hi[:-1]))

    run_start = np.maximum.accumulate(np.where(hi & ~prev_hi, idx, 0))
    is_header = hi & ((idx - run_start) % 2 == 0)
    if is_header[-1]:
        raise ValueError("Поток оборван: после счётчика нет байта данных")
    is_data = np.zeros(n, bool)
    is_data[np.flatnonzero(is_header) + 1] = True
    nxt = np.append(b[1:], 0)
    vals = np.where(is_header, nxt, b)
    cnts = np.where(is_header, (b & 63).astype(np.int64) + 1, 1)
    sel = ~is_data
    out = np.repeat(vals[sel], cnts[sel]).astype(np.uint8)
    if expected is not None and out.size != expected:
        raise ValueError(f"Размер после распаковки {out.size}, ожидалось {expected}")
    return out

# контейнер .rle
def compress(arr, planar=False):
    arr = np.asarray(arr, np.uint8)
    h, w = arr.shape[:2]
    ch = 1 if arr.ndim == 2 else arr.shape[2]
    flat = arr.transpose(2, 0, 1) if (ch == 3 and planar) else arr
    return HEADER.pack(MAGIC, w, h, ch, 1 if planar else 0) + rle_encode(flat)

def decompress(blob):
    if len(blob) < HEADER.size:
        raise ValueError("Файл слишком короткий")
    magic, w, h, ch, planar = HEADER.unpack_from(blob)
    if magic != MAGIC or ch not in (1, 3):
        raise ValueError("Это не файл формата RLE1")
    flat = rle_decode(blob[HEADER.size:], w * h * ch)
    if ch == 1:
        return flat.reshape(h, w)
    if planar:
        return np.ascontiguousarray(flat.reshape(3, h, w).transpose(1, 2, 0))
    return flat.reshape(h, w, 3)