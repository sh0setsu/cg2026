"""ЛР4, вариант 13: 1) Сазерленд-Коэн; 2) отсечение выпуклого многоугольника."""

import math
import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import clipping as cl

C_WIN = "#1f5fbf"
# окно / отсекатель
C_SRC = "#d9534f"
# исходные данные
C_VIS = "#1a9f3a"
# видимая часть
C_SEL = "#f0a000"
# выделение

SAMPLE_SEG = """
# число отрезков
8
# x1 y1 x2 y2
2 2 8 6
-3 4 5 4
4 -3 4 12
-2 -2 12 10
-3 6 3 12
12 1 15 5
-4 9 -1 12
1 7 11 1
# окно: xmin ymin xmax ymax
0 0 10 8
"""

SAMPLE_POLY = """
# отсекаемый многоугольник:
4
3 3
9 3
9 9
3 9
# отсекатель (выпуклый):
4
0 0
6 0
6 6
0 6
"""

MODES = ["Часть 1: Сазерленд–Коэн (отрезки, прямоугольное окно)",
         "Часть 2: отсечение выпуклого многоугольника"]

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def nice_step(s, target=60.0):
    raw = target / s
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if m * mag >= raw:
            return m * mag

def label(v):
    return format(round(v, 10), "g")

class App(object):
    def __init__(self, root):
        self.root = root
        root.title("ЛР4 (вариант 13): отсечение отрезков и многоугольников")
        root.geometry("1280x780")
        root.minsize(1000, 600)
        self.mode = 0
        self.s, self.ox, self.oy = 40.0, 100.0, 400.0
        self.need_fit = True
        self.segs, self.win, self.seg_res, self.seg_log = [], (0, 0, 1, 1), [], []
        self.sel = None
        self.subject, self.clip, self.stages, self.edge_logs = [], [], [], []
        self.stage = 0
        self._pan = None
        self._build()
        self.txt.insert("1.0", SAMPLE_SEG)
        self.apply()


# интерфейс
    def _build(self):
        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True)
        left = ttk.Frame(paned, padding=6, width=440)
        left.pack_propagate(False)
        right = ttk.Frame(paned)
        paned.add(left, weight=0)
        paned.add(right, weight=1)

        self.cb = ttk.Combobox(left, state="readonly", values=MODES)
        self.cb.current(0)
        self.cb.pack(fill="x")
        self.cb.bind("<<ComboboxSelected>>", self.on_mode)

        row = ttk.Frame(left)
        row.pack(fill="x", pady=4)
        for text, cmd in (("Открыть…", self.open_file),
                          ("Сохранить…", self.save_file),
                          ("Пример", self.load_sample),
                          ("Случайный", self.load_random)):
            ttk.Button(row, text=text, command=cmd).pack(
                side="left", expand=True, fill="x")

        ttk.Label(left, text="Входные данные (можно редактировать):").pack(anchor="w")
        f = ttk.Frame(left)
        f.pack(fill="x")
        self.txt = tk.Text(f, height=11, width=40, font=("Consolas", 10), undo=True)
        sb = ttk.Scrollbar(f, command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.txt.pack(side="left", fill="x", expand=True)
        self.txt.bind("<Control-Return>", lambda e: (self.apply(), "break")[1])
        ttk.Button(left, text="Применить и отсечь (Ctrl+Enter)",
                   command=self.apply).pack(fill="x", pady=3)

        self.v_grid = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text="Сетка", variable=self.v_grid,
                        command=self.redraw).pack(anchor="w")
        ttk.Button(left, text="Вписать в окно", command=self.fit).pack(fill="x")

        self.lbl = ttk.Label(left, text="", wraplength=420, justify="left")
        self.lbl.pack(fill="x", pady=3)


# режим 1: список отрезков
        self.f_seg = ttk.Frame(left)
        ttk.Label(self.f_seg, text="Отрезки (выберите, чтобы увидеть шаги):").pack(anchor="w")
        fl = ttk.Frame(self.f_seg)
        fl.pack(fill="x")
        self.lb = tk.Listbox(fl, height=7, exportselection=False,
                             font=("Consolas", 9))
        sb2 = ttk.Scrollbar(fl, command=self.lb.yview)
        self.lb.configure(yscrollcommand=sb2.set)
        sb2.pack(side="right", fill="y")
        self.lb.pack(side="left", fill="x", expand=True)
        self.lb.bind("<<ListboxSelect>>", self.on_list)


# режим 2: шаги по рёбрам
        self.f_poly = ttk.Frame(left)
        self.scale = tk.Scale(self.f_poly, from_=0, to=1, orient="horizontal",
                              label="Шаг: 0 - исходный, k - после k-го ребра отсекателя",
                              command=self.on_stage)
        self.scale.pack(fill="x")

        self.trace_label = ttk.Label(left, text="Ход алгоритма:")
        self.trace_label.pack(anchor="w")
        ft = ttk.Frame(left)
        ft.pack(fill="both", expand=True)
        self.trace = tk.Text(ft, height=10, width=40, font=("Consolas", 9),
                             state="disabled", wrap="word")
        sb3 = ttk.Scrollbar(ft, command=self.trace.yview)
        self.trace.configure(yscrollcommand=sb3.set)
        sb3.pack(side="right", fill="y")
        self.trace.pack(side="left", fill="both", expand=True)

        self.cv = tk.Canvas(right, bg="white", highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.v_cur = tk.StringVar()
        ttk.Label(right, textvariable=self.v_cur, font=("Consolas", 10)).pack(anchor="w", padx=6)
        ttk.Label(right, foreground="#555",
                  text="Колесо - масштаб, перетаскивание мышью - сдвиг.").pack(anchor="w", padx=6)
        self.cv.bind("<Configure>", self.on_configure)
        self.cv.bind("<Motion>", self.on_motion)
        self.cv.bind("<ButtonPress-1>", self.on_pan_start)
        self.cv.bind("<ButtonPress-3>", self.on_pan_start)
        self.cv.bind("<B1-Motion>", self.on_pan)
        self.cv.bind("<B3-Motion>", self.on_pan)
        self.cv.bind("<MouseWheel>", self.on_wheel)

        self.f_seg.pack(fill="x", before=self.trace_label)

    def status(self, text, error=False):
        self.lbl.config(text=text, foreground="#c00000" if error else "black")

    def set_trace(self, text):
        self.trace.config(state="normal")
        self.trace.delete("1.0", "end")
        self.trace.insert("1.0", text)
        self.trace.config(state="disabled")

    def set_mode_ui(self, mode):
        self.mode = mode
        self.cb.current(mode)
        self.f_seg.pack_forget()
        self.f_poly.pack_forget()
        frame = self.f_seg if mode == 0 else self.f_poly
        frame.pack(fill="x", before=self.trace_label)


# данные
    def on_mode(self, _e=None):
        self.set_mode_ui(self.cb.current())
        self.load_sample()

    def load_sample(self):
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", SAMPLE_SEG if self.mode == 0 else SAMPLE_POLY)
        self.apply()

    def load_random(self):
        r = random.Random()
        if self.mode == 0:
            n = r.randint(6, 12)
            lines = ["# число отрезков", str(n), "# x1 y1 x2 y2"]
            for _ in range(n):
                lines.append("%.1f %.1f %.1f %.1f"
                             % tuple(r.uniform(-6, 16) for _ in range(4)))
            lines += ["# окно: xmin ymin xmax ymax", "2 2 12 9"]
        else:
            def poly(cx, cy, rad, n, regular):
                if regular:
                    a0 = r.uniform(0, 6.28)
                    angs = [a0 + 2 * math.pi * i / n for i in range(n)]
                else:
                    angs = sorted(r.uniform(0, 2 * math.pi) for _ in range(n))
                return [(cx + rad * math.cos(a), cy + rad * math.sin(a)) for a in angs]
            sub = poly(r.uniform(-2, 2), r.uniform(-2, 2), r.uniform(6, 9), r.randint(3, 8), False)
            clp = poly(0, 0, r.uniform(4, 6), r.randint(3, 7), True)
            lines = ["# отсекаемый многоугольник", str(len(sub))]
            lines += ["%.2f %.2f" % p for p in sub]
            lines += ["# отсекатель", str(len(clp))]
            lines += ["%.2f %.2f" % p for p in clp]
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", "\n".join(lines) + "\n")
        self.apply()

    def open_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8-sig") as f:
                data = f.read()
        except Exception as e:
            messagebox.showerror("Ошибка", "Не удалось прочитать файл:\n%s" % e)
            return
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", data)
        self.apply()

    def save_file(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            filetypes=[("Текстовые файлы", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.txt.get("1.0", "end"))


# вычисление
    def _compute(self, mode, text):
        """Разбирает текст и вычисляет результат; self не меняет."""
        if mode == 0:
            segs, win = cl.parse_segments(text)
            res, logs = [], []
            for s in segs:
                r, lg = cl.cohen_sutherland(s[0], s[1], s[2], s[3], win)
                res.append(r)
                logs.append(lg)
            return segs, win, res, logs
        subject, clip = cl.parse_polygons(text)
        clip_ccw, stages, logs = cl.clip_polygon(subject, clip)
        return subject, clip_ccw, stages, logs

    def apply(self):
        text = self.txt.get("1.0", "end")
        mode = self.mode
        try:
            data = self._compute(mode, text)
        except ValueError as e1:
            try:
# вдруг открыт файл другого типа
                data = self._compute(1 - mode, text)
                mode = 1 - mode
            except ValueError:
                self.status("Ошибка: %s" % e1, True)
                return
        self.set_mode_ui(mode)
        if mode == 0:
            self.segs, self.win, self.seg_res, self.seg_log = data
            self.lb.delete(0, "end")
            for i, (s, r) in enumerate(zip(self.segs, self.seg_res)):
                head = "%2d: %s–%s" % (i + 1, cl.pt(s[:2]), cl.pt(s[2:]))
                tail = "вне окна" if r is None else \
                    ("виден целиком" if tuple(r) == tuple(s) else "обрезан")
                self.lb.insert("end", "%s  %s" % (head, tail))
            vis = sum(1 for r in self.seg_res if r)
            self.status("Отрезков: %d; видимых (полностью или частично): %d; "
                        "полностью отброшено: %d." % (len(self.segs), vis,
                                                      len(self.segs) - vis))
            self.sel = 0 if self.segs else None
            if self.sel is not None:
                self.lb.selection_set(0)
            self.show_seg_trace()
        else:
            self.subject, self.clip, self.stages, self.edge_logs = data
            m = len(self.clip)
            self.scale.config(to=m)
            self.stage = m
            self.scale.set(m)
            msg = "Результат: %d вершин." % len(self.stages[-1])
            if not cl.is_convex(self.subject):
                msg += (" Отсекаемый многоугольник невыпуклый: алгоритм работает, "
                        "но результат может содержать лишние рёбра вдоль границы.")
            if not self.stages[-1]:
                msg = "Многоугольник целиком вне отсекателя: результат пуст."
            self.status(msg)
            self.show_poly_trace()
        self.need_fit = True
        self.fit()


# журнал
    def show_seg_trace(self):
        if self.sel is None:
            self.set_trace("")
            return
        i = self.sel
        s = self.segs[i]
        lines = ["Отрезок %d: %s–%s" % (i + 1, cl.pt(s[:2]), cl.pt(s[2:])),
                 "Коды: бит 3 - верх, 2 - низ, 1 - право, 0 - лево", ""]
        lines += [t for t, _p in self.seg_log[i]]
        r = self.seg_res[i]
        lines.append("")
        lines.append("Итог: " + ("отрезок отброшен" if r is None else
                                 "видимая часть %s–%s" % (cl.pt(r[:2]), cl.pt(r[2:]))))
        self.set_trace("\n".join(lines))

    def show_poly_trace(self):
        k = self.stage
        if k == 0:
            lines = ["Исходный многоугольник (%d вершин):" % len(self.subject)]
            lines += ["  " + cl.pt(p) for p in self.subject]
            lines += ["", "Отсекатель обходится против часовой стрелки, "
                      "внутренняя часть - слева от каждого ребра:"]
            lines += ["  " + cl.pt(p) for p in self.clip]
        else:
            lines = self.edge_logs[k - 1]
        self.set_trace("\n".join(lines))

    def on_list(self, _e=None):
        sel = self.lb.curselection()
        if sel:
            self.sel = sel[0]
            self.show_seg_trace()
            self.redraw()

    def on_stage(self, v):
        if not self.stages:
            return
        k = int(float(v))
        if k != self.stage:
            self.stage = k
            self.show_poly_trace()
            self.redraw()


# вид
    def px(self, x):
        return self.ox + x * self.s

    def py(self, y):
        return self.oy - y * self.s

    def points(self):
        if self.mode == 0:
            pts = [(self.win[0], self.win[1]), (self.win[2], self.win[3])]
            for s in self.segs:
                pts += [s[:2], s[2:]]
        else:
            pts = list(self.subject) + list(self.clip)
        return pts

    def fit(self):
        pts = self.points() + [(0, 0)]
        w = max(self.cv.winfo_width(), 200)
        h = max(self.cv.winfo_height(), 200)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        bw = max(max(xs) - min(xs), 1e-6)
        bh = max(max(ys) - min(ys), 1e-6)
        self.s = min((w - 100) / bw, (h - 100) / bh)
        self.ox = w / 2 - (min(xs) + max(xs)) / 2 * self.s
        self.oy = h / 2 + (min(ys) + max(ys)) / 2 * self.s
        self.redraw()

    def on_configure(self, _e):
        if self.need_fit and self.cv.winfo_width() > 150:
            self.need_fit = False
            self.fit()
        else:
            self.redraw()

    def on_motion(self, e):
        self.v_cur.set("x = %.3f   y = %.3f   масштаб: %.1f px/ед."
                       % ((e.x - self.ox) / self.s, (self.oy - e.y) / self.s, self.s))

    def on_pan_start(self, e):
        self._pan = (e.x, e.y, self.ox, self.oy)

    def on_pan(self, e):
        if self._pan:
            self.ox = self._pan[2] + e.x - self._pan[0]
            self.oy = self._pan[3] + e.y - self._pan[1]
            self.redraw()

    def on_wheel(self, e):
        f = 1.15 if e.delta > 0 else 1 / 1.15
        new = clamp(self.s * f, 0.5, 5000)
        wx, wy = (e.x - self.ox) / self.s, (self.oy - e.y) / self.s
        self.s = new
        self.ox, self.oy = e.x - wx * new, e.y + wy * new
        self.redraw()


# рисование
    def draw_axes(self, w, h):
        c, s = self.cv, self.s
        step = nice_step(s)
        x0, x1 = -self.ox / s, (w - self.ox) / s
        y0, y1 = (self.oy - h) / s, self.oy / s
        if self.v_grid.get():
            i = math.ceil(x0 / step)
            while i * step <= x1:
                X = self.px(i * step)
                c.create_line(X, 0, X, h, fill="#e6e6e6")
                i += 1
            j = math.ceil(y0 / step)
            while j * step <= y1:
                Y = self.py(j * step)
                c.create_line(0, Y, w, Y, fill="#e6e6e6")
                j += 1
        c.create_line(0, self.oy, w - 4, self.oy, fill="black", width=2, arrow="last")
        c.create_line(self.ox, h, self.ox, 4, fill="black", width=2, arrow="last")
        ly = clamp(self.oy + 12, 10, h - 10)
        lx = clamp(self.ox - 4, 24, w - 8)
        i = math.ceil(x0 / step)
        while i * step <= x1:
            if i != 0:
                X = self.px(i * step)
                c.create_line(X, self.oy - 3, X, self.oy + 3)
                c.create_text(X, ly, text=label(i * step), font=("Arial", 8))
            i += 1
        j = math.ceil(y0 / step)
        while j * step <= y1:
            if j != 0:
                Y = self.py(j * step)
                c.create_line(self.ox - 3, Y, self.ox + 3, Y)
                c.create_text(lx, Y, text=label(j * step), font=("Arial", 8), anchor="e")
            j += 1
        c.create_text(clamp(self.ox - 8, 14, w - 8), ly, text="0", font=("Arial", 8))
        c.create_text(w - 12, clamp(self.oy - 14, 10, h - 10), text="x",
                      font=("Arial", 11, "bold"))
        c.create_text(clamp(self.ox + 14, 10, w - 10), 12, text="y",
                      font=("Arial", 11, "bold"))

    def flat(self, poly):
        out = []
        for x, y in poly:
            out += [self.px(x), self.py(y)]
        return out

    def draw_poly(self, poly, **kw):
        c = self.cv
        if len(poly) >= 3:
            c.create_polygon(self.flat(poly), **kw)
        elif len(poly) == 2:
            c.create_line(self.flat(poly), fill=kw.get("outline", "black"),
                          width=kw.get("width", 1))
        elif len(poly) == 1:
            X, Y = self.px(poly[0][0]), self.py(poly[0][1])
            c.create_oval(X - 4, Y - 4, X + 4, Y + 4, fill=kw.get("outline", "black"))

    def legend(self, items):
        y = 8
        for color, text in items:
            self.cv.create_rectangle(self.cv.winfo_width() - 250, y,
                                     self.cv.winfo_width() - 236, y + 10, fill=color, outline=color)
            self.cv.create_text(self.cv.winfo_width() - 230, y + 5, text=text,
                                anchor="w", font=("Arial", 9))
            y += 16

    def redraw(self):
        c = self.cv
        c.delete("all")
        w, h = max(c.winfo_width(), 50), max(c.winfo_height(), 50)
        self.draw_axes(w, h)
        if self.mode == 0:
            self.draw_segments()
        else:
            self.draw_polys()

    def draw_segments(self):
        c = self.cv
        x0, y0, x1, y1 = self.win
        c.create_rectangle(self.px(x0), self.py(y1), self.px(x1), self.py(y0),
                           outline=C_WIN, width=2)
        for i, s in enumerate(self.segs):
            c.create_line(self.px(s[0]), self.py(s[1]), self.px(s[2]), self.py(s[3]),
                          fill=C_SRC, dash=(4, 3))
            c.create_text(self.px(s[0]) + 8, self.py(s[1]) - 8, text=str(i + 1),
                          fill=C_SRC, font=("Arial", 8))
        for r in self.seg_res:
            if r:
                c.create_line(self.px(r[0]), self.py(r[1]), self.px(r[2]), self.py(r[3]),
                              fill=C_VIS, width=4, capstyle="round")
        if self.sel is not None and self.sel < len(self.segs):
            s = self.segs[self.sel]
            c.create_line(self.px(s[0]), self.py(s[1]), self.px(s[2]), self.py(s[3]),
                          fill=C_SEL, width=2)
            for _t, pts in self.seg_log[self.sel]:
                for (x, y) in pts:
                    X, Y = self.px(x), self.py(y)
                    c.create_oval(X - 5, Y - 5, X + 5, Y + 5, outline=C_SEL,
                                  fill="white", width=2)
        self.legend([(C_WIN, "отсекающее окно"), (C_SRC, "исходные отрезки"),
                     (C_VIS, "видимые части"), (C_SEL, "выбранный отрезок / точки пересечения")])

    def draw_polys(self):
        c = self.cv
        self.draw_poly(self.clip, outline=C_WIN, fill="", width=2)
        self.draw_poly(self.subject, outline=C_SRC, fill="", width=1, dash=(4, 3))
        k = self.stage
        if self.stages:
            cur = self.stages[k]
            self.draw_poly(cur, outline=C_VIS, fill=C_VIS, stipple="gray25", width=3)
            for (x, y) in cur:
                X, Y = self.px(x), self.py(y)
                c.create_oval(X - 3, Y - 3, X + 3, Y + 3, fill=C_VIS, outline=C_VIS)
        if k >= 1:
            m = len(self.clip)
            a, b = self.clip[k - 1], self.clip[k % m]
            c.create_line(self.px(a[0]), self.py(a[1]), self.px(b[0]), self.py(b[1]),
                          fill=C_SEL, width=4)
        self.legend([(C_WIN, "отсекатель (выпуклый)"), (C_SRC, "исходный многоугольник"),
                     (C_VIS, "результат текущего шага"), (C_SEL, "текущее ребро отсекателя")])

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()