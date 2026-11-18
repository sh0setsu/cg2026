# ЛР2, вариант 13:
# 1) локальная пороговая обработка: Niblack и Sauvola (+ глобальный Оцу для сравнения)
# 2) высокочастотные фильтры: лапласиан и нерезкая маска (high-boost)/
import os
import sys
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
from PIL import Image, ImageTk

import processing as ip

import io
import compression as rle

PANEL_W, PANEL_H = 400, 290
EXT = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")
MAX_SIDE = 1600

def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def load_rgb(path):
    """Открывает файл как RGB; большие фото уменьшает до MAX_SIDE."""
    img = Image.open(path).convert("RGB")
    note = ""
    if max(img.size) > MAX_SIDE:
        s = MAX_SIDE / max(img.size)
        img = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
        note = " (уменьшено)"
    return img, note

AUX_SUFFIXES = {"gt": ("__gt", "_gt", "__GT", "_GT"),
                "ref": ("__ref", "_ref")}

def is_aux(filename):
    stem = os.path.splitext(filename)[0]
    return stem.endswith(AUX_SUFFIXES["gt"] + AUX_SUFFIXES["ref"])

def find_aux(base, kind):
    for suf in AUX_SUFFIXES[kind]:
        for ext in EXT:
            p = base + suf + ext
            if os.path.exists(p):
                return p
    return None
TEST_DIR = os.path.join(app_dir(), "test_images")

def ensure_test_images():
    os.makedirs(TEST_DIR, exist_ok=True)

class ScrollFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.cv = tk.Canvas(self, highlightthickness=0)
        vs = ttk.Scrollbar(self, orient="vertical", command=self.cv.yview)
        hs = ttk.Scrollbar(self, orient="horizontal", command=self.cv.xview)
        self.cv.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side="right", fill="y")
        hs.pack(side="bottom", fill="x")
        self.cv.pack(side="left", fill="both", expand=True)

        self.inner = ttk.Frame(self.cv)
        self.cv.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>",
                        lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))

        self.cv.bind_all("<MouseWheel>", self._wheel, add="+")

    def _wheel(self, e):
        if self.winfo_ismapped():
            self.cv.yview_scroll(int(-e.delta / 120), "units")

# панель с изображением
class ImagePanel(ttk.LabelFrame):
    def __init__(self, parent, title):    
        super().__init__(parent, text=title, padding=4)
        self.arr = None
        self._tk = None
        self.title_text = title
        self.cv = tk.Canvas(self, width=PANEL_W, height=PANEL_H,
                            bg="#2b2b2b", highlightthickness=0)
        self.cv.pack()
        self.cv.bind("<Double-Button-1>", lambda e: self.zoom())
        self.cap = tk.Label(self, text="", width=1, height=3, anchor="nw",
                            justify="left", wraplength=PANEL_W)
        self.cap.pack(fill="x")
        row = ttk.Frame(self)
        row.pack(fill="x")
        ttk.Label(row, text="двойной клик - во весь размер").pack(side="left")
        ttk.Button(row, text="Сохранить…", command=self.save).pack(side="right")

    def show(self, arr, caption=""):
        self.arr = arr
        img = Image.fromarray(arr)
        w, h = img.size
        s = min(PANEL_W / w, PANEL_H / h)
        if s != 1:
            img = img.resize((max(1, int(w * s)), max(1, int(h * s))),
                             Image.LANCZOS if s < 1 else Image.NEAREST)
        self._tk = ImageTk.PhotoImage(img)
        self.cv.delete("all")
        self.cv.create_image(PANEL_W // 2, PANEL_H // 2, image=self._tk)
        self.cap.config(text=caption)

    def zoom(self):
        if self.arr is None:
            return
        top = tk.Toplevel(self)
        top.title(self.title_text + " (100%)")
        img = ImageTk.PhotoImage(Image.fromarray(self.arr))
        w, h = img.width(), img.height()
        cv = tk.Canvas(top, width=min(w, 1100), height=min(h, 700),
                       scrollregion=(0, 0, w, h))
        hs = ttk.Scrollbar(top, orient="horizontal", command=cv.xview)
        vs = ttk.Scrollbar(top, orient="vertical", command=cv.yview)
        cv.configure(xscrollcommand=hs.set, yscrollcommand=vs.set)
        hs.pack(side="bottom", fill="x")
        vs.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)
        cv.create_image(0, 0, anchor="nw", image=img)
        cv.image = img

    def save(self):
        if self.arr is None:
            return
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            filetypes=[("PNG", "*.png")])
        if path:
            Image.fromarray(self.arr).save(path)

# приложение
class App:
    def __init__(self, root):
        self.root = root
        root.title("ЛР2 (вариант 13): локальная пороговая обработка, повышение резкости и алгоритм сжатия")
        root.geometry("1100x760")
        self.rgb = self.gray = self.gt = self.ref = None
        self.after_id = None
        self.blob = None
        

        self._build_toolbar()
        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._build_threshold_tab()
        self._build_sharpen_tab()
        self._build_compress_tab()
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self.refresh())
        self._fill_list()


# интерфейс
    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=6)
        bar.pack(fill="x")
        ttk.Label(bar, text="Тестовое изображение:").pack(side="left")
        self.combo = ttk.Combobox(bar, state="readonly", width=32)
        self.combo.pack(side="left", padx=6)
        self.combo.bind("<<ComboboxSelected>>", self.on_pick)
        ttk.Button(bar, text="Открыть файл…", command=self.open_file).pack(side="left")
        self.info = ttk.Label(bar, text="")
        self.info.pack(side="left", padx=12)

    def _slider(self, parent, text, col, lo, hi, init, step):
        ttk.Label(parent, text=text).grid(row=0, column=col, sticky="w", padx=6)
        var = tk.DoubleVar(value=init)
        tk.Scale(parent, from_=lo, to=hi, resolution=step, orient="horizontal",
                 length=170, variable=var,
                 command=lambda _v: self.schedule()).grid(row=1, column=col, padx=6)
        return var

    def _build_threshold_tab(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text="Локальная пороговая обработка")
        tab = sf.inner
        ctrl = ttk.LabelFrame(tab, text="Параметры", padding=4)
        ctrl.pack(fill="x", padx=4, pady=4)
        self.v_w = self._slider(ctrl, "Окно w (нечётное)", 0, 3, 151, 25, 2)
        self.v_nk = self._slider(ctrl, "Niblack: k", 1, -1.0, 1.0, -0.2, 0.05)
        self.v_sk = self._slider(ctrl, "Sauvola: k", 2, 0.0, 1.0, 0.3, 0.05)
        self.v_sr = self._slider(ctrl, "Sauvola: R", 3, 16, 255, 128, 1)
        grid = ttk.Frame(tab)
        grid.pack()
        self.t_orig = ImagePanel(grid, "Исходное (градации серого)")
        self.t_nib = ImagePanel(grid, "Niblack (локальный)")
        self.t_sau = ImagePanel(grid, "Sauvola (локальный)")
        self.t_otsu = ImagePanel(grid, "Оцу (глобальный, для сравнения)")
        for i, p in enumerate((self.t_orig, self.t_nib, self.t_sau, self.t_otsu)):
            p.grid(row=i // 2, column=i % 2, padx=4, pady=2)

    def _build_sharpen_tab(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text="Повышение резкости (ВЧ-фильтры)")
        tab = sf.inner
        ctrl = ttk.LabelFrame(tab, text="Параметры", padding=4)
        ctrl.pack(fill="x", padx=4, pady=4)
        ttk.Label(ctrl, text="Ядро лапласиана").grid(row=0, column=0, sticky="w", padx=6)
        self.lap_cb = ttk.Combobox(ctrl, state="readonly", width=22,
                                   values=["4-связное (0,1,0 / 1,-4,1)",
                                           "8-связное (1,1,1 / 1,-8,1)"])
        self.lap_cb.current(0)
        self.lap_cb.grid(row=1, column=0, padx=6)
        self.lap_cb.bind("<<ComboboxSelected>>", lambda e: self.schedule())
        self.v_la = self._slider(ctrl, "Лапласиан: сила c", 1, 0.0, 3.0, 0.5, 0.1)
        self.v_us = self._slider(ctrl, "Нерезкая маска: σ", 2, 0.5, 10.0, 1.5, 0.1)
        self.v_ua = self._slider(ctrl, "Нерезкая маска: A", 3, 0.0, 5.0, 1.5, 0.1)
        grid = ttk.Frame(tab)
        grid.pack()
        self.s_orig = ImagePanel(grid, "Исходное")
        self.s_lap = ImagePanel(grid, "Лапласиан: g = f - c·∇²f")
        self.s_usm = ImagePanel(grid, "Нерезкая маска: g = f + A·(f - Gauss(f))")
        self.s_hf = ImagePanel(grid, "ВЧ-компонента (отклик лапласиана)")
        for i, p in enumerate((self.s_orig, self.s_lap, self.s_usm, self.s_hf)):
            p.grid(row=i // 2, column=i % 2, padx=4, pady=2)


# загрузка
    def _fill_list(self):
        ensure_test_images()
        files = sorted(f for f in os.listdir(TEST_DIR)
               if f.lower().endswith(EXT) and not is_aux(f))
        self.combo["values"] = files
        if files:
            self.combo.current(0)
            self.load(os.path.join(TEST_DIR, files[0]))
        else:
            self.info.config(text="Папка test_images пуста: положите туда изображения "
                                  "или нажмите «Открыть файл…»")

    def on_pick(self, _e=None):
        self.load(os.path.join(TEST_DIR, self.combo.get()))

    def open_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff")])
        if path:
            self.load(path)

    def _aux(self, path, mode, size):
        if not os.path.exists(path):
            return None
        try:
            im = Image.open(path).convert(mode)
            if im.size != size:
                im = im.resize(size, Image.NEAREST)
            return np.array(im)
        except Exception:
            return None

    def load(self, path):
        try:
            img, note = load_rgb(path)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{e}")
            return
        self.rgb = np.array(img)
        self.gray = ip.to_gray(self.rgb)

        base = os.path.splitext(path)[0]
        p_gt, p_ref = find_aux(base, "gt"), find_aux(base, "ref")
        self.gt = self._aux(p_gt, "L", img.size) if p_gt else None
        self.ref = self._aux(p_ref, "RGB", img.size) if p_ref else None

        extra = ""
        if self.gt is not None:
            extra += "; есть эталон бинаризации"
        if self.ref is not None:
            extra += "; есть резкий оригинал"
        self.info.config(text=f"{os.path.basename(path)} - {img.width}×{img.height}{note}{extra}")
        self.refresh()

# сжатие (RLE)
    def _build_compress_tab(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text="Сжатие (RLE)")
        tab = sf.inner
        ctrl = ttk.LabelFrame(tab, text="Параметры", padding=4)
        ctrl.pack(fill="x", padx=4, pady=4)
        ttk.Label(ctrl, text="Представление данных:").pack(side="left", padx=6)
        self.cmp_cb = ttk.Combobox(ctrl, state="readonly", width=42,
                                   values=[t for _k, t in rle.MODES])
        self.cmp_cb.current(0)
        self.cmp_cb.pack(side="left")
        self.cmp_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Button(ctrl, text="Сохранить .rle…", command=self.save_rle).pack(side="left", padx=8)
        ttk.Button(ctrl, text="Открыть .rle…", command=self.open_rle).pack(side="left")
        ttk.Button(ctrl, text="Таблица по всей папке", command=self.batch).pack(side="left", padx=8)

        row = ttk.Frame(tab)
        row.pack()
        self.c_orig = ImagePanel(row, "Исходные данные (после подготовки)")
        self.c_dec = ImagePanel(row, "После распаковки")
        self.c_orig.grid(row=0, column=0, padx=4)
        self.c_dec.grid(row=0, column=1, padx=4)

        self.c_info = tk.Label(tab, text="", justify="left", anchor="w", font=("Consolas", 10))
        self.c_info.pack(fill="x", padx=8)

        cols = ("name", "raw", "rle", "ratio", "png")
        heads = ("Файл", "Исходно, Б", "RLE, Б", "K (RLE)", "K (PNG, справка)")
        self.tree = ttk.Treeview(tab, columns=cols, show="headings", height=6)
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h, command=lambda c=c: self._sort_tree(c))
            self.tree.column(c, width=200 if c == "name" else 120, anchor="w" if c == "name" else "e")
        self.tree.tag_configure("best", background="#d4f4d4")
        self.tree.tag_configure("worst", background="#f8d4d4")
        self.tree.pack(fill="x", padx=8, pady=4)
        self.c_sum = ttk.Label(tab, text="Нажмите «Таблица по всей папке», чтобы найти "
                                         "лучшее и худшее изображение.")
        self.c_sum.pack(anchor="w", padx=8)
        self._sort_rev = {}

    def _cmp_mode(self):
        return rle.MODES[self.cmp_cb.current()][0]

    @staticmethod
    def _png_size(arr):
        buf = io.BytesIO()
        Image.fromarray(arr).save(buf, "PNG")
        return len(buf.getvalue())

    def update_cmp(self):
        arr, planar = rle.prepare(self.rgb, self._cmp_mode())
        t0 = time.perf_counter()
        blob = rle.compress(arr, planar)
        t_enc = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        dec = rle.decompress(blob)
        t_dec = (time.perf_counter() - t0) * 1000
        same = np.array_equal(dec, arr)

        self.blob = blob
        raw = arr.size
        k = raw / len(blob)
        runs = rle.count_runs(arr.transpose(2, 0, 1) if (arr.ndim == 3 and planar) else arr)
        png = self._png_size(arr)
        self.c_orig.show(arr, f"{raw} байт данных, серий: {runs}")
        self.c_dec.show(dec, "Совпадает с оригиналом" if same else "ОШИБКА: не совпадает!")
        self.c_info.config(text=(
            f"Исходный размер: {raw:>10} Б\n"
            f"RLE-файл:        {len(blob):>10} Б (заголовок {rle.HEADER.size} Б)\n"
            f"Коэффициент K = исходный / сжатый = {k:.3f} "
            f"({'экономия' if k >= 1 else 'ПРИРОСТ'} {abs(1 - 1 / k) * 100:.1f} %)\n"
            f"Средняя длина серии: {raw / runs:.2f} байт\n"
            f"Сжатие {t_enc:.0f} мс, распаковка {t_dec:.0f} мс, "
            f"распаковка == оригинал: {'ДА' if same else 'НЕТ'}\n"
            f"Для справки PNG (LZ77 + Хаффман): {png} Б, K = {raw / png:.3f}\n"
            f"Теоретические границы схемы: лучший K = 32, худший K = 0.5"))

    def save_rle(self):
        if self.blob is None:
            return
        path = filedialog.asksaveasfilename(defaultextension=".rle",
                                            filetypes=[("RLE", "*.rle")])
        if path:
            with open(path, "wb") as f:
                f.write(self.blob)

    def open_rle(self):
        path = filedialog.askopenfilename(filetypes=[("RLE", "*.rle")])
        if not path:
            return
        try:
            with open(path, "rb") as f:
                blob = f.read()
            dec = rle.decompress(blob)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось распаковать:\n{e}")
            return
        self.blob = blob
        self.c_dec.show(dec, f"Из файла {os.path.basename(path)}: "
                             f"{dec.shape[1]}×{dec.shape[0]}, {len(blob)} Б")

    def batch(self):
        mode = self._cmp_mode()
        files = sorted(f for f in os.listdir(TEST_DIR) if f.lower().endswith(EXT))
        if not files:
            messagebox.showinfo("Нет файлов", "Папка test_images пуста")
            return
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        rows = []
        for f in files:
            try:
                img, _ = load_rgb(os.path.join(TEST_DIR, f))
                arr, planar = rle.prepare(np.array(img), mode)
                size = len(rle.compress(arr, planar))
                rows.append((f, arr.size, size, arr.size / size,
                             arr.size / self._png_size(arr)))
            except Exception:
                continue
        self.root.config(cursor="")
        if not rows:
            return
        rows.sort(key=lambda r: -r[3])
        self.tree.delete(*self.tree.get_children())
        for i, (name, raw, size, k, kp) in enumerate(rows):
            tag = "best" if i == 0 else "worst" if i == len(rows) - 1 else ""
            self.tree.insert("", "end", values=(name, raw, size, f"{k:.3f}", f"{kp:.3f}"),
                             tags=(tag,))
        self.c_sum.config(text=f"Лучший: {rows[0][0]} (K = {rows[0][3]:.2f}),  "
                               f"худший: {rows[-1][0]} (K = {rows[-1][3]:.2f}),  "
                               f"режим: {rle.MODES[self.cmp_cb.current()][1]}")

    def _sort_tree(self, col):
        rev = not self._sort_rev.get(col, True)
        self._sort_rev[col] = rev

        def key(item):
            try:
                return float(item[0])
            except ValueError:
                return item[0].lower()
        items = sorted(((self.tree.set(k, col), k) for k in self.tree.get_children("")),
                       key=key, reverse=rev)
        for i, (_v, k) in enumerate(items):
            self.tree.move(k, "", i)


# обновление
    def schedule(self):
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.after_id = self.root.after(120, self.refresh)

    def refresh(self):
        self.after_id = None
        if self.gray is None:
            return
        tab = self.nb.index(self.nb.select())
        if tab == 0:
            self.update_thr()
        elif tab == 1:
            self.update_shp()
        else:
            self.update_cmp()

    def _seg_text(self, res, dt):
        txt = f"время: {dt:.0f} мс"
        if self.gt is not None:
            p, r, f1, acc = ip.seg_metrics(res, self.gt)
            txt += (f"\nF1 = {f1:.3f}  точность = {p:.3f}  "
                    f"полнота = {r:.3f}  accuracy = {acc:.3f}")
        return txt

    def update_thr(self):
        g = self.gray
        w = int(self.v_w.get())
        if w % 2 == 0:
            w += 1
        self.t_orig.show(ip.to_uint8(g), "Яркость = 0.299R + 0.587G + 0.114B")

        k = self.v_nk.get()
        t0 = time.perf_counter()
        res = ip.binarize(g, ip.niblack_threshold(g, w, k))
        dt = (time.perf_counter() - t0) * 1000
        self.t_nib.show(res, f"T = m + k·s;  окно {w}×{w}, k = {k:.2f}\n" + self._seg_text(res, dt))

        k, R = self.v_sk.get(), self.v_sr.get()
        t0 = time.perf_counter()
        res = ip.binarize(g, ip.sauvola_threshold(g, w, k, R))
        dt = (time.perf_counter() - t0) * 1000
        self.t_sau.show(res, f"T = m·(1 + k·(s/R - 1));  окно {w}×{w}, k = {k:.2f}, R = {R:.0f}\n"
                        + self._seg_text(res, dt))

        t0 = time.perf_counter()
        T = ip.otsu_threshold(ip.to_uint8(g))
        res = ip.binarize(g, T)
        dt = (time.perf_counter() - t0) * 1000
        self.t_otsu.show(res, f"единый порог T = {T:.0f}\n" + self._seg_text(res, dt))

    def _sharp_text(self, arr):
        txt = f"резкость (дисперсия ∇²): {ip.sharpness(ip.to_gray(arr)):.0f}"
        if self.ref is not None:
            p = ip.psnr(arr, self.ref)
            txt += "\nPSNR к резкому оригиналу: " + ("∞" if p == float("inf") else f"{p:.2f} дБ")
        return txt

    def update_shp(self):
        f = self.rgb.astype(np.float64)
        K = ip.LAPLACE_8 if self.lap_cb.current() == 1 else ip.LAPLACE_4
        self.s_orig.show(self.rgb, self._sharp_text(self.rgb))

        c = self.v_la.get()
        t0 = time.perf_counter()
        r1 = ip.to_uint8(ip.laplacian_sharpen(f, K, c))
        dt = (time.perf_counter() - t0) * 1000
        self.s_lap.show(r1, f"c = {c:.1f}, {dt:.0f} мс\n" + self._sharp_text(r1))

        sigma, A = self.v_us.get(), self.v_ua.get()
        t0 = time.perf_counter()
        r2 = ip.to_uint8(ip.unsharp_mask(f, sigma, A))
        dt = (time.perf_counter() - t0) * 1000
        self.s_usm.show(r2, f"σ = {sigma:.1f}, A = {A:.1f}, {dt:.0f} мс\n" + self._sharp_text(r2))

        self.s_hf.show(ip.laplacian_view(self.gray, K),
                       "серый = нет перепадов, светлее/темнее = границы")

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop() 