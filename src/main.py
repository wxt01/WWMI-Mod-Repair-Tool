# -*- coding: utf-8 -*-
"""WWMI MOD 修复助手 - 图形界面入口（中英双语）
用法：python main.py  （或运行打包后的 exe）
"""
import os
import sys
import json
import threading
import ctypes
import tkinter as tk
from tkinter import ttk, filedialog

# Windows 高 DPI 感知：避免窗口被系统放大导致内容溢出屏幕（按钮看不见）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
import history
import prompt as prompt_mod
import i18n as i18n_mod

BG = "#f5f6f8"
CARD = "#ffffff"
ACCENT = "#3b82f6"
ACCENT_DK = "#2563eb"
TEXT = "#1f2937"
MUTED = "#6b7280"
BORDER = "#e5e7eb"
DANGER = "#b91c1c"

SETTINGS_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                            "WWMI_MOD修复助手")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")


def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8-sig") as _f:
            return json.load(_f)
    except Exception:
        return {}


def save_settings(d):
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as _f:
            json.dump(d, _f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self._screen_h = self.winfo_screenheight()
        self._screen_w = self.winfo_screenwidth()
        self.settings = load_settings()
        # 语言：设置里有就用；没有则先弹语言选择（首启）
        self.tr = i18n_mod.I18N(self.settings.get("lang") or "zh")
        if self.settings.get("lang") not in ("zh", "en"):
            self._choose_lang_first()

        self.title(self.tr.t("app_name"))
        self.geometry("1080x760")
        self.minsize(860, 560)
        self.configure(bg=BG)
        self.current_folder = None
        self.analysis = None
        self.wuwa_var = tk.StringVar()
        if self.settings.get("wuwa_config"):
            self.wuwa_var.set(self.settings["wuwa_config"])
        self._build_style()
        self._build_ui()
        self._refresh_history()
        # 按内容高度自适应：确保底部按钮（回滚/清除）默认就可见，不依赖全屏
        self.update_idletasks()
        req_h = self.winfo_reqheight()
        self.geometry("1080x%d" % min(req_h + 4, max(600, self._screen_h - 20)))
    # ---------- 首启语言选择 ----------
    def _choose_lang_first(self):
        win = tk.Toplevel(self)
        win.title(i18n_mod.STR["lang_choose_title"]["zh"])
        win.configure(bg=CARD)
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        body = tk.Frame(win, bg=CARD)
        body.pack(fill="both", expand=True, padx=28, pady=(24, 8))
        tk.Label(body, text=i18n_mod.STR["lang_choose_hint"]["zh"],
                 font=("Microsoft YaHei UI", 11), bg=CARD, fg=TEXT).pack()
        btns = tk.Frame(body, bg=CARD)
        btns.pack(pady=(18, 4))

        def _pick(lang):
            self.tr.set(lang)
            self.settings["lang"] = lang
            save_settings(self.settings)
            win.destroy()

        ttk.Button(btns, text=i18n_mod.STR["lang_zh"]["zh"], style="Accent.TButton",
                   width=18, command=lambda: _pick("zh")).pack(side="left", padx=(0, 12))
        ttk.Button(btns, text=i18n_mod.STR["lang_en"]["zh"], style="Accent.TButton",
                   width=18, command=lambda: _pick("en")).pack(side="left")
        # 居中
        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry("+%d+%d" % (max(0, (self._screen_w - w) // 2),
                                 max(0, (self._screen_h - h) // 2)))
        win.wait_window()

    # ---------- 样式 ----------
    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Card.TLabelframe", background=CARD, bordercolor=BORDER,
                        borderwidth=1, relief="solid", padding=8)
        style.configure("Card.TLabelframe.Label", background=CARD, foreground=TEXT,
                        font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("TButton", font=("Microsoft YaHei UI", 9), padding=(10, 4))
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 9, "bold"),
                        padding=(12, 6), foreground="#ffffff", background=ACCENT)
        style.map("Accent.TButton",
                  background=[("active", ACCENT_DK), ("pressed", "#1d4ed8")],
                  foreground=[("active", "#ffffff")])
        style.configure("Danger.TButton", font=("Microsoft YaHei UI", 9),
                        padding=(10, 4), foreground=DANGER)
        style.configure("Treeview", font=("Microsoft YaHei UI", 9), rowheight=24,
                        background=CARD, fieldbackground=CARD, bordercolor=BORDER)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"),
                        background="#eef1f5", foreground=TEXT)
        style.map("Treeview", background=[("selected", "#dbeafe")],
                  foreground=[("selected", TEXT)])
        style.configure("Status.TLabel", background=BG, foreground=MUTED,
                        font=("Microsoft YaHei UI", 9))
        style.configure("Hint.TLabel", background=BG, foreground=MUTED,
                        font=("Microsoft YaHei UI", 9))
        style.configure("Learn.TButton", font=("Microsoft YaHei UI", 9),
                        padding=(10, 4), foreground=ACCENT)

    # ---------- 界面 ----------
    def _build_ui(self):
        pad = dict(padx=14, pady=6)
        T = self.tr.t

        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", **pad)
        tk.Label(header, text=T("app_name"), font=("Microsoft YaHei UI", 13, "bold"),
                 bg=BG, fg=TEXT).pack(side="left")
        tk.Label(header, text=T("app_subtitle"),
                 font=("Microsoft YaHei UI", 9), bg=BG, fg=MUTED).pack(side="left", padx=12)
        ttk.Button(header, text=T("btn_settings"), style="Accent.TButton",
                   command=self._show_settings).pack(side="right", padx=(0, 8))
        ttk.Button(header, text=T("btn_prompt"), style="Accent.TButton",
                   command=self._show_prompt).pack(side="right")

        # --- 第一步：选择 mod 文件夹 ---
        card1 = ttk.LabelFrame(self, text=T("card_mod"), style="Card.TLabelframe")
        card1.pack(fill="x", **pad)
        row = tk.Frame(card1, bg=CARD)
        row.pack(fill="x")
        self.folder_var = tk.StringVar()
        tk.Entry(row, textvariable=self.folder_var, font=("Microsoft YaHei UI", 9),
                 bg="#fafafa", relief="solid", bd=1).pack(side="left", fill="x",
                                                          expand=True, ipady=4)
        ttk.Button(row, text=T("browse"), command=self._pick_folder).pack(side="left", padx=(8, 0))

        wrow = tk.Frame(card1, bg=CARD)
        wrow.pack(fill="x", pady=(8, 0))
        tk.Label(wrow, text=T("community_config"), font=("Microsoft YaHei UI", 9),
                 bg=CARD, fg=TEXT).pack(side="left")
        tk.Entry(wrow, textvariable=self.wuwa_var, font=("Microsoft YaHei UI", 9),
                 bg="#fafafa", relief="solid", bd=1).pack(side="left", fill="x",
                                                          expand=True, ipady=4, padx=(8, 0))
        ttk.Button(wrow, text=T("browse"), command=self._pick_wuwa).pack(side="left", padx=(8, 0))
        ttk.Button(wrow, text=T("clear"), command=lambda: self.wuwa_var.set("")).pack(side="left", padx=(6, 0))
        tk.Label(wrow, text=T("community_hint"), bg=CARD, fg=MUTED,
                 font=("Microsoft YaHei UI", 8)).pack(side="left", padx=(10, 0))

        self.tree = ttk.Treeview(card1, columns=("file", "state", "diffuse"),
                                 show="headings", height=2)
        self.tree.heading("file", text=T("col_ini"))
        self.tree.heading("state", text=T("col_state"))
        self.tree.heading("diffuse", text=T("col_diffuse"))
        self.tree.column("file", width=300)
        self.tree.column("state", width=90, anchor="center")
        self.tree.column("diffuse", width=330)
        self.tree.pack(fill="x", pady=(10, 0))
        btnrow = tk.Frame(card1, bg=CARD)
        btnrow.pack(anchor="e", pady=(10, 0))
        ttk.Button(btnrow, text=T("btn_preset"),
                   command=self._preset_repair).pack(side="left", padx=(0, 8))
        ttk.Button(btnrow, text=T("btn_repair"), style="Accent.TButton",
                   command=self._repair).pack(side="left")

        # --- 第二步：备份记录 ---
        card2 = ttk.LabelFrame(self, text=T("card_history"), style="Card.TLabelframe")
        card2.pack(fill="both", expand=True, **pad)
        self.hist_tree = ttk.Treeview(card2, columns=("time", "folder", "inis", "state"),
                                      show="headings", height=2)
        self.hist_tree.heading("time", text=T("col_time"))
        self.hist_tree.heading("folder", text=T("col_folder"))
        self.hist_tree.heading("inis", text=T("col_count"))
        self.hist_tree.heading("state", text=T("col_rec_state"))
        self.hist_tree.column("time", width=150)
        self.hist_tree.column("folder", width=420)
        self.hist_tree.column("inis", width=70, anchor="center")
        self.hist_tree.column("state", width=80, anchor="center")
        self.hist_tree.bind("<Double-1>", lambda e: self._rollback_selected())
        btns = tk.Frame(card2, bg=CARD)
        # 按钮行固定贴 card2 底部（树自适应压缩在上方），任何窗口高度都可见
        btns.pack(fill="x", side="bottom", pady=(8, 0))
        ttk.Button(btns, text=T("btn_rollback"),
                   command=self._rollback_selected).pack(side="left")
        ttk.Button(btns, text=T("btn_rollback_all"), style="Danger.TButton",
                   command=self._rollback_all).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text=T("btn_clear_rec"), style="Danger.TButton",
                   command=self._clear_history).pack(side="left", padx=(8, 0))
        tk.Label(btns, text=T("rollback_hint"), bg=CARD, fg=MUTED,
                 font=("Microsoft YaHei UI", 8)).pack(side="right")
        self.hist_tree.pack(fill="both", expand=True, pady=(10, 0))

        # --- 底部：状态栏 ---
        self.status_var = tk.StringVar(value=T("status_ready"))
        ttk.Label(self, textvariable=self.status_var, style="Status.TLabel").pack(
            side="bottom", anchor="w", padx=14, pady=6)

    # ---------- 自定义对话框（关闭 / 了解更多） ----------
    def _dialog(self, kind, msg, title_key=None, detail=None):
        """kind: info/warning/error；detail 提供时显示「了解更多」按钮。"""
        title = self.tr.t(title_key or {
            "info": "dlg_info_title", "warning": "dlg_warn_title", "error": "dlg_error_title"
        }.get(kind, "dlg_info_title"))
        win = tk.Toplevel(self)
        win.title(title)
        win.configure(bg=CARD)
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        body = tk.Frame(win, bg=CARD)
        body.pack(fill="both", expand=True, padx=18, pady=(16, 4))
        icon = "ℹ️" if kind == "info" else ("⚠️" if kind == "warning" else "❌")
        head = tk.Frame(body, bg=CARD)
        head.pack(fill="x")
        tk.Label(head, text=icon, font=("Segoe UI Emoji", 14), bg=CARD).pack(side="left", padx=(0, 8))
        long = len(msg) > 180
        tk.Label(body, text=msg, font=("Microsoft YaHei UI", 10), bg=CARD, fg=TEXT,
                 justify="left", wraplength=640, anchor="w").pack(fill="x", pady=(4, 2))
        btns = tk.Frame(win, bg=CARD)
        btns.pack(fill="x", padx=18, pady=(6, 14))
        if detail:
            ttk.Button(btns, text=self.tr.t("dlg_learn_more"), style="Learn.TButton",
                       command=lambda: self._show_detail(win, detail)).pack(side="left")
        ttk.Button(btns, text=self.tr.t("dlg_close"), style="Accent.TButton",
                   command=win.destroy).pack(side="right")
        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry("+%d+%d" % (max(0, (self._screen_w - w) // 2),
                                 max(0, (self._screen_h - h) // 2)))

    def _show_detail(self, parent, detail):
        win = tk.Toplevel(self)
        win.title(self.tr.t("learn_dump_title"))
        win.geometry("640x520")
        win.configure(bg=BG)
        win.transient(parent)
        win.grab_set()
        txt = tk.Text(win, font=("Microsoft YaHei UI", 10), wrap="word",
                      bg="#ffffff", fg=TEXT, relief="solid", bd=1,
                      padx=12, pady=10)
        txt.insert("1.0", detail)
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True, padx=12, pady=(12, 8))
        ttk.Button(win, text=self.tr.t("dlg_close"), style="Accent.TButton",
                   command=win.destroy).pack(pady=(0, 12))

    def _ask_yesno(self, msg):
        win = tk.Toplevel(self)
        win.title(self.tr.t("dlg_confirm"))
        win.configure(bg=CARD)
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        result = {"v": False}
        tk.Label(win, text="❓", font=("Segoe UI Emoji", 14), bg=CARD).pack(pady=(16, 0))
        tk.Label(win, text=msg, font=("Microsoft YaHei UI", 10), bg=CARD, fg=TEXT,
                 wraplength=520, justify="left").pack(padx=20, pady=(6, 8))
        btns = tk.Frame(win, bg=CARD)
        btns.pack(pady=(4, 14))
        ttk.Button(btns, text=self.tr.t("dlg_yes"), style="Accent.TButton",
                   command=lambda: (result.update(v=True), win.destroy())).pack(side="left", padx=(0, 10))
        ttk.Button(btns, text=self.tr.t("dlg_no"),
                   command=win.destroy).pack(side="left")
        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry("+%d+%d" % (max(0, (self._screen_w - w) // 2),
                                 max(0, (self._screen_h - h) // 2)))
        win.wait_window()
        return result["v"]

    # ---------- 行为 ----------
    def _pick_folder(self):
        start = self.settings.get("mod_start_dir") or None
        folder = filedialog.askdirectory(title=self.tr.t("card_mod"), initialdir=start)
        if folder:
            self.folder_var.set(folder)
            self._analyze()

    def _pick_wuwa(self):
        start = None
        if self.settings.get("wuwa_config"):
            start = os.path.dirname(self.settings["wuwa_config"])
        elif self.settings.get("mod_start_dir"):
            start = self.settings["mod_start_dir"]
        path = filedialog.askopenfilename(
            title=self.tr.t("community_config"),
            initialdir=start,
            filetypes=[("JSON", "*.json"), ("*", "*.*")])
        if path:
            self.wuwa_var.set(path)
            self.status_var.set(self.tr.t("status_pick_wuwa"))

    def _show_settings(self):
        T = self.tr.t
        win = tk.Toplevel(self)
        win.title(T("settings_title"))
        win.configure(bg=CARD)
        win.geometry("680x360")
        win.transient(self)
        win.grab_set()

        body = tk.Frame(win, bg=CARD)
        body.pack(fill="both", expand=True, padx=16, pady=(16, 8))

        tk.Label(body, text=T("settings_mod_dir"), font=("Microsoft YaHei UI", 10, "bold"),
                 bg=CARD, fg=TEXT).pack(anchor="w")
        r1 = tk.Frame(body, bg=CARD)
        r1.pack(fill="x", pady=(4, 10))
        mod_var = tk.StringVar(value=self.settings.get("mod_start_dir", ""))
        tk.Entry(r1, textvariable=mod_var, font=("Microsoft YaHei UI", 9),
                 bg="#fafafa", relief="solid", bd=1).pack(side="left", fill="x",
                                                          expand=True, ipady=4)
        ttk.Button(r1, text=T("browse"),
                   command=lambda: mod_var.set(filedialog.askdirectory(
                       title=T("settings_mod_dir"),
                       initialdir=mod_var.get().strip().strip('"') or None) or mod_var.get())
                   ).pack(side="left", padx=(8, 0))
        ttk.Button(r1, text=T("clear"), command=lambda: mod_var.set("")).pack(side="left", padx=(6, 0))

        tk.Label(body, text=T("settings_wuwa"), font=("Microsoft YaHei UI", 10, "bold"),
                 bg=CARD, fg=TEXT).pack(anchor="w")
        r2 = tk.Frame(body, bg=CARD)
        r2.pack(fill="x", pady=(4, 10))
        wuwa_var = tk.StringVar(value=self.settings.get("wuwa_config", ""))
        tk.Entry(r2, textvariable=wuwa_var, font=("Microsoft YaHei UI", 9),
                 bg="#fafafa", relief="solid", bd=1).pack(side="left", fill="x",
                                                          expand=True, ipady=4)

        def _browse_wuwa():
            d0 = os.path.dirname(wuwa_var.get().strip().strip('"')) \
                or self.settings.get("mod_start_dir") or None
            p = filedialog.askopenfilename(title=T("settings_wuwa"), initialdir=d0,
                                           filetypes=[("JSON", "*.json"), ("*", "*.*")])
            if p:
                wuwa_var.set(p)
        ttk.Button(r2, text=T("browse"), command=_browse_wuwa).pack(side="left", padx=(8, 0))
        ttk.Button(r2, text=T("clear"), command=lambda: wuwa_var.set("")).pack(side="left", padx=(6, 0))

        # 语言切换
        tk.Label(body, text=T("settings_lang"), font=("Microsoft YaHei UI", 10, "bold"),
                 bg=CARD, fg=TEXT).pack(anchor="w")
        r3 = tk.Frame(body, bg=CARD)
        r3.pack(fill="x", pady=(4, 10))
        lang_var = tk.StringVar(value=self.tr.lang)
        cb = ttk.Combobox(r3, textvariable=lang_var, state="readonly",
                          values=["zh", "en"], font=("Microsoft YaHei UI", 9), width=10)
        cb.pack(side="left")

        def _save():
            self.settings["mod_start_dir"] = mod_var.get().strip().strip('"')
            self.settings["wuwa_config"] = wuwa_var.get().strip().strip('"')
            self.settings["lang"] = lang_var.get()
            save_settings(self.settings)
            self.tr.set(lang_var.get())
            self.wuwa_var.set(self.settings["wuwa_config"])
            self.status_var.set(T("status_saved"))
            win.destroy()
            self._rebuild_ui_lang()

        btns = tk.Frame(win, bg=CARD)
        btns.pack(fill="x", padx=16, pady=(0, 14))
        ttk.Button(btns, text=T("dlg_save"), style="Accent.TButton", command=_save).pack(side="right")
        ttk.Button(btns, text=T("dlg_cancel"), command=win.destroy).pack(side="right", padx=(0, 8))
        tk.Label(btns, text=T("settings_fullscreen_hint"), bg=CARD, fg=MUTED,
                 font=("Microsoft YaHei UI", 8)).pack(side="left")

    def _rebuild_ui_lang(self):
        """语言切换后重建界面文本。"""
        self.title(self.tr.t("app_name"))
        # 简单可靠：重建全部 UI
        for child in self.winfo_children():
            child.destroy()
        self._build_ui()
        self._refresh_history()
        # 保留已分析结果
        if self.analysis:
            self._render_analysis()
        self.update_idletasks()
        req_h = self.winfo_reqheight()
        self.geometry("1080x%d" % min(req_h + 4, max(600, self._screen_h - 20)))
    def _render_analysis(self):
        self.tree.delete(*self.tree.get_children())
        for it in self.analysis["inis"]:
            self.tree.insert("", "end", values=(
                it["file"], self.tr.map_state(it["state"]),
                it.get("diffuse", "") or "—"))

    def _analyze(self):
        folder = self.folder_var.get().strip().strip('"')
        if not folder:
            self._dialog("warning", self.tr.t("warn_pick_folder"))
            return
        self.current_folder = folder
        r = engine.analyze_folder(folder, wuwa_path=self.wuwa_var.get().strip().strip('"') or None)
        if "error" in r:
            self._dialog("error", r["error"],
                         detail=self.tr.t("learn_dump_body"))
            return
        self.analysis = r
        self._render_analysis()
        n_ok = sum(1 for it in r["inis"] if it["state"].startswith("可修复"))
        self.status_var.set(self.tr.t("status_analyzed", len(r["inis"]), n_ok))

    def _preset_repair(self):
        T = self.tr.t
        presets = []
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(base, "presets.json"), "r", encoding="utf-8") as _f:
                presets = json.load(_f).get("presets", [])
        except Exception:
            presets = []
        if not presets:
            self._dialog("warning", T("warn_preset_empty"))
            return

        win = tk.Toplevel(self)
        win.title(T("preset_title"))
        win.configure(bg=CARD)
        win.geometry("860x540")
        win.transient(self)
        win.grab_set()
        tk.Label(win, text=T("preset_hint"), font=("Microsoft YaHei UI", 10, "bold"),
                 bg=CARD, fg=TEXT).pack(anchor="w", padx=14, pady=(12, 6))
        cols = ("name", "author", "source", "method", "desc")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=6)
        tree.heading("name", text=T("preset_col_name")); tree.column("name", width=190)
        tree.heading("author", text=T("preset_col_author")); tree.column("author", width=80)
        tree.heading("source", text=T("preset_col_source")); tree.column("source", width=110)
        tree.heading("method", text=T("preset_col_method")); tree.column("method", width=50, anchor="center")
        tree.heading("desc", text=T("preset_col_desc")); tree.column("desc", width=360)
        for pr in presets:
            tree.insert("", "end", values=(
                pr.get("name", ""), pr.get("author", ""), pr.get("source", ""),
                pr.get("method", ""),
                (pr.get("desc", "") + " ｜ " + self.tr.map_state(pr.get("applicable", "")))
                if self.tr.lang == "zh" else
                (pr.get("desc_en", "") or pr.get("desc", ""))))
        tree.pack(fill="x", padx=14, pady=(0, 8))
        if tree.get_children():
            tree.selection_set(tree.get_children()[0])

        frow = tk.Frame(win, bg=CARD)
        frow.pack(fill="x", padx=14, pady=4)
        tk.Label(frow, text=T("preset_target"), font=("Microsoft YaHei UI", 9),
                 bg=CARD, fg=TEXT).pack(side="left")
        fvar = tk.StringVar()
        tk.Entry(frow, textvariable=fvar, font=("Microsoft YaHei UI", 9),
                 bg="#fafafa", relief="solid", bd=1).pack(side="left", fill="x",
                                                          expand=True, ipady=4, padx=(8, 0))

        def _browse():
            d = filedialog.askdirectory(title=T("preset_target"),
                                        initialdir=self.settings.get("mod_start_dir") or None)
            if d:
                fvar.set(d)
        ttk.Button(frow, text=T("browse"), command=_browse).pack(side="left", padx=(8, 0))

        detail = tk.Label(win, text="", font=("Microsoft YaHei UI", 9),
                          bg=CARD, fg=MUTED, wraplength=820, justify="left")
        detail.pack(fill="x", padx=14, pady=4)

        def _on_sel(_e=None):
            sel = tree.selection()
            if sel:
                vals = tree.item(sel[0], "values")
                if len(vals) >= 5:
                    detail.config(text=T("preset_detail") % vals[4])
        tree.bind("<<TreeviewSelect>>", _on_sel)
        _on_sel()

        def _run():
            folder = fvar.get().strip().strip('"')
            if not folder:
                self._dialog("warning", T("warn_preset_target"))
                return
            sel = tree.selection()
            if not sel:
                self._dialog("warning", T("warn_preset_select"))
                return
            pr = presets[tree.index(sel[0])]
            win.destroy()
            self.folder_var.set(folder)
            self.status_var.set(T("status_preset") % pr.get("name", ""))
            self._repair()

        ttk.Button(win, text=T("preset_start"), style="Accent.TButton",
                   command=_run).pack(pady=(10, 12))

    def _ask_dump_folder(self):
        """一键修复(方法E)前选择转储文件夹：FrameAnalysis-*（F8 生成，含 deduped 子目录）。
        返回路径或 None（跳过=自动查找）。选择会记住到设置。"""
        T = self.tr.t
        win = tk.Toplevel(self)
        win.title(T("dump_title"))
        win.configure(bg=BG)
        win.attributes("-topmost", True)
        # 预填：设置记忆 → 自动找到的最新转储
        pref = (self.settings.get("dump_dir") or "").strip()
        if not pref and self.current_folder:
            try:
                pref = engine._find_dedup_folder(self.current_folder) or ""
            except Exception:
                pref = ""
        if pref:
            pref = pref.replace("\\deduped", "").rstrip("\\/")
        var = tk.StringVar(value=pref)
        result = {}

        frm = tk.Frame(win, bg=BG)
        frm.pack(fill="x", padx=16, pady=(16, 4))
        tk.Label(frm, bg=BG, fg=TEXT, wraplength=560, justify="left",
                 font=("Microsoft YaHei UI", 10), text=T("dump_hint")).pack(fill="x")
        tk.Label(frm, bg=BG, fg=MUTED, wraplength=560, justify="left",
                 font=("Microsoft YaHei UI", 9), text=T("dump_hint2")).pack(fill="x", pady=(6, 0))
        row = tk.Frame(frm, bg=BG)
        row.pack(fill="x", pady=(10, 0))
        ent = ttk.Entry(row, textvariable=var)
        ent.pack(side="left", fill="x", expand=True)

        def _browse():
            d = filedialog.askdirectory(title=T("dump_title"), initialdir=os.path.dirname(pref) if pref else None)
            if d:
                var.set(d)

        ttk.Button(row, text=T("dump_browse"), command=_browse).pack(side="left", padx=(6, 0))

        def _use():
            v = var.get().strip().strip('"')
            if not v:
                self._dialog("warning", T("dump_warn_empty"))
                return
            cand = v.rstrip("\\/")
            dd = cand if os.path.basename(cand) == "deduped" else os.path.join(cand, "deduped")
            if not os.path.isdir(dd):
                self._dialog("warning", T("dump_warn_bad") % os.path.basename(cand))
                return
            result["path"] = cand
            self.settings["dump_dir"] = cand
            save_settings(self.settings)
            win.destroy()

        def _skip():
            result["path"] = None
            win.destroy()

        btns = tk.Frame(win, bg=BG)
        btns.pack(fill="x", padx=16, pady=(12, 16))
        ttk.Button(btns, text=T("dump_use"), style="Accent.TButton", command=_use).pack(side="left")
        ttk.Button(btns, text=T("dump_skip"), command=_skip).pack(side="right")
        win.grab_set()
        win.wait_window()
        return result.get("path")

    def _repair(self):
        if not self.analysis:
            self._dialog("warning", self.tr.t("warn_pick_folder"))
            return
        # 方法 E（贴图挂钩）需要转储数据：一键修复时让用户显式选择 FrameAnalysis 文件夹（保证准确性）
        need_dump = any(it["state"].startswith("可修复(E") for it in self.analysis["inis"])
        dump_folder = None
        if need_dump:
            dump_folder = self._ask_dump_folder()
        self.status_var.set(self.tr.t("status_repairing"))
        self.update_idletasks()
        repaired, skipped = [], []
        for it in self.analysis["inis"]:
            if not it["state"].startswith("可修复"):
                skipped.append(it["file"])
                continue
            try:
                r = engine.repair_ini(it["path"], wuwa_path=self.wuwa_var.get().strip().strip('"') or None,
                                      dedup_folder=dump_folder)
            except Exception as e:
                skipped.append(it["file"] + "（%s）" % e)
                continue
            if r["ok"]:
                repaired.append({"path": it["path"], "backup": r["backup"],
                                 "file": it["file"], "diffuse": r.get("diffuse", "")})
            else:
                skipped.append(it["file"] + "（" + r["reason"] + "）")
        if repaired:
            history.add_record(self.current_folder,
                               [{"path": x["path"], "backup": x["backup"]} for x in repaired],
                               "，".join(x["diffuse"] for x in repaired))
        self._refresh_history()
        if repaired:
            msg = self.tr.t("repair_done", len(repaired))
            kind = "info"
        else:
            msg = self.tr.t("repair_none")
            kind = "warning"
        if skipped:
            msg += "\n" + self.tr.t("repair_skipped") % "；".join(skipped[:6])
            if len(skipped) > 6:
                msg += "\n…（共 %d 项）" % len(skipped)
            if any(("转储" in s or "deduped" in s) for s in skipped):
                msg += "\n" + self.tr.t("repair_skip_note")
        self.status_var.set(msg.split("\n")[0])
        need_dump = any(("转储" in s or "deduped" in s) for s in skipped)
        self._dialog(kind, msg, detail=self.tr.t("learn_dump_body") if need_dump else None)
        self._analyze()

    def _refresh_history(self):
        self.hist_tree.delete(*self.hist_tree.get_children())
        for rec in history.load_history():
            self.hist_tree.insert("", "end", iid=rec["id"],
                                  values=(rec["time"], rec["folder"],
                                          len(rec.get("inis", [])),
                                          self.tr.t("rec_rolled") if rec.get("rolled_back")
                                          else self.tr.t("rec_fixed")))

    def _rollback_selected(self):
        sel = self.hist_tree.selection()
        if not sel:
            self._dialog("warning", self.tr.t("warn_history_select"))
            return
        rec_id = sel[0]
        if not self._ask_yesno(self.tr.t("confirm_rollback")):
            return
        r = history.rollback_record(rec_id)
        self.status_var.set(r["msg"])
        self._dialog("info", r["msg"])
        self._refresh_history()

    def _clear_history(self):
        if not self._ask_yesno(self.tr.t("confirm_clear")):
            return
        r = history.clear_all()
        self.status_var.set(r["msg"])
        self._dialog("info", r["msg"])
        self._refresh_history()

    def _rollback_all(self):
        if not self._ask_yesno(self.tr.t("confirm_rollback_all")):
            return
        r = history.rollback_all()
        msg = self.tr.t("status_rollback_all_done", r["total"], r["failed"])
        self.status_var.set(msg)
        self._dialog("info", msg)
        self._refresh_history()

    def _show_prompt(self):
        T = self.tr.t
        win = tk.Toplevel(self)
        win.title(T("prompt_title"))
        win.geometry("780x640")
        win.configure(bg=BG)
        hint = tk.Label(win, bg=BG, fg=MUTED, wraplength=740, justify="left",
                        font=("Microsoft YaHei UI", 9), text=T("prompt_hint"))
        hint.pack(fill="x", padx=14, pady=(14, 6))
        top = tk.Frame(win, bg=BG)
        top.pack(fill="x", padx=14)
        ttk.Button(top, text=T("prompt_copy"),
                   command=lambda: self._copy_prompt(win)).pack(side="right")
        text = tk.Text(win, font=("Microsoft YaHei UI", 9), wrap="word",
                       bg="#ffffff", fg=TEXT, relief="solid", bd=1)
        text.insert("1.0", prompt_mod.get_prompt())
        text.config(state="disabled")
        text.pack(fill="both", expand=True, padx=14, pady=(8, 14))

    def _copy_prompt(self, win):
        win.clipboard_clear()
        win.clipboard_append(prompt_mod.get_prompt())
        self.status_var.set(self.tr.t("status_copied"))
        self._dialog("info", self.tr.t("prompt_copied"))


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
