# -*- coding: utf-8 -*-
"""Алгоритмы отсечения.
Часть 1: Сазерленд-Коэн (прямая через явное уравнение y = k*x + b).
Часть 2: отсечение многоугольника выпуклым многоугольником (Сазерленд-Ходжмен).
Только стандартная библиотека."""

import math

EPS = 1e-9
LEFT, RIGHT, BOTTOM, TOP = 1, 2, 4, 8
# биты кода; запись кода: T B R L

def fmt(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s

def pt(p):
    return "(%s; %s)" % (fmt(p[0]), fmt(p[1]))

# Разбор входных данных
def _numbers(text):
    out = []
    for line in text.splitlines():
        line = line.split("#")[0]
# комментарии после '#'
        for tok in line.replace(";", " ").split():
            try:
                out.append(float(tok.replace(",", ".")))
            except ValueError:
                raise ValueError("Не число: «%s»" % tok)
    return out

def parse_segments(text):
    """n; n строк x1 y1 x2 y2; xmin ymin xmax ymax -> (segs, win)."""
    a = _numbers(text)
    if not a:
        raise ValueError("Файл пуст")
    n = a[0]
    if n != int(n) or n < 0:
        raise ValueError("Число отрезков должно быть целым неотрицательным")
    n = int(n)
    if len(a) != 1 + 4 * n + 4:
        raise ValueError("Ожидалось %d чисел (n=%d), найдено %d"
                         % (1 + 4 * n + 4, n, len(a)))
    segs = [tuple(a[1 + 4 * i: 5 + 4 * i]) for i in range(n)]
    x0, y0, x1, y1 = a[1 + 4 * n:]
    win = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    if win[0] == win[2] or win[1] == win[3]:
        raise ValueError("Окно вырождено (нулевая ширина или высота)")
    return segs, win

def parse_polygons(text):
    a = _numbers(text)
    if not a:
        raise ValueError("Файл пуст")
    polys, i = [], 0
    for _ in range(2):
        if i >= len(a) or a[i] != int(a[i]) or a[i] < 0:
            raise ValueError("Неверное число вершин")
        n = int(a[i])
        i += 1
        if i + 2 * n > len(a):
            raise ValueError("Не хватает координат вершин")
        polys.append([(a[i + 2 * j], a[i + 2 * j + 1]) for j in range(n)])
        i += 2 * n
    if i != len(a):
        raise ValueError("В файле есть лишние числа")
    if len(polys[0]) < 3 or len(polys[1]) < 3:
        raise ValueError("В многоугольнике должно быть не меньше 3 вершин")
    return polys[0], polys[1]

# Часть 1. Сазерленд-Коэн
def outcode(x, y, win):
    xmin, ymin, xmax, ymax = win
    c = 0
    if x < xmin - EPS:
        c |= LEFT
    elif x > xmax + EPS:
        c |= RIGHT
    if y < ymin - EPS:
        c |= BOTTOM
    elif y > ymax + EPS:
        c |= TOP
    return c

def code_str(c):
    return format(c, "04b")

def cohen_sutherland(x1, y1, x2, y2, win):
    xmin, ymin, xmax, ymax = win
    log = []
    if x1 == x2:
# вертикальная: x = const
        k = b = None
        log.append(("Прямая вертикальная: x = %s" % fmt(x1), []))
    else:
# явное задание прямой
        k = (y2 - y1) / (x2 - x1)
        b = y1 - k * x1
        log.append(("Прямая через отрезок: y = k·x + b, k = %s, b = %s"
                    % (fmt(k), fmt(b)), []))

    for it in range(1, 12):
# предохранитель от зацикливания
        c1, c2 = outcode(x1, y1, win), outcode(x2, y2, win)
        head = "Шаг %d: P1%s код %s, P2%s код %s" % (
            it, pt((x1, y1)), code_str(c1), pt((x2, y2)), code_str(c2))
        if (c1 | c2) == 0:
            log.append((head + "\n  оба кода 0000 → отрезок виден целиком",
                        []))
            return (x1, y1, x2, y2), log
        if c1 & c2:
            log.append((head + "\n  c1 AND c2 = %s ≠ 0 → отрезок целиком "
                        "вне окна, отбрасываем" % code_str(c1 & c2), []))
            return None, log

        first = c1 != 0
# какую точку переносим
        c = c1 if first else c2
        if c & LEFT:
            nx = xmin
            ny = k * nx + b
            side = "левой границей x = %s" % fmt(xmin)
        elif c & RIGHT:
            nx = xmax
            ny = k * nx + b
            side = "правой границей x = %s" % fmt(xmax)
        elif c & BOTTOM:
            ny = ymin
            nx = x1 if k is None else (ny - b) / k
            side = "нижней границей y = %s" % fmt(ymin)
        else:
            ny = ymax
            nx = x1 if k is None else (ny - b) / k
            side = "верхней границей y = %s" % fmt(ymax)
        name = "P1" if first else "P2"
        if first:
            x1, y1 = nx, ny
        else:
            x2, y2 = nx, ny
        log.append((head + "\n  %s вне окна: пересечение прямой с %s → %s := %s"
                    % (name, side, name, pt((nx, ny))), [(nx, ny)]))
    log.append(("Превышен лимит итераций", []))
    return None, log

# Часть 2. Отсечение выпуклого многоугольника (Сазерленд-Ходжмен)
def cross(a, b, p):
    """Векторное произведение (b-a) x (p-a): >0, если p левее ребра a->b."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])

def signed_area(poly):
    s = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return s / 2

def is_convex(poly):
    n = len(poly)
    if n < 3:
        return False
    sign, total = 0, 0.0
    for i in range(n):
        a, b, c = poly[i], poly[(i + 1) % n], poly[(i + 2) % n]
        ux, uy, vx, vy = b[0] - a[0], b[1] - a[1], c[0] - b[0], c[1] - b[1]
        cr = ux * vy - uy * vx
        dt = ux * vx + uy * vy
        if abs(cr) > EPS:
            sg = 1 if cr > 0 else -1
            if sign == 0:
                sign = sg
            elif sg != sign:
                return False
        total += math.atan2(cr, dt)
    return sign != 0 and abs(abs(total) - 2 * math.pi) < 1e-6

def _intersect(s, e, a, b):
    d1, d2 = cross(a, b, s), cross(a, b, e)
    t = d1 / (d1 - d2)
    return (s[0] + t * (e[0] - s[0]), s[1] + t * (e[1] - s[1]))

def _dedupe(poly):
    out = []
    for p in poly:
        if not out or abs(p[0] - out[-1][0]) > EPS or abs(p[1] - out[-1][1]) > EPS:
            out.append(p)
    while len(out) > 1 and abs(out[0][0] - out[-1][0]) <= EPS \
            and abs(out[0][1] - out[-1][1]) <= EPS:
        out.pop()
    return out

def clip_polygon(subject, clip):
    if abs(signed_area(clip)) < EPS:
        raise ValueError("Отсекатель вырожден (нулевая площадь)")
    if not is_convex(clip):
        raise ValueError("Отсекатель не является выпуклым многоугольником")
    clip = list(clip)
    if signed_area(clip) < 0:
        clip.reverse()
# внутренность всегда слева от ребра
    stages = [list(subject)]
    logs = []
    out = list(subject)
    m = len(clip)
    for i in range(m):
        a, b = clip[i], clip[(i + 1) % m]
        lines = ["Ребро %d отсекателя: %s → %s; вход: %d вершин"
                 % (i + 1, pt(a), pt(b), len(out))]
        inp, out = out, []
        if inp:
            s = inp[-1]
            for e in inp:
                ins_s = cross(a, b, s) >= -EPS
                ins_e = cross(a, b, e) >= -EPS
                if ins_e and ins_s:
                    out.append(e)
                    act = "оба внутри → E"
                elif ins_e:
                    p = _intersect(s, e, a, b)
                    out += [p, e]
                    act = "вход в область → пересечение %s, E" % pt(p)
                elif ins_s:
                    p = _intersect(s, e, a, b)
                    out.append(p)
                    act = "выход из области → пересечение %s" % pt(p)
                else:
                    act = "оба снаружи → ничего"
                lines.append("  S%s → E%s: %s" % (pt(s), pt(e), act))
                s = e
        out = _dedupe(out)
        lines.append("Результат шага: %d вершин" % len(out))
        for p in out:
            lines.append("  " + pt(p))
        stages.append(list(out))
        logs.append(lines)
    return clip, stages, logs