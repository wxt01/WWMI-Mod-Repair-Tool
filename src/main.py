# -*- coding: utf-8 -*-
"""WWMI MOD 修复助手 - 图形界面入口
用法：python main.py  （或运行打包后的 exe）
"""
import os
import sys
import json
import threading
import ctypes
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Windows 高 DPI 感知：避免窗口被系统放大导致内容溢出屏幕（按钮看不见）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
import history
import prompt as prompt_mod

APP_NAME = "WWMI MOD 修复助手"
BG = "#f5f6f8"
CARD = "#ffffff"
ACCENT = "#3b82f6"
TEXT = "#1f2937"
MUTED = "#6b7280"
BORDER = "#e5e7eb"

# 用户级设置：记住 Mod 起始文件夹 / 社区配置文件路径（跨启动持久）
SETTINGS_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                            "WWMI_MOD修复助手")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")


def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as _f:
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
        self.title(APP_NAME)
        self._screen_h = self.winfo_screenheight()
        self._screen_w = self.winfo_screenwidth()
        self.geometry("1080x760")
        self.minsize(860, 560)
        self.configure(bg=BG)
        self.current_folder = None
        self.analysis = None
        self.settings = load_settings()
        self.wuwa_var = tk.StringVar()
        if self.settings.get("wuwa_config"):
            self.wuwa_var.set(self.settings["wuwa_config"])
        self._build_style()
        self._build_ui()
        self._refresh_history()
        # 按内容高度自适应：确保底部按钮（回滚/清除）默认就可见，不依赖全屏
        self.update_idletasks()
        req_h = self.winfo_reqheight()
        self.geometry("1080x%d" % min(req_h + 4, max(600, self._screen_h - 100)))

    # ---------- 样式 ----------
    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Card.TLabelframe", background=CARD, bordercolor=BORDER,
                        borderwidth=1, relief="solid", padding=12)
        style.configure("Card.TLabelframe.Label", background=CARD, foreground=TEXT,
                        font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(14, 7))
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 10, "bold"),
                        padding=(18, 9), foreground="#ffffff", background=ACCENT)
        style.map("Accent.TButton",
                  background=[("active", "#2563eb"), ("pressed", "#1d4ed8")],
                  foreground=[("active", "#ffffff")])
        style.configure("Danger.TButton", font=("Microsoft YaHei UI", 10),
                        padding=(14, 7), foreground="#b91c1c")
        style.configure("Treeview", font=("Microsoft YaHei UI", 9), rowheight=26,
                        background=CARD, fieldbackground=CARD, bordercolor=BORDER)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"),
                        background="#eef1f5", foreground=TEXT)
        style.map("Treeview", background=[("selected", "#dbeafe")],
                  foreground=[("selected", TEXT)])
        style.configure("Status.TLabel", background=BG, foreground=MUTED,
                        font=("Microsoft YaHei UI", 9))
        style.configure("Hint.TLabel", background=BG, foreground=MUTED,
                        font=("Microsoft YaHei UI", 9))

    # ---------- 界面 ----------
    def _build_ui(self):
        pad = dict(padx=14, pady=6)

        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", **pad)
        tk.Label(header, text=APP_NAME, font=("Microsoft YaHei UI", 16, "bold"),
                 bg=BG, fg=TEXT).pack(side="left")
        tk.Label(header,
                 text="修复游戏更新后失效的角色 MOD（B/B2：作者式槽位替换 / G：形态变量分支 / A：RabbitFX窗口 / D：RFX补全 / F：社区配置 / E：哈希兜底）",
                 font=("Microsoft YaHei UI", 9), bg=BG, fg=MUTED).pack(side="left", padx=12)
        ttk.Button(header, text="⚙ 设置", style="Accent.TButton",
                   command=self._show_settings).pack(side="right", padx=(0, 8))
        ttk.Button(header, text="📋 AI 修复提示词", style="Accent.TButton",
                   command=self._show_prompt).pack(side="right")

        # --- 第一步：选择 mod 文件夹 ---
        card1 = ttk.LabelFrame(self, text="① 选择 Mod 文件夹", style="Card.TLabelframe")
        card1.pack(fill="x", **pad)
        row = tk.Frame(card1, bg=CARD)
        row.pack(fill="x")
        self.folder_var = tk.StringVar()
        tk.Entry(row, textvariable=self.folder_var, font=("Microsoft YaHei UI", 9),
                 bg="#fafafa", relief="solid", bd=1).pack(side="left", fill="x",
                                                          expand=True, ipady=4)
        ttk.Button(row, text="浏览…", command=self._pick_folder).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="分析", command=self._analyze).pack(side="left", padx=(6, 0))

        # 社区配置文件（可选）：方法 F 的数据来源，用户自行下载 Wuwa_Mod_Fixer 的 config.json
        wrow = tk.Frame(card1, bg=CARD)
        wrow.pack(fill="x", pady=(8, 0))
        tk.Label(wrow, text="社区配置文件（可选）", font=("Microsoft YaHei UI", 9),
                 bg=CARD, fg=TEXT).pack(side="left")
        tk.Entry(wrow, textvariable=self.wuwa_var, font=("Microsoft YaHei UI", 9),
                 bg="#fafafa", relief="solid", bd=1).pack(side="left", fill="x",
                                                          expand=True, ipady=4, padx=(8, 0))
        ttk.Button(wrow, text="选择…", command=self._pick_wuwa).pack(side="left", padx=(8, 0))
        ttk.Button(wrow, text="清除", command=lambda: self.wuwa_var.set("")).pack(side="left", padx=(6, 0))
        tk.Label(wrow, text="（修复时用于更新失效哈希，方法 F/G 需要；不内置任何社区数据）",
                 bg=CARD, fg=MUTED, font=("Microsoft YaHei UI", 8)).pack(side="left", padx=(10, 0))

        # 分析结果
        self.tree = ttk.Treeview(card1, columns=("file", "state", "diffuse"),
                                 show="headings", height=5)
        self.tree.heading("file", text="INI 文件")
        self.tree.heading("state", text="状态")
        self.tree.heading("diffuse", text="识别的主贴图")
        self.tree.column("file", width=300)
        self.tree.column("state", width=90, anchor="center")
        self.tree.column("diffuse", width=330)
        self.tree.pack(fill="x", pady=(10, 0))
        btnrow = tk.Frame(card1, bg=CARD)
        btnrow.pack(anchor="e", pady=(10, 0))
        ttk.Button(btnrow, text="🔧 单独修复（预设方案）",
                   command=self._preset_repair).pack(side="left", padx=(0, 8))
        ttk.Button(btnrow, text="一键修复（可修复项）", style="Accent.TButton",
                   command=self._repair).pack(side="left")

        # --- 第二步：备份记录 ---
        card2 = ttk.LabelFrame(self, text="② 备份记录（已修复的 Mod）", style="Card.TLabelframe")
        card2.pack(fill="both", expand=True, **pad)
        self.hist_tree = ttk.Treeview(card2, columns=("time", "folder", "inis", "state"),
                                      show="headings", height=7)
        self.hist_tree.heading("time", text="修复时间")
        self.hist_tree.heading("folder", text="Mod 文件夹")
        self.hist_tree.heading("inis", text="INI 数")
        self.hist_tree.heading("state", text="状态")
        self.hist_tree.column("time", width=150)
        self.hist_tree.column("folder", width=420)
        self.hist_tree.column("inis", width=70, anchor="center")
        self.hist_tree.column("state", width=80, anchor="center")
        self.hist_tree.pack(fill="both", expand=True, pady=(10, 0))
        self.hist_tree.bind("<Double-1>", lambda e: self._rollback_selected())
        btns = tk.Frame(card2, bg=CARD)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="↩ 回滚选中（或双击记录）",
                   command=self._rollback_selected).pack(side="left")
        ttk.Button(btns, text="⤺ 一键回滚全部", style="Danger.TButton",
                   command=self._rollback_all).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="🗑 清除记录", style="Danger.TButton",
                   command=self._clear_history).pack(side="left", padx=(8, 0))
        tk.Label(btns, text="每行一次修复的备份；回滚 = 从 .bak 恢复原文件",
                 bg=CARD, fg=MUTED, font=("Microsoft YaHei UI", 8)).pack(side="right")

        # --- 底部：状态栏 ---
        self.status_var = tk.StringVar(
            value="就绪 ｜ 可修复(H)=toggle默认态兜底；可修复(G)=形态变量分支；可修复(F)=社区配置修复；可修复(E)=贴图挂钩型兜底(需先F8转储)；可修复(RFX)=漏注组件补全；F11 全屏")
        ttk.Label(self, textvariable=self.status_var, style="Status.TLabel").pack(
            side="bottom", anchor="w", padx=14, pady=6)

    # ---------- 行为 ----------
    def _pick_folder(self):
        start = self.settings.get("mod_start_dir") or None
        folder = filedialog.askdirectory(title="选择 Mod 文件夹", initialdir=start)
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
            title="选择 Wuwa_Mod_Fixer 的 config.json（社区配置，从该项目 GitHub 下载）",
            initialdir=start,
            filetypes=[("JSON 配置", "*.json"), ("所有文件", "*.*")])
        if path:
            self.wuwa_var.set(path)
            self.status_var.set("已选择社区配置文件，重新分析以生效")

    def _show_settings(self):
        """设置：记住 Mod 起始文件夹与社区配置文件路径（下次打开自动生效）。"""
        win = tk.Toplevel(self)
        win.title("设置")
        win.configure(bg=CARD)
        win.geometry("640x300")
        win.transient(self)
        win.grab_set()

        body = tk.Frame(win, bg=CARD)
        body.pack(fill="both", expand=True, padx=16, pady=(16, 8))

        # Mod 起始文件夹
        tk.Label(body, text="Mod 起始文件夹（浏览 Mod 时从这里开始）",
                 font=("Microsoft YaHei UI", 10, "bold"), bg=CARD, fg=TEXT).pack(anchor="w")
        r1 = tk.Frame(body, bg=CARD)
        r1.pack(fill="x", pady=(4, 10))
        mod_var = tk.StringVar(value=self.settings.get("mod_start_dir", ""))
        tk.Entry(r1, textvariable=mod_var, font=("Microsoft YaHei UI", 9),
                 bg="#fafafa", relief="solid", bd=1).pack(side="left", fill="x",
                                                          expand=True, ipady=4)
        ttk.Button(r1, text="选择…",
                   command=lambda: mod_var.set(filedialog.askdirectory(
                       title="选择 Mod 起始文件夹",
                       initialdir=mod_var.get().strip().strip('"') or None) or mod_var.get())
                   ).pack(side="left", padx=(8, 0))
        ttk.Button(r1, text="清除", command=lambda: mod_var.set("")).pack(side="left", padx=(6, 0))

        # 社区配置文件
        tk.Label(body, text="社区配置文件（Wuwa_Mod_Fixer 的 config.json，记住后下次免选）",
                 font=("Microsoft YaHei UI", 10, "bold"), bg=CARD, fg=TEXT).pack(anchor="w")
        r2 = tk.Frame(body, bg=CARD)
        r2.pack(fill="x", pady=(4, 10))
        wuwa_var = tk.StringVar(value=self.settings.get("wuwa_config", ""))
        tk.Entry(r2, textvariable=wuwa_var, font=("Microsoft YaHei UI", 9),
                 bg="#fafafa", relief="solid", bd=1).pack(side="left", fill="x",
                                                          expand=True, ipady=4)

        def _browse_wuwa():
            d0 = os.path.dirname(wuwa_var.get().strip().strip('"')) \
                or self.settings.get("mod_start_dir") or None
            p = filedialog.askopenfilename(
                title="选择社区配置文件 config.json",
                initialdir=d0,
                filetypes=[("JSON 配置", "*.json"), ("所有文件", "*.*")])
            if p:
                wuwa_var.set(p)
        ttk.Button(r2, text="选择…", command=_browse_wuwa).pack(side="left", padx=(8, 0))
        ttk.Button(r2, text="清除", command=lambda: wuwa_var.set("")).pack(side="left", padx=(6, 0))

        def _save():
            self.settings["mod_start_dir"] = mod_var.get().strip().strip('"')
            self.settings["wuwa_config"] = wuwa_var.get().strip().strip('"')
            save_settings(self.settings)
            self.wuwa_var.set(self.settings["wuwa_config"])
            self.status_var.set("设置已保存：Mod 起始文件夹、社区配置文件（下次启动自动生效）")
            win.destroy()

        btns = tk.Frame(win, bg=CARD)
        btns.pack(fill="x", padx=16, pady=(0, 14))
        ttk.Button(btns, text="保存", style="Accent.TButton", command=_save).pack(side="right")
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="right", padx=(0, 8))
        tk.Label(btns, text="设置保存在 %APPDATA%\\WWMI_MOD修复助手\\settings.json",
                 bg=CARD, fg=MUTED, font=("Microsoft YaHei UI", 8)).pack(side="left")

    def _analyze(self):
        folder = self.folder_var.get().strip().strip('"')
        if not folder:
            messagebox.showwarning(APP_NAME, "请先选择 Mod 文件夹")
            return
        self.current_folder = folder
        r = engine.analyze_folder(folder, wuwa_path=self.wuwa_var.get().strip().strip('"') or None)
        if "error" in r:
            messagebox.showerror(APP_NAME, r["error"])
            return
        self.analysis = r
        self.tree.delete(*self.tree.get_children())
        for it in r["inis"]:
            self.tree.insert("", "end",
                             values=(it["file"], it["state"],
                                     it.get("diffuse", "") or "—"))
        n_ok = sum(1 for it in r["inis"] if it["state"].startswith("可修复"))
        self.status_var.set("分析完成：%d 个 ini，其中 %d 个可修复" % (len(r["inis"]), n_ok))

    def _preset_repair(self):
        """单独修复：从预设方案库选择已验证案例，应用到选定的 mod 文件夹。
        预设方案记录"这种结构的 mod 用什么方法修过"；实际修复仍走引擎自动检测（含方法 G）。"""
        presets = []
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(base, "presets.json"), "r", encoding="utf-8") as _f:
                presets = json.load(_f).get("presets", [])
        except Exception:
            presets = []
        if not presets:
            messagebox.showwarning(APP_NAME, "预设方案库为空")
            return

        win = tk.Toplevel(self)
        win.title("单独修复（预设方案）")
        win.configure(bg=CARD)
        win.geometry("820x520")
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="选择已验证的修复方案，应用到你的 mod 文件夹：",
                 font=("Microsoft YaHei UI", 10, "bold"), bg=CARD, fg=TEXT).pack(anchor="w", padx=14, pady=(12, 6))
        cols = ("name", "author", "source", "method", "desc")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=6)
        tree.heading("name", text="Mod 名称"); tree.column("name", width=190)
        tree.heading("author", text="作者"); tree.column("author", width=80)
        tree.heading("source", text="来源"); tree.column("source", width=110)
        tree.heading("method", text="方法"); tree.column("method", width=50, anchor="center")
        tree.heading("desc", text="修复思路 / 适用说明"); tree.column("desc", width=340)
        for pr in presets:
            tree.insert("", "end", values=(
                pr.get("name", ""), pr.get("author", ""), pr.get("source", ""),
                pr.get("method", ""), pr.get("desc", "") + " ｜ 适用：" + pr.get("applicable", "")))
        tree.pack(fill="x", padx=14, pady=(0, 8))
        tree.selection_set(tree.get_children()[0])

        frow = tk.Frame(win, bg=CARD)
        frow.pack(fill="x", padx=14, pady=4)
        tk.Label(frow, text="目标 Mod 文件夹", font=("Microsoft YaHei UI", 9),
                 bg=CARD, fg=TEXT).pack(side="left")
        fvar = tk.StringVar()
        tk.Entry(frow, textvariable=fvar, font=("Microsoft YaHei UI", 9),
                 bg="#fafafa", relief="solid", bd=1).pack(side="left", fill="x",
                                                          expand=True, ipady=4, padx=(8, 0))

        def _browse():
            d = filedialog.askdirectory(title="选择要修复的 Mod 文件夹",
                                        initialdir=self.settings.get("mod_start_dir") or None)
            if d:
                fvar.set(d)
        ttk.Button(frow, text="浏览…", command=_browse).pack(side="left", padx=(8, 0))

        detail = tk.Label(win, text="", font=("Microsoft YaHei UI", 9),
                          bg=CARD, fg=MUTED, wraplength=780, justify="left")
        detail.pack(fill="x", padx=14, pady=4)

        def _on_sel(_e=None):
            sel = tree.selection()
            if sel:
                vals = tree.item(sel[0], "values")
                if len(vals) >= 5:
                    detail.config(text="方案说明：%s" % vals[4])
        tree.bind("<<TreeviewSelect>>", _on_sel)
        _on_sel()

        def _run():
            folder = fvar.get().strip().strip('"')
            if not folder:
                messagebox.showwarning(APP_NAME, "请选择要修复的 Mod 文件夹")
                return
            sel = tree.selection()
            if not sel:
                messagebox.showwarning(APP_NAME, "请先选择一个预设方案")
                return
            pr = presets[tree.index(sel[0])]
            win.destroy()
            self.folder_var.set(folder)
            self.status_var.set("单独修复中（方案：%s）…" % pr.get("name", ""))
            self._repair()

        ttk.Button(win, text="开始修复", style="Accent.TButton", command=_run).pack(pady=(10, 12))

    def _repair(self):
        if not self.analysis:
            messagebox.showwarning(APP_NAME, "请先选择并分析 Mod 文件夹")
            return
        self.status_var.set("正在修复…")
        self.update_idletasks()
        repaired, skipped = [], []
        for it in self.analysis["inis"]:
            if not it["state"].startswith("可修复"):
                skipped.append(it["file"])
                continue
            try:
                r = engine.repair_ini(it["path"], wuwa_path=self.wuwa_var.get().strip().strip('"') or None)
            except Exception as e:
                skipped.append(it["file"] + "（修复异常：%s）" % e)
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
            msg = "修复完成：%d 个 ini（已自动备份）" % len(repaired)
        else:
            msg = "无需修复"
        if skipped:
            msg += "\n跳过：%s" % "；".join(skipped[:8])
        self.status_var.set(msg)
        messagebox.showinfo(APP_NAME, msg)
        self._analyze()

    def _refresh_history(self):
        self.hist_tree.delete(*self.hist_tree.get_children())
        for rec in history.load_history():
            self.hist_tree.insert("", "end", iid=rec["id"],
                                  values=(rec["time"], rec["folder"],
                                          len(rec.get("inis", [])),
                                          "已回滚" if rec.get("rolled_back") else "已修复"))

    def _rollback_selected(self):
        sel = self.hist_tree.selection()
        if not sel:
            messagebox.showwarning(APP_NAME, "请先在备份列表选中一条记录")
            return
        rec_id = sel[0]
        if not messagebox.askyesno(APP_NAME, "确认回滚这条修复记录？"):
            return
        r = history.rollback_record(rec_id)
        self.status_var.set(r["msg"])
        messagebox.showinfo(APP_NAME, r["msg"])
        self._refresh_history()

    def _clear_history(self):
        if not messagebox.askyesno(APP_NAME, "确认清除全部备份记录？（只清列表，不删除 .bak 备份文件）"):
            return
        r = history.clear_all()
        self.status_var.set(r["msg"])
        messagebox.showinfo(APP_NAME, r["msg"])
        self._refresh_history()

    def _rollback_all(self):
        if not messagebox.askyesno(APP_NAME, "确认回滚全部已修复的 Mod？"):
            return
        r = history.rollback_all()
        self.status_var.set("回滚完成：%d 条，失败 %d 条" % (r["total"], r["failed"]))
        messagebox.showinfo(APP_NAME, "回滚完成：%d 条，失败 %d 条" % (r["total"], r["failed"]))
        self._refresh_history()

    def _show_prompt(self):
        win = tk.Toplevel(self)
        win.title("AI 修复提示词")
        win.geometry("760x640")
        win.configure(bg=BG)
        hint = tk.Label(win, bg=BG, fg=MUTED, wraplength=720, justify="left",
                        font=("Microsoft YaHei UI", 9),
                        text="如果一键修复后 MOD 仍然有问题，把下面的提示词连同你的 MOD 情况一起发给 AI，"
                             "AI 会按照整套诊断与修复思路继续排查。点击「复制」后粘贴给 AI 即可。")
        hint.pack(fill="x", padx=14, pady=(14, 6))
        top = tk.Frame(win, bg=BG)
        top.pack(fill="x", padx=14)
        ttk.Button(top, text="复制全部", command=lambda: self._copy_prompt(win)).pack(side="right")
        text = tk.Text(win, font=("Microsoft YaHei UI", 9), wrap="word",
                       bg="#ffffff", fg=TEXT, relief="solid", bd=1)
        text.insert("1.0", prompt_mod.get_prompt())
        text.config(state="disabled")
        text.pack(fill="both", expand=True, padx=14, pady=(8, 14))

    def _copy_prompt(self, win):
        win.clipboard_clear()
        win.clipboard_append(prompt_mod.get_prompt())
        self.status_var.set("提示词已复制，粘贴给 AI 即可")
        messagebox.showinfo(APP_NAME, "提示词已复制到剪贴板")


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
