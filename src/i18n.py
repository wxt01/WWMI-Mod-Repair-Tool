# -*- coding: utf-8 -*-
"""中英双语文案表（i18n）。lang 存于 settings.json（'lang': 'zh'/'en'）。"""
import os
import json

# 默认语言
DEFAULT_LANG = "zh"

# 全部可翻译文案
STR = {
    # ---- 主窗口 ----
    "app_name": {"zh": "WWMI MOD 修复助手", "en": "WWMI Mod Repair Assistant"},
    "app_subtitle": {
        "zh": "一键修复游戏更新后失效的角色 MOD（方法 H/G/B/B2/A/D/F/E）",
        "en": "One-click fix for MODs broken by game updates"},
    "btn_settings": {"zh": "⚙ 设置", "en": "⚙ Settings"},
    "btn_prompt": {"zh": "📋 AI 修复提示词", "en": "📋 AI Repair Prompt"},
    "card_mod": {"zh": "① 选择 Mod 文件夹", "en": "① Select Mod Folder"},
    "browse": {"zh": "浏览…", "en": "Browse…"},
    "analyze": {"zh": "分析", "en": "Analyze"},
    "community_config": {"zh": "社区配置文件（可选）", "en": "Community Config (optional)"},
    "community_hint": {
        "zh": "（方法 F/G 需要，用于更新失效哈希；不内置任何社区数据）",
        "en": "(needed by F/G to remap hashes)"},
    "clear": {"zh": "清除", "en": "Clear"},
    "col_ini": {"zh": "INI 文件", "en": "INI File"},
    "col_state": {"zh": "状态", "en": "Status"},
    "col_diffuse": {"zh": "识别的主贴图", "en": "Detected Diffuse"},
    "btn_preset": {"zh": "🔧 单独修复（预设方案）", "en": "🔧 Preset Repair"},
    "btn_repair": {"zh": "一键修复（可修复项）", "en": "One-click Repair"},
    "card_history": {"zh": "② 备份记录（已修复的 Mod）", "en": "② Backup History (Repaired MODs)"},
    "col_time": {"zh": "修复时间", "en": "Repaired At"},
    "col_folder": {"zh": "Mod 文件夹", "en": "Mod Folder"},
    "col_count": {"zh": "INI 数", "en": "INIs"},
    "col_rec_state": {"zh": "状态", "en": "Status"},
    "btn_rollback": {"zh": "↩ 回滚选中（或双击记录）", "en": "↩ Rollback Selected (or double-click)"},
    "btn_rollback_all": {"zh": "⤺ 一键回滚全部", "en": "⤺ Rollback All"},
    "btn_clear_rec": {"zh": "🗑 清除记录", "en": "🗑 Clear History"},
    "rollback_hint": {
        "zh": "每行一次修复的备份；回滚 = 从 .bak 恢复原文件",
        "en": "One backup per repair; rollback restores from .bak"},
    "status_ready": {
        "zh": "就绪 ｜ H=toggle默认态兜底 G=形态变量分支 F=社区配置 E=贴图挂钩(需F8转储) RFX=漏注补全 D2=共享贴图补注 ｜ F11 全屏",
        "en": "Ready ｜ H=toggle default G=form branch F=community config E=texture hooks(need F8 dump) RFX=backfill D2=shared texture ｜ F11 fullscreen"},
    "status_pick_wuwa": {"zh": "已选择社区配置文件，重新分析以生效", "en": "Community config selected; re-analyze to apply"},
    "status_analyzed": {"zh": "分析完成：%d 个 ini，其中 %d 个可修复", "en": "Analyzed: %d ini, %d repairable"},
    "status_saved": {
        "zh": "设置已保存：Mod 起始文件夹、社区配置文件、语言（下次启动自动生效）",
        "en": "Settings saved: Mod start folder, community config, language (applied next launch)"},
    "status_repairing": {"zh": "正在修复…", "en": "Repairing…"},
    "status_repaired": {"zh": "修复完成：%d 个 ini（已自动备份）", "en": "Repaired: %d ini (backed up)"},
    "status_none": {"zh": "无需修复", "en": "Nothing to repair"},
    "status_skipped": {"zh": "跳过：%s", "en": "Skipped: %s"},
    "status_rollback_one": {"zh": "已回滚：%s", "en": "Rolled back: %s"},
    "status_rollback_all_done": {"zh": "回滚完成：%d 条，失败 %d 条", "en": "Rolled back: %d, failed: %d"},
    "status_cleared": {"zh": "已清除全部备份记录", "en": "All backup records cleared"},
    "status_copied": {"zh": "提示词已复制，粘贴给 AI 即可", "en": "Prompt copied; paste it to an AI"},
    "status_preset": {"zh": "单独修复中（方案：%s）…", "en": "Preset repairing (%s)…"},
    "rec_rolled": {"zh": "已回滚", "en": "Rolled back"},
    "rec_fixed": {"zh": "已修复", "en": "Repaired"},
    # ---- 通用弹窗 ----
    "dlg_close": {"zh": "关闭", "en": "Close"},
    "dlg_learn_more": {"zh": "了解更多", "en": "Learn More"},
    "dlg_ok": {"zh": "确定", "en": "OK"},
    "dlg_yes": {"zh": "是", "en": "Yes"},
    "dlg_no": {"zh": "否", "en": "No"},
    "dlg_cancel": {"zh": "取消", "en": "Cancel"},
    "dlg_save": {"zh": "保存", "en": "Save"},
    "dlg_info_title": {"zh": "提示", "en": "Info"},
    "dlg_warn_title": {"zh": "警告", "en": "Warning"},
    "dlg_error_title": {"zh": "错误", "en": "Error"},
    "dlg_confirm": {"zh": "确认", "en": "Confirm"},
    "dlg_success": {"zh": "成功", "en": "Success"},
    # ---- 首启语言选择 ----
    "lang_choose_title": {"zh": "选择语言 / Choose Language", "en": "Choose Language / 选择语言"},
    "lang_choose_hint": {
        "zh": "请选择界面语言（可在「⚙ 设置」中随时切换）",
        "en": "Select the UI language (can be changed anytime in ⚙ Settings)"},
    "lang_zh": {"zh": "中文", "en": "中文 (Chinese)"},
    "lang_en": {"zh": "English", "en": "English"},
    # ---- 设置窗口 ----
    "settings_title": {"zh": "设置", "en": "Settings"},
    "settings_mod_dir": {"zh": "Mod 起始文件夹（浏览 Mod 时从这里开始）", "en": "Mod start folder (browse starts here)"},
    "settings_wuwa": {"zh": "社区配置文件（Wuwa_Mod_Fixer 的 config.json，记住后下次免选）",
                      "en": "Community config (Wuwa_Mod_Fixer config.json, remembered for next time)"},
    "settings_lang": {"zh": "界面语言 / Language", "en": "Interface Language / 语言"},
    "settings_path_hint": {"zh": "设置保存在 %APPDATA%\\WWMI_MOD修复助手\\settings.json",
                           "en": "Settings stored at %APPDATA%\\WWMI_MOD修复助手\\settings.json"},
    "settings_fullscreen_hint": {
        "zh": "若窗口显示不全，请最大化窗口（或按 F11 全屏）使用",
        "en": "If parts are cut off, maximize the window (or press F11 for fullscreen)"},
    # ---- 预设方案窗口 ----
    "preset_title": {"zh": "单独修复（预设方案）", "en": "Preset Repair"},
    "preset_hint": {"zh": "选择已验证的修复方案，应用到你的 mod 文件夹：",
                    "en": "Pick a verified preset and apply it to your mod folder:"},
    "preset_col_name": {"zh": "Mod 名称", "en": "Mod Name"},
    "preset_col_author": {"zh": "作者", "en": "Author"},
    "preset_col_source": {"zh": "来源", "en": "Source"},
    "preset_col_method": {"zh": "方法", "en": "Method"},
    "preset_col_desc": {"zh": "修复思路 / 适用说明", "en": "Approach / Applicability"},
    "preset_target": {"zh": "目标 Mod 文件夹", "en": "Target Mod Folder"},
    "preset_detail": {"zh": "方案说明：%s", "en": "Preset detail: %s"},
    "preset_start": {"zh": "开始修复", "en": "Start Repair"},
    # ---- 提示词窗口 ----
    "prompt_title": {"zh": "AI 修复提示词", "en": "AI Repair Prompt"},
    "prompt_hint": {
        "zh": "如果一键修复后 MOD 仍然有问题，把下面的提示词连同你的 MOD 情况一起发给 AI，AI 会按照整套诊断与修复思路继续排查。点击「复制」后粘贴给 AI 即可。",
        "en": "If the MOD still has issues after one-click repair, send this prompt together with your MOD details to an AI; it will follow the full diagnosis & repair methodology. Click Copy and paste it to the AI."},
    "prompt_copy": {"zh": "复制全部", "en": "Copy All"},
    "prompt_copied": {"zh": "提示词已复制到剪贴板", "en": "Prompt copied to clipboard"},
    # ---- 了解更多（转储说明）----
    "learn_dump_title": {"zh": "什么是转储（Dump）？", "en": "What is a Dump?"},
    "learn_dump_body": {
        "zh": (
            "转储（Dump）是 WWMI / 3DMigoto 的调试功能：在游戏中按 F8，"
            "系统会把当前画面用到的模型与贴图资源保存到 WWMI 目录下的 "
            "FrameAnalysis-* 文件夹（含 deduped 子目录）。\n\n"
            "为什么要转储？\n"
            "游戏更新后，角色贴图的哈希值会变，MOD 里旧的挂钩全部失效，贴图不再替换。"
            "工具的方法 E / F 需要读取转储里的“游戏当前贴图”，才能把 MOD 的旧哈希更新成新哈希。\n\n"
            "怎么转储：\n"
            "1) 确认 MOD 已在 XXMI 启动器中启用；\n"
            "2) 进入游戏，把目标角色拉到镜头前（近景，最好手持武器，方便武器 MOD 也一起修）；\n"
            "3) 按 F8 完成转储（WWMI 目录下会生成新的 FrameAnalysis-* 文件夹）；\n"
            "4) 回到工具重新「分析」。\n\n"
            "转储会失败的情况：\n"
            "· 角色不在画面里 / 距离太远（只抓到远景 LOD 贴图，近景哈希缺失）→ 靠近角色再转储；\n"
            "· MOD 未启用 → 在 XXMI 启动器中开启；\n"
            "· 需要修武器但没有持武器 → 手持武器再转储。\n\n"
            "想请 AI 继续排查？\n"
            "可以把以下内容发给任意 AI（如 DSH、Codex、Claude）：\n"
            "· 你的 MOD 情况描述（哪个角色、什么现象）；\n"
            "· 本工具源码（ModRepairTool/src 文件夹）；\n"
            "· 转储文件位置（WWMI 目录下的 FrameAnalysis-*）。\n"
            "AI 会结合工具内置的「AI 修复提示词」顺着整套思路继续排查与修复。"),
        "en": (
            "A Dump is a WWMI / 3DMigoto debug feature: press F8 in-game and the "
            "models/textures used on screen are saved into a FrameAnalysis-* folder "
            "under the WWMI directory (with a deduped subfolder).\n\n"
            "Why dump?\n"
            "After a game update the texture hashes change, so every old hook in the "
            "MOD stops matching and textures are no longer replaced. Methods E/F need "
            "the dumped 'current game textures' to remap the MOD's old hashes to new ones.\n\n"
            "How to dump:\n"
            "1) Make sure the MOD is enabled in the XXMI launcher;\n"
            "2) In-game, bring the target character close to the camera (near view; "
            "holding a weapon helps fix weapon MODs too);\n"
            "3) Press F8 to dump (a new FrameAnalysis-* folder appears under WWMI);\n"
            "4) Back in the tool, click Analyze again.\n\n"
            "Why a dump can be incomplete:\n"
            "· Character off-screen or too far (only far-LOD textures captured, near-LOD "
            "hashes missing) → move closer and dump again;\n"
            "· MOD not enabled → enable it in the XXMI launcher;\n"
            "· Weapon MODs need the character to hold the weapon while dumping.\n\n"
            "Want an AI to keep troubleshooting?\n"
            "Send the following to any AI (e.g. DSH, Codex, Claude):\n"
            "· Your MOD situation (which character, what symptom);\n"
            "· This tool's source (ModRepairTool/src folder);\n"
            "· The dump location (FrameAnalysis-* under the WWMI directory).\n"
            "The AI will continue the diagnosis using the built-in 'AI Repair Prompt'.")},
    # ---- 选择转储文件夹弹窗（方法 E）----
    "dump_title": {"zh": "选择转储文件夹（FrameAnalysis-*）", "en": "Select Dump Folder (FrameAnalysis-*)"},
    "dump_hint": {
        "zh": "此 MOD 需要转储数据才能修复（方法 E：按贴图内容自动匹配新哈希）。\n请选择 WWMI 目录下的 FrameAnalysis-xxx 文件夹（游戏内按 F8 转储生成，内含 deduped 子目录）。",
        "en": "This MOD needs dump data to be repaired (Method E: auto-match new hashes by texture content).\nSelect the FrameAnalysis-xxx folder under the WWMI directory (created by pressing F8 in-game, contains a deduped subfolder)."},
    "dump_hint2": {
        "zh": "选好后会自动记住，下次修复优先使用；点「跳过」则自动查找 WWMI 目录下的转储。",
        "en": "Your choice is remembered for next time; click Skip to auto-locate dumps under the WWMI directory."},
    "dump_browse": {"zh": "浏览…", "en": "Browse…"},
    "dump_use": {"zh": "使用此文件夹", "en": "Use This Folder"},
    "dump_skip": {"zh": "跳过（自动查找）", "en": "Skip (auto-locate)"},
    "dump_warn_empty": {"zh": "请先选择转储文件夹，或点「跳过」自动查找", "en": "Pick a dump folder first, or click Skip to auto-locate"},
    "dump_warn_bad": {"zh": "%s 不是有效的转储文件夹（应包含 deduped 子目录）", "en": "%s is not a valid dump folder (should contain a deduped subfolder)"},
    # ---- 错误/跳过弹窗 ----
    "warn_pick_folder": {"zh": "请先选择 Mod 文件夹", "en": "Please select a Mod folder first"},
    "warn_preset_empty": {"zh": "预设方案库为空", "en": "Preset library is empty"},
    "warn_preset_target": {"zh": "请选择要修复的 Mod 文件夹", "en": "Please select the target Mod folder"},
    "warn_preset_select": {"zh": "请先选择一个预设方案", "en": "Please select a preset first"},
    "warn_history_select": {"zh": "请先在备份列表选中一条记录", "en": "Select a record in the backup list first"},
    "confirm_rollback": {"zh": "确认回滚这条修复记录？", "en": "Roll back this repair record?"},
    "confirm_rollback_all": {"zh": "确认回滚全部已修复的 Mod？", "en": "Roll back all repaired MODs?"},
    "confirm_clear": {"zh": "确认清除全部备份记录？（只清列表，不删除 .bak 备份文件）",
                      "en": "Clear all backup records? (list only; .bak files are kept)"},
    "repair_done": {"zh": "修复完成：%d 个 ini（已自动备份）", "en": "Repaired: %d ini (backed up)"},
    "repair_none": {"zh": "无需修复", "en": "Nothing to repair"},
    "repair_skip_note": {
        "zh": "若提示“未找到转储 deduped 目录（需 F8 转储）”，点「了解更多」查看怎么转储。",
        "en": "If you see 'deduped folder not found (F8 dump needed)', click Learn More to see how to dump."},
    "repair_skipped": {"zh": "跳过：%s", "en": "Skipped: %s"},
    # ---- 状态映射（engine 返回的中文状态 → 英文）----
    "st_fixable_h": {"zh": "可修复(H)", "en": "Fixable (H)"},
    "st_fixable_g": {"zh": "可修复(G)", "en": "Fixable (G)"},
    "st_fixable_b": {"zh": "可修复(B)", "en": "Fixable (B)"},
    "st_fixable_b2": {"zh": "可修复(B2)", "en": "Fixable (B2)"},
    "st_fixable_a": {"zh": "可修复(A)", "en": "Fixable (A)"},
    "st_fixable_rfx": {"zh": "可修复(RFX)", "en": "Fixable (RFX)"},
    "st_fixable_f": {"zh": "可修复(F)", "en": "Fixable (F)"},
    "st_fixable_e": {"zh": "可修复(E)", "en": "Fixable (E)"},
    "st_dual_ai": {"zh": "双形态(需AI)", "en": "Dual-form (needs AI)"},
    "st_fixed": {"zh": "已修复", "en": "Repaired"},
    "st_unsupported": {"zh": "不支持", "en": "Unsupported"},
    "st_unknown": {"zh": "未知", "en": "Unknown"},
}


class I18N:
    def __init__(self, lang=DEFAULT_LANG):
        self.lang = lang if lang in ("zh", "en") else DEFAULT_LANG

    def set(self, lang):
        if lang in ("zh", "en"):
            self.lang = lang

    def t(self, key, *args):
        pair = STR.get(key)
        if not pair:
            return key
        s = pair.get(self.lang) or pair.get("zh") or key
        if args:
            try:
                s = s % args
            except Exception:
                pass
        return s

    def map_state(self, zh_state):
        """把 engine 返回的中文状态映射为当前语言（未识别则原样返回）。"""
        if self.lang == "zh":
            return zh_state
        table = {
            "可修复(H)": "st_fixable_h", "可修复(G)": "st_fixable_g",
            "可修复(B)": "st_fixable_b", "可修复(B2)": "st_fixable_b2",
            "可修复(A)": "st_fixable_a", "可修复(RFX)": "st_fixable_rfx",
            "可修复(F)": "st_fixable_f", "可修复(E)": "st_fixable_e",
            "双形态(需AI)": "st_dual_ai", "已修复": "st_fixed",
            "不支持": "st_unsupported", "未知": "st_unknown",
        }
        return self.t(table.get(zh_state, "st_unknown")) if zh_state in table else zh_state


def load_lang_from_settings():
    try:
        base = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                            "WWMI_MOD修复助手")
        with open(os.path.join(base, "settings.json"), "r", encoding="utf-8") as f:
            d = json.load(f)
        lang = d.get("lang", "")
        return lang if lang in ("zh", "en") else DEFAULT_LANG
    except Exception:
        return DEFAULT_LANG


def save_lang_to_settings(lang):
    try:
        base = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                            "WWMI_MOD修复助手")
        os.makedirs(base, exist_ok=True)
        p = os.path.join(base, "settings.json")
        d = {}
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            pass
        d["lang"] = lang
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
