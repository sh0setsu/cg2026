"""ЛР3. Базовые растровые алгоритмы: пошаговый, ЦДА, Брезенхем (отрезок и окружность)."""
import math
import tkinter as tk
from tkinter import ttk, messagebox

import raster

LIMIT = 2000
# максимальная |координата| / радиус
MAX_ROWS = 3000
# сколько строк трассировки показывать в таблице
S_MIN, S_MAX = 4, 80
# масштаб, пикселей экрана на клетку

HELP = (
    "Привязка целых координат к сетке\n\n"
    "• Растровый пиксель (x; y) - это клетка сетки. Целые координаты (x; y) "
    "соответствуют ЦЕНТРУ клетки.\n"
    "• Границы клеток проходят по полуцелым значениям (x ± 0,5, y ± 0,5): "
    "именно там нарисованы линии сетки.\n"
    "• Оси X и Y проходят через центры клеток с x = 0 и y = 0. Подписи "
    "на осях - целые числа, они стоят под центрами клеток.\n"
    "• Преобразование в экранные координаты: X = ox + x·s, Y = oy − y·s, "
    "где s - масштаб (пикселей экрана на клетку), (ox, oy) - положение "
    "начала координат на экране. Минус у y - потому что на экране ось Y "
    "направлена вниз, а в системе координат - вверх.\n"
    "• Обратно: x = round((X − ox)/s), y = round((oy − Y)/s).\n"
    "• Красная линия - идеальный (математический) отрезок или окружность; "
    "закрашенные клетки - то, что построил алгоритм.\n\n"
    "Управление\n"
    "• Левая кнопка мыши по полотну: задать точку (для отрезка - начало, "
    "затем конец; для окружности - центр).\n"
    "• Правая кнопка + движение: сдвиг. Колесо: масштаб.\n"
    "• Клик по строке таблицы: показать построение до этого шага.")

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

class App(object):
    def __init__(self, root):
        self.root = root
        root.title("ЛР3: базовые растровые алгоритмы")
        root.geometry("1200x720")
        root.minsize(900, 600)

        self.scale = 30.0
        self.ox = 100.0
        self.oy = 400.0
        self.pts = []
        self.steps = []
        self.shown = 0
        self.params = None
        self.kind = "line"
        self.click_n = 0
        self._lock = False
        self._pan = None

        self._build()
        root.update_idletasks()
        self.on_example()


#интерфейс
    def _build(self):
        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True)
        left = ttk.Frame(paned, padding=6, width=430)
        left.pack_propagate(False)
        right = ttk.Frame(paned)
        paned.add(left, weight=0)
        paned.add(right, weight=1)


# алгоритм
        box = ttk.LabelFrame(left, text="Алгоритм", padding=4)
        box.pack(fill="x")
        self.cb = ttk.Combobox(box, state="readonly",
                               values=[a[0] for a in raster.ALGORITHMS])
        self.cb.current(0)
        self.cb.pack(fill="x")
        self.cb.bind("<<ComboboxSelected>>", self.on_algo)


# параметры
        box = ttk.LabelFrame(left, text="Параметры (целые числа)", padding=4)
        box.pack(fill="x", pady=4)
        self.vars = [tk.StringVar() for _ in range(4)]
        self.lbls, self.ents = [], []
        for i in range(4):
            r, c = divmod(i, 2)
            lb = ttk.Label(box, text="")
            lb.grid(row=r, column=c * 2, sticky="e", padx=(6, 2), pady=2)
            en = ttk.Entry(box, textvariable=self.vars[i], width=7, justify="center")
            en.grid(row=r, column=c * 2 + 1, padx=(0, 10))
            en.bind("<Return>", lambda e: self.build(True))
            self.lbls.append(lb)
            self.ents.append(en)

        row = ttk.Frame(left)
        row.pack(fill="x")
        ttk.Button(row, text="Построить", command=lambda: self.build(True)).pack(side="left", expand=True, fill="x")
        ttk.Button(row, text="Пример", command=self.on_example).pack(side="left", expand=True, fill="x")
        row = ttk.Frame(left)
        row.pack(fill="x", pady=2)
        ttk.Button(row, text="◀ Шаг", command=lambda: self.move(-1)).pack(side="left", expand=True, fill="x")
        ttk.Button(row, text="Шаг ▶", command=lambda: self.move(1)).pack(side="left", expand=True, fill="x")
        ttk.Button(row, text="Всё", command=lambda: self.move(10 ** 9)).pack(side="left", expand=True, fill="x")
        ttk.Button(row, text="Сброс", command=lambda: self.move(-10 ** 9)).pack(side="left", expand=True, fill="x")


# опции
        self.v_ideal = tk.BooleanVar(value=True)
        self.v_labels = tk.BooleanVar(value=True)
        self.v_auto = tk.BooleanVar(value=True)
        for text, var in (("Идеальная линия (красная)", self.v_ideal),
                          ("Координаты в клетках (при крупном масштабе)", self.v_labels),
                          ("Автоподбор масштаба при построении", self.v_auto)):
            ttk.Checkbutton(left, text=text, variable=var, command=self.redraw).pack(anchor="w")

        self.v_scale = tk.DoubleVar(value=self.scale)
        tk.Scale(left, from_=S_MIN, to=S_MAX, resolution=1, orient="horizontal",
                 label="Масштаб, пикселей экрана на клетку",
                 variable=self.v_scale, command=self.on_scale).pack(fill="x")

        row = ttk.Frame(left)
        row.pack(fill="x")
        ttk.Button(row, text="Замер времени…", command=self.bench).pack(side="left", expand=True, fill="x")
        ttk.Button(row, text="Справка", command=lambda: messagebox.showinfo("Справка", HELP)).pack(
            side="left", expand=True, fill="x")

        self.lbl_status = ttk.Label(left, text="", wraplength=410, justify="left")
        self.lbl_status.pack(fill="x", pady=4)


# таблица трассировки
        frm = ttk.Frame(left)
        frm.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frm, show="headings", height=8)
        sb = ttk.Scrollbar(frm, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_row)


# полотно
        self.cv = tk.Canvas(right, bg="white", highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.v_cursor = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.v_cursor, font=("Consolas", 10)).pack(anchor="w", padx=6)
        ttk.Label(right, foreground="#555",
                  text="Целая координата (x; y) = центр клетки-пикселя; линии сетки - на полуцелых "
                       "значениях; экран: X = ox + x·s, Y = oy − y·s. Подробнее - «Справка».").pack(
            anchor="w", padx=6, pady=(0, 4))
        self.cv.bind("<Configure>", lambda e: self.redraw())
        self.cv.bind("<Motion>", self.on_motion)
        self.cv.bind("<Button-1>", self.on_click)
        self.cv.bind("<ButtonPress-3>", self.on_pan_start)
        self.cv.bind("<B3-Motion>", self.on_pan)
        self.cv.bind("<MouseWheel>", self.on_wheel)


# вспомогательное
    def status(self, text, error=False):
        self.lbl_status.config(text=text, foreground="#c00000" if error else "black")

    def algo(self):
        return raster.ALGORITHMS[self.cb.current()]

    def set_labels(self, kind):
        names = ("x0", "y0", "x1", "y1") if kind == "line" else ("xc", "yc", "R", "")
        for i in range(4):
            self.lbls[i].config(text=names[i])
            if names[i]:
                self.lbls[i].grid()
                self.ents[i].grid()
            else:
                self.lbls[i].grid_remove()
                self.ents[i].grid_remove()

    def read_params(self):
        kind = self.algo()[3]
        n = 4 if kind == "line" else 3
        try:
            vals = [int(self.vars[i].get().strip()) for i in range(n)]
        except ValueError:
            self.status("Ошибка: все параметры должны быть целыми числами.", True)
            return None
        if any(abs(v) > LIMIT for v in vals):
            self.status("Ошибка: |значение| не должно превышать %d." % LIMIT, True)
            return None
        if kind == "circle" and vals[2] < 0:
            self.status("Ошибка: радиус не может быть отрицательным.", True)
            return None
        return tuple(vals)

    def set_scale(self, s, notify=False):
        self.scale = float(clamp(s, S_MIN, S_MAX))
        self._lock = True
        self.v_scale.set(self.scale)
        self._lock = False


# построение
    def on_algo(self, _e=None):
        new_kind = self.algo()[3]
        if new_kind != self.kind:
            self.on_example()
        else:
            self.build(False)

    def on_example(self):
        kind = self.algo()[3]
        self.kind = kind
        self.set_labels(kind)
        vals = (1, 1, 8, 5) if kind == "line" else (0, 0, 6, 0)
        for i in range(4):
            self.vars[i].set(str(vals[i]))
        self.build(True)

    def build(self, fit):
        p = self.read_params()
        if p is None:
            return
        title, func, cols, kind = self.algo()
        self.kind = kind
        trace = []
        pts = func(*p, trace=trace)
        t = raster.measure(func, p, min_time=0.01, repeat=3)
        self.params = (kind, p)
        self.pts = pts
        self.steps = trace
        self.shown = len(trace)
        self.click_n = 0


# таблица
        self.tree.delete(*self.tree.get_children())
        self.tree.configure(columns=cols)
        w = (390 - 40) // (len(cols) - 1)
        for j, c in enumerate(cols):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=40 if j == 0 else w, anchor="center", stretch=(j == len(cols) - 1))
        for i, (row, _px) in enumerate(trace[:MAX_ROWS]):
            self.tree.insert("", "end", iid=str(i), values=row)

        n_unique = len(set(pts))
        txt = "Пикселей: %d; шагов: %d; время построения: %.1f мкс (без трассировки)." % (
            n_unique, len(trace), t * 1e6)
        if len(trace) > MAX_ROWS:
            txt += " В таблице показаны первые %d шагов." % MAX_ROWS
        self.status(txt)

        if fit and self.v_auto.get():
            self.fit()
        self.sync()

    def fit(self):
        if not self.pts:
            return
        w = max(self.cv.winfo_width(), 100)
        h = max(self.cv.winfo_height(), 100)
        xs = [q[0] for q in self.pts]
        ys = [q[1] for q in self.pts]
        minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
        s = min(w / (maxx - minx + 5.0), h / (maxy - miny + 5.0))
        self.set_scale(int(s))
        self.ox = w / 2.0 - (minx + maxx) / 2.0 * self.scale
        self.oy = h / 2.0 + (miny + maxy) / 2.0 * self.scale


# пошаговый показ
    def move(self, delta):
        self.shown = clamp(self.shown + delta, 0, len(self.steps))
        self.sync()

    def sync(self):
        self._lock = True
        sel = self.shown - 1
        self.tree.selection_remove(*self.tree.selection())
        if 0 <= sel < MAX_ROWS and sel < len(self.steps):
            self.tree.selection_set(str(sel))
            self.tree.see(str(sel))
        self._lock = False
        self.redraw()

    def on_row(self, _e=None):
        if self._lock:
            return
        sel = self.tree.selection()
        if sel:
            self.shown = int(sel[0]) + 1
            self.redraw()


# мышь
    def cell(self, X, Y):
        return (int(round((X - self.ox) / self.scale)), int(round((self.oy - Y) / self.scale)))

    def on_motion(self, e):
        x, y = self.cell(e.x, e.y)
        self.v_cursor.set("курсор: клетка (x = %d; y = %d)    масштаб: %d px/клетку" % (x, y, self.scale))

    def on_click(self, e):
        x, y = self.cell(e.x, e.y)
        if abs(x) > LIMIT or abs(y) > LIMIT:
            return
        if self.kind == "line":
            if self.click_n % 2 == 0:
                vals = (x, y, x, y)
            else:
                vals = (int(self.vars[0].get() or 0), int(self.vars[1].get() or 0), x, y)
            n = self.click_n + 1
            for i in range(4):
                self.vars[i].set(str(vals[i]))
            self.build(False)
            self.click_n = n
        else:
            self.vars[0].set(str(x))
            self.vars[1].set(str(y))
            self.build(False)

    def on_pan_start(self, e):
        self._pan = (e.x, e.y, self.ox, self.oy)

    def on_pan(self, e):
        if self._pan:
            self.ox = self._pan[2] + e.x - self._pan[0]
            self.oy = self._pan[3] + e.y - self._pan[1]
            self.redraw()

    def on_wheel(self, e):
        old = self.scale
        new = clamp(old + (2 if e.delta > 0 else -2), S_MIN, S_MAX)
        if new == old:
            return
        wx = (e.x - self.ox) / old
        wy = (self.oy - e.y) / old
        self.set_scale(new)
        self.ox = e.x - wx * new
        self.oy = e.y + wy * new
        self.redraw()

    def on_scale(self, val):
        if self._lock:
            return
        old = self.scale
        new = float(val)
        w = self.cv.winfo_width()
        h = self.cv.winfo_height()
        wx = (w / 2.0 - self.ox) / old
        wy = (self.oy - h / 2.0) / old
        self.scale = new
        self.ox = w / 2.0 - wx * new
        self.oy = h / 2.0 + wy * new
        self.redraw()


# отрисовка
    def redraw(self):
        c = self.cv
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        s, ox, oy = self.scale, self.ox, self.oy
        xmin = int(math.floor(-ox / s)) - 1
        xmax = int(math.ceil((w - ox) / s)) + 1
        ymax = int(math.ceil(oy / s)) + 1
        ymin = int(math.floor((oy - h) / s)) - 1


# 1. закрашенные клетки (под сеткой, чтобы линии были видны)
        done = set()
        for _row, px in self.steps[:max(self.shown - 1, 0)]:
            done.update(px)
        last = set(self.steps[self.shown - 1][1]) if 0 < self.shown <= len(self.steps) else set()
        for group, colour in ((done, "#8db8e8"), (last, "#f6a623")):
            for (x, y) in group:
                if xmin <= x <= xmax and ymin <= y <= ymax:
                    c.create_rectangle(ox + (x - 0.5) * s, oy - (y + 0.5) * s,
                                       ox + (x + 0.5) * s, oy - (y - 0.5) * s,
                                       fill=colour, outline="")


# 2. линии сетки на границах клеток (полуцелые значения)
        gstep = 1 if s >= 6 else 5
        for i in range(xmin, xmax + 1):
            if i % gstep == 0:
                X = ox + (i - 0.5) * s
                c.create_line(X, 0, X, h, fill="#d0d0d0")
        for j in range(ymin, ymax + 1):
            if j % gstep == 0:
                Y = oy - (j - 0.5) * s
                c.create_line(0, Y, w, Y, fill="#d0d0d0")


# 3. идеальная фигура
        if self.v_ideal.get() and self.params:
            kind, p = self.params
            if kind == "line":
                c.create_line(ox + p[0] * s, oy - p[1] * s, ox + p[2] * s, oy - p[3] * s,
                              fill="#d00000", width=2)
            else:
                c.create_oval(ox + (p[0] - p[2]) * s, oy - (p[1] + p[2]) * s,
                              ox + (p[0] + p[2]) * s, oy - (p[1] - p[2]) * s,
                              outline="#d00000", width=2)


# 4. подписи координат внутри клеток
        if self.v_labels.get() and s >= 42:
            for (x, y) in done | last:
                if xmin <= x <= xmax and ymin <= y <= ymax:
                    c.create_text(ox + x * s, oy - y * s, text="%d;%d" % (x, y),
                                  font=("Arial", 8), fill="#222")


# 5. оси
        c.create_line(0, oy, w - 4, oy, fill="black", width=2, arrow="last")
        c.create_line(ox, h, ox, 4, fill="black", width=2, arrow="last")


# 6. подписи и засечки (прижимаются к краю, если ось вне окна)
        lstep = 1 if s >= 28 else 2 if s >= 14 else 5 if s >= 7 else 10
        ly = clamp(oy + 12, 10, h - 10)
        lx = clamp(ox - 12, 16, w - 16)
        for i in range(xmin, xmax + 1):
            if i % lstep == 0 and i != 0:
                X = ox + i * s
                c.create_line(X, oy - 3, X, oy + 3, fill="black")
                c.create_text(X, ly, text=str(i), font=("Arial", 8))
        for j in range(ymin, ymax + 1):
            if j % lstep == 0 and j != 0:
                Y = oy - j * s
                c.create_line(ox - 3, Y, ox + 3, Y, fill="black")
                c.create_text(lx, Y, text=str(j), font=("Arial", 8))
        c.create_text(clamp(ox - 10, 16, w - 16), clamp(oy + 12, 10, h - 10), text="0", font=("Arial", 8))
        c.create_text(w - 12, clamp(oy - 14, 10, h - 10), text="x", font=("Arial", 11, "bold"))
        c.create_text(clamp(ox + 14, 10, w - 10), 12, text="y", font=("Arial", 11, "bold"))


# 7. прогресс
        if self.steps:
            c.create_text(8, h - 8, anchor="sw", font=("Arial", 9),
                          text="показано шагов: %d из %d" % (self.shown, len(self.steps)))


# замер времени
    def bench(self):
        win = tk.Toplevel(self.root)
        win.title("Временные характеристики алгоритмов")
        lbl = ttk.Label(win, text="Идёт замер, подождите…")
        lbl.pack(padx=10, pady=6)
        win.update()
        self.root.config(cursor="watch")
        rows = raster.benchmark(callback=win.update)
        self.root.config(cursor="")
        lbl.config(text="Среднее время одного вызова (без отрисовки), лучшее из 5 серий.")
        cols = ("Алгоритм", "Размер", "Пикселей", "Время, мс", "нс на пиксель")
        tr = ttk.Treeview(win, columns=cols, show="headings", height=len(rows))
        for c, wd in zip(cols, (180, 120, 90, 100, 110)):
            tr.heading(c, text=c)
            tr.column(c, width=wd, anchor="center")
        for r in rows:
            tr.insert("", "end", values=r)
        tr.pack(padx=10, pady=4)

        def copy():
            text = "\n".join("\t".join(str(v) for v in r) for r in [cols] + rows)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)

        ttk.Button(win, text="Копировать таблицу в буфер", command=copy).pack(pady=6)

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()