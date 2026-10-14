"""
Лабораторная работа 1. Цветовые модели.
Вариант (нечётный): CMYK - RGB - HLS.
"""
import tkinter as tk
from tkinter import ttk, colorchooser

def rgb_to_cmyk(r, g, b):
    k = 1 - max(r, g, b)
    if k >= 1:
# чистый чёрный
        return 0.0, 0.0, 0.0, 1.0
    c = (1 - r - k) / (1 - k)
    m = (1 - g - k) / (1 - k)
    y = (1 - b - k) / (1 - k)
    return c, m, y, k

def cmyk_to_rgb(c, m, y, k):
    r = (1 - c) * (1 - k)
    g = (1 - m) * (1 - k)
    b = (1 - y) * (1 - k)
    return r, g, b

def rgb_to_hls(r, g, b, hue_default=0.0):
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    l = (mx + mn) / 2
    if d == 0:
        return hue_default, l, 0.0
    s = d / (1 - abs(2 * l - 1))
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h * 60, l, s

def hls_to_rgb(h, l, s):
    h = h % 360
    c = (1 - abs(2 * l - 1)) * s
# цветность (chroma)
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    sector = int(h // 60)
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x),
               (0, x, c), (x, 0, c), (c, 0, x)][sector % 6]
    return r + m, g + m, b + m

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

FIELDS = {
    "RGB":  [("R", 255, True), ("G", 255, True), ("B", 255, True)],
    "CMYK": [("C (%)", 100, False), ("M (%)", 100, False),
             ("Y (%)", 100, False), ("K (%)", 100, False)],
    "HLS":  [("H (°)", 360, False), ("L (%)", 100, False), ("S (%)", 100, False)],
}
TITLES = {"RGB": "RGB", "CMYK": "CMYK", "HLS": "HLS (HSL)"}

def model_to_rgb(model, v):
    if model == "RGB":
        return v[0] / 255, v[1] / 255, v[2] / 255
    if model == "CMYK":
        return cmyk_to_rgb(v[0] / 100, v[1] / 100, v[2] / 100, v[3] / 100)
    return hls_to_rgb(v[0], v[1] / 100, v[2] / 100)

def fmt(v, is_int):
    if is_int:
        return str(int(round(v)))
    v = round(v, 1)
    return str(int(v)) if v == int(v) else f"{v:.1f}"


# приложение
PAL_W, PAL_H = 180, 100
ZOOM = 2

class ColorApp:
    def __init__(self, root):
        self.root = root
        root.title("Цветовые модели: CMYK – RGB – HLS")
        root.resizable(False, False)

        self.busy = False
# защита от рекурсии при обновлении виджетов
        self.hue_keep = 0.0
# запоминаем оттенок для серых цветов
        self.drawn_s = None
# при какой S нарисована палитра
        self.vars, self.scales, self.entries = {}, {}, {}

        self._build_ui()
        self.apply("RGB", [52, 152, 219])
# стартовый цвет


# интерфейс
    def _build_ui(self):
        left = ttk.Frame(self.root, padding=10)
        left.grid(row=0, column=0, sticky="n")
        right = ttk.Frame(self.root, padding=10)
        right.grid(row=0, column=1, sticky="n")


# предпросмотр
        self.preview = tk.Canvas(left, width=PAL_W * ZOOM, height=70,
                                 highlightthickness=1, highlightbackground="#888")
        self.preview.pack()
        self.hex_label = ttk.Label(left, text="#000000", font=("Consolas", 14, "bold"))
        self.hex_label.pack(pady=4)


# палитра
        ttk.Label(left, text="Палитра: X – оттенок (H), Y – яркость (L).\n"
                             "Насыщенность (S) берётся из текущего цвета.",
                  justify="center").pack(pady=(6, 2))
        self.pal_canvas = tk.Canvas(left, width=PAL_W * ZOOM, height=PAL_H * ZOOM,
                                    cursor="crosshair", highlightthickness=1,
                                    highlightbackground="#888")
        self.pal_canvas.pack()
        self.pal_item = self.pal_canvas.create_image(0, 0, anchor="nw")
        self.mark_h = self.pal_canvas.create_line(0, 0, 0, 0, fill="black")
        self.mark_oval = self.pal_canvas.create_oval(0, 0, 0, 0,
                                                     outline="white", width=2)
        self.pal_canvas.bind("<Button-1>", self.on_palette)
        self.pal_canvas.bind("<B1-Motion>", self.on_palette)

        ttk.Button(left, text="Выбрать цвет в диалоге…",
                   command=self.open_dialog).pack(pady=8, fill="x")


# три модели
        for row, model in enumerate(("RGB", "CMYK", "HLS")):
            box = ttk.LabelFrame(right, text=TITLES[model], padding=8)
            box.grid(row=row, column=0, sticky="ew", pady=4)
            for i, (name, mx, is_int) in enumerate(FIELDS[model]):
                ttk.Label(box, text=name, width=6).grid(row=i, column=0, sticky="w")
                sc = ttk.Scale(box, from_=0, to=mx, length=260,
                               command=lambda _v, m=model: self.on_scale(m))
                sc.grid(row=i, column=1, padx=6, pady=2)
                var = tk.StringVar()
                en = tk.Entry(box, textvariable=var, width=7, justify="center")
                en.grid(row=i, column=2)
                var.trace_add("write", lambda *_a, m=model: self.on_entry(m, False))
                en.bind("<Return>", lambda _e, m=model: self.on_entry(m, True))
                en.bind("<FocusOut>", lambda _e, m=model: self.on_entry(m, True))
                self.vars[(model, i)] = var
                self.scales[(model, i)] = sc
                self.entries[(model, i)] = en


# обработчики событий
    def on_scale(self, model):
        if self.busy:
            return
        vals = []
        for i, (_n, _mx, is_int) in enumerate(FIELDS[model]):
            v = self.scales[(model, i)].get()
            vals.append(round(v) if is_int else round(v, 1))
        self.apply(model, vals)

    def on_entry(self, model, commit):
        if self.busy:
            return
        vals, ok = [], True
        for i, (_n, mx, is_int) in enumerate(FIELDS[model]):
            en = self.entries[(model, i)]
            try:
                v = float(self.vars[(model, i)].get().replace(",", "."))
                v = clamp(v, 0, mx)
                vals.append(round(v) if is_int else v)
                en.config(bg="white")
            except ValueError:
                en.config(bg="#ffb3b3")
                ok = False
        if not ok:
            if commit:
                self.apply(self.model_cur, self.vals_cur[self.model_cur])
            return
        self.apply(model, vals, skip_entries=not commit and model)

    def on_palette(self, event):
        x = clamp(event.x, 0, PAL_W * ZOOM - 1)
        y = clamp(event.y, 0, PAL_H * ZOOM - 1)
        h = x / (PAL_W * ZOOM) * 360
        l = 1 - y / (PAL_H * ZOOM)
        s = self.vals_cur["HLS"][2]
        self.apply("HLS", [h, l * 100, s])

    def open_dialog(self):
        res = colorchooser.askcolor(color=self.hex_label.cget("text"),
                                    title="Выбор цвета")
        if res and res[0]:
            self.apply("RGB", [round(c) for c in res[0]])

    def apply(self, src, src_vals, skip_entries=None):
        self.busy = True
        r, g, b = model_to_rgb(src, src_vals)
        r, g, b = clamp(r, 0, 1), clamp(g, 0, 1), clamp(b, 0, 1)

        if src == "HLS":
            self.hue_keep = src_vals[0]
        h, l, s = rgb_to_hls(r, g, b, self.hue_keep)
        c, m, y, k = rgb_to_cmyk(r, g, b)

        allv = {
            "RGB":  [r * 255, g * 255, b * 255],
            "CMYK": [c * 100, m * 100, y * 100, k * 100],
            "HLS":  [h, l * 100, s * 100],
        }
        allv[src] = list(src_vals)
        self.vals_cur = allv
        self.model_cur = src

        for model, vs in allv.items():
            for i, v in enumerate(vs):
                is_int = FIELDS[model][i][2]
                self.scales[(model, i)].set(v)
                if skip_entries != model:
                    self.vars[(model, i)].set(fmt(v, is_int))
                    self.entries[(model, i)].config(bg="white")

        hex_color = "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))
        self.preview.config(bg=hex_color)
        self.hex_label.config(text=hex_color.upper())
        self._update_palette(allv["HLS"])
        self.busy = False


# палитра
    def _update_palette(self, hls):
        h, l, s = hls[0], hls[1], hls[2]
        if self.drawn_s is None or abs(self.drawn_s - s) > 0.5:
            self.drawn_s = s
            img = tk.PhotoImage(width=PAL_W, height=PAL_H)
            rows = []
            for yy in range(PAL_H):
                ll = 1 - (yy + 0.5) / PAL_H
                row = []
                for xx in range(PAL_W):
                    rr, gg, bb = hls_to_rgb((xx + 0.5) / PAL_W * 360, ll, s / 100)
                    row.append("#%02x%02x%02x" % (round(rr * 255), round(gg * 255),
                                                  round(bb * 255)))
                rows.append("{" + " ".join(row) + "}")
            img.put(" ".join(rows))
            self.pal_img = img.zoom(ZOOM, ZOOM)
            self.pal_canvas.itemconfig(self.pal_item, image=self.pal_img)

        px = h / 360 * PAL_W * ZOOM
        py = (1 - l / 100) * PAL_H * ZOOM
        self.pal_canvas.coords(self.mark_oval, px - 6, py - 6, px + 6, py + 6)
        self.pal_canvas.coords(self.mark_h, px - 9, py, px + 9, py)
        self.pal_canvas.tag_raise(self.mark_oval)
        self.pal_canvas.tag_raise(self.mark_h)

if __name__ == "__main__":
    root = tk.Tk()
    ColorApp(root)
    root.mainloop()