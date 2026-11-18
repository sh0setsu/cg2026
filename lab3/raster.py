# -*- coding: utf-8 -*-
"""Базовые растровые алгоритмы: пошаговый, ЦДА, Брезенхем (отрезок),
Брезенхем (окружность). Только стандартная библиотека.

Каждая функция возвращает список пикселей [(x, y), ...].
Если передан trace=[], в него добавляются пары (строка_таблицы, [пиксели шага])
для пошаговой иллюстрации. При trace=None трассировка отключена."""
import gc
import math
import time

def _round(v):
    return int(math.floor(v + 0.5))

def _f(v):
    return "%.3f" % v

def _pt(p):
    return "(%d; %d)" % (p[0], p[1])

# 1. Пошаговый алгоритм: y = k*x + b
def step_by_step(x0, y0, x1, y1, trace=None):
    pts = []
    dx = x1 - x0
    dy = y1 - y0
    if abs(dx) >= abs(dy):
        if dx == 0:
            p = (x0, y0)
            pts.append(p)
            if trace is not None:
                trace.append(((0, x0, y0, _pt(p)), [p]))
            return pts
        k = dy / dx
        b = y0 - k * x0
        step = 1 if dx > 0 else -1
        i = 0
        for x in range(x0, x1 + step, step):
            y = k * x + b
            p = (x, _round(y))
            pts.append(p)
            if trace is not None:
                trace.append(((i, x, _f(y), _pt(p)), [p]))
            i += 1
    else:
        k = dx / dy
        b = x0 - k * y0
        step = 1 if dy > 0 else -1
        i = 0
        for y in range(y0, y1 + step, step):
            x = k * y + b
            p = (_round(x), y)
            pts.append(p)
            if trace is not None:
                trace.append(((i, _f(x), y, _pt(p)), [p]))
            i += 1
    return pts

# 2. ЦДА (цифровой дифференциальный анализатор)
def dda(x0, y0, x1, y1, trace=None):
    pts = []
    dx = x1 - x0
    dy = y1 - y0
    length = max(abs(dx), abs(dy))
# число шагов
    if length == 0:
        sx = sy = 0.0
    else:
        sx = dx / length
        sy = dy / length
    x = float(x0)
    y = float(y0)
    for i in range(length + 1):
        p = (_round(x), _round(y))
        pts.append(p)
        if trace is not None:
            trace.append(((i, _f(x), _f(y), _pt(p)), [p]))
        x += sx
        y += sy
    return pts

# 3. Брезенхем (отрезок), целочисленный, все октанты
def bresenham_line(x0, y0, x1, y1, trace=None):
    pts = []
    steep = abs(y1 - y0) > abs(x1 - x0)
    if steep:
        x0, y0 = y0, x0
        x1, y1 = y1, x1
    if x0 > x1:
        x0, x1 = x1, x0
        y0, y1 = y1, y0
    dx = x1 - x0
    dy = abs(y1 - y0)
    ystep = 1 if y0 < y1 else -1
    d = 2 * dy - dx
    y = y0
    for i in range(dx + 1):
        x = x0 + i
        p = (y, x) if steep else (x, y)
        pts.append(p)
        if d > 0:
            nd = d + 2 * (dy - dx)
            ch = "y%+d" % ystep
            ynext = y + ystep
        else:
            nd = d + 2 * dy
            ch = "y"
            ynext = y
        if trace is not None:
            trace.append(((i, _pt(p), d,
                           "—" if i == dx else "%s, d'=%d" % (ch, nd)), [p]))
        d = nd
        y = ynext
    return pts

# 4. Брезенхем (окружность), первый октант + симметрия
def bresenham_circle(xc, yc, r, trace=None):
    pts = []
    x = 0
    y = r
    d = 3 - 2 * r
    i = 0
    while x <= y:
        eight = [(xc + x, yc + y), (xc - x, yc + y), (xc + x, yc - y), (xc - x, yc - y),
                 (xc + y, yc + x), (xc - y, yc + x), (xc + y, yc - x), (xc - y, yc - x)]
        pts.extend(eight)
        if d < 0:
            nd = d + 4 * x + 6
            ch = "y"
        else:
            nd = d + 4 * (x - y) + 10
            ch = "y-1"
        if trace is not None:
            trace.append(((i, x, y, d, "%s, d'=%d" % (ch, nd)), eight))
        if d >= 0:
            y -= 1
        d = nd
        x += 1
        i += 1
    return pts

ALGORITHMS = [
    ("Пошаговый алгоритм", step_by_step, ("i", "x", "y", "пиксель"), "line"),
    ("ЦДА", dda, ("i", "x", "y", "пиксель"), "line"),
    ("Брезенхем (отрезок)", bresenham_line, ("i", "пиксель", "d", "следующий"), "line"),
    ("Брезенхем (окружность)", bresenham_circle, ("i", "x", "y", "d", "следующий"), "circle"),
]

# Замер времени
def measure(func, args, min_time=0.03, repeat=5):
    """Среднее время одного вызова, с. Лучшее из repeat серий; в серии
    столько вызовов, чтобы она длилась не меньше min_time."""
    n = 1
    while True:
        t0 = time.perf_counter()
        for _ in range(n):
            func(*args)
        dt = time.perf_counter() - t0
        if dt >= min_time:
            break
        n = n * 10 if dt < 1e-4 else n * 2
    best = dt / n
    for _ in range(repeat - 1):
        t0 = time.perf_counter()
        for _ in range(n):
            func(*args)
        best = min(best, (time.perf_counter() - t0) / n)
    return best

SIZES = (50, 200, 1000, 5000)

def benchmark(callback=None):
    """Возвращает строки (алгоритм, размер, пикселей, мс, нс/пиксель)."""
    rows = []
    gc.disable()
    try:
        for title, func, _cols, kind in ALGORITHMS:
            for n in SIZES:
                if kind == "line":
                    args = (0, 0, n, int(n * 0.4))
                    label = "dx=%d, dy=%d" % (args[2], args[3])
                else:
                    args = (0, 0, n // 2)
                    label = "R=%d" % (n // 2)
                pix = len(func(*args))
                t = measure(func, args)
                rows.append((title, label, pix, "%.3f" % (t * 1000), "%.0f" % (t * 1e9 / pix)))
                if callback:
                    callback()
    finally:
        gc.enable()
    return rows