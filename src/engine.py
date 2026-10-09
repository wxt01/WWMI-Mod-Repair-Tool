# -*- coding: utf-8 -*-
"""修复引擎：双方法

方法 B（首选，作者官方修法，琳奈案例验证）：
- mod 的 [CommandListSetTexture] 段内条件形如 `if vs == 114514.1 && draw_type == 2`，
  依赖 vs 打标器；游戏更新后打标器挂钩的 vs 哈希失效 → 条件永不触发 → 贴图不替换 → 纹理乱
- 修复：把条件换成贴图格式打标（ps-t0/t3 == 1718.3/1718.6）+ 加 [TextureOverrideMainColorFeature]
  （BC7_TYPELESS 方形主贴图 → filter_index = 1718.3），不依赖任何 vs/ps 哈希
- 游戏 shader 真实槽位：t3=漫反射、t0=法线、t2=材质参数(light)、t8=附加；直接改 ps-t0/t2/t3/t8

方法 A（RabbitFX 精确窗口，绯雪/莫宁案例验证）：
- mod 无 SetTexture 条件结构 / 方法 B 不适用时使用
- 在原始 SetTexture 窗口内插入 RabbitFX Diffuse/Normalmap + SetTextures，窗口结束前 ClearTSR
"""
import os
import re
import sys
import shutil
import datetime
import struct
import numpy as np

RABBIT_SET = "run = Commandlist\\RabbitFX\\SetTextures"
RABBIT_CLEAR = "run = Commandlist\\RabbitFX\\ClearTSR"
MARK_DIFFUSE = "Resource\\RabbitFX\\Diffuse = ref "
MARK_NORMAL = "Resource\\RabbitFX\\Normalmap = ref "
MARK_MATERIAL = "Resource\\RabbitFX\\Materialmap = ref "

# 方法 B 相关
FEATURE_SECTION = """[TextureOverrideMainColorFeature]
match_type = Texture2D
match_format = BC7_TYPELESS
match_width = height
match_height = >1
match_bind_flags = shader_resource
if $object_detected
    allow_duplicate_hash = overrule
    filter_index = 1718.3
endif
"""
METHOD_B_COND = "if (ps-t0 == 1718.3 && ps-t3 == 1718.3) || (ps-t0 == 1718.6 && ps-t3 == 1718.6)"


def read_text(path):
    raw = open(path, "rb").read()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    return has_bom, raw.decode("utf-8-sig")


def write_text(path, has_bom, text):
    if has_bom:
        text = "\ufeff" + text
    open(path, "wb").write(text.encode("utf-8"))


def is_repaired(text):
    """判定是否已是修复版：方法 A（RabbitFX 管道）、方法 B（1718.3 格式打标+条件）、
    方法 E（贴图哈希已更新）或方法 F（社区配置修复）"""
    if F_MARK in text or E_MARK in text:
        return True
    if RABBIT_SET in text:
        return True
    if re.search(r"filter_index\s*=\s*1718\.3", text) and "ps-t0 == 1718.3" in text:
        return True
    return False


def _get_section(text, name):
    """按段名取 [name] 段的正文行（到下一个 [ 段为止），返回行列表或 None"""
    m = re.search(r"^\[" + re.escape(name) + r"\]\s*$", text, re.M)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^\[", rest, re.M)
    body = rest[:nxt.start()] if nxt else rest
    return body.splitlines()


def _vs_cond_count(text):
    """统计 SetTexture 段内 vs 打标条件行数。
    - 行内含 vs == 且含 ||（合并写法，如 if (vs == A || vs == B)）→ 计 1 个条件
    - 行内含 if vs == / else if vs ==（无 ||）→ 各自计 1 个条件
    - 返回 (条件数, 是否有 ref 替换, 条件行内容列表)"""
    body = _get_section(text, "CommandListSetTexture")
    if body is None:
        return 0, False, []
    cond_lines = []
    has_ref = False
    for ln in body:
        if re.match(r"^\s*ps-t\d+\s*=\s*ref\s+", ln):
            has_ref = True
        m = re.match(r"^\s*(?:else\s+)?if\s*(?:\()?\s*vs\s*==\s*[\d.]+", ln)
        if m:
            cond_lines.append(ln)
    return len(cond_lines), has_ref, cond_lines


def has_vs_mark_condition(text):
    """方法 B 适用判定（SpacePig 作者式）：
    SetTexture 段内恰【1 个】vs 条件行（合并写法 || 也算 1 个）+ 有 ps-tN = ref 标准替换
    → 方法 B 适用（单分支，如琳奈、role_page 形态）；
    多个条件行（红/蓝或双形态分支）→ 方法 B 会破坏分支，需人工转储直改哈希。"""
    n, has_ref, _ = _vs_cond_count(text)
    return n == 1 and has_ref


def find_textures(text, folder):
    """扫描资源段 -> filename，返回 {资源名: 绝对路径}
    兼容三种命名：[Resource_Texture_X]（下划线中缀）、[ResourceTexture_X]（无中缀）、
    [ResourceTextureN]（无中缀纯数字后缀，如 ResourceTexture8/12/13）"""
    res = {}
    for m in re.finditer(r"^\[(Resource_?Texture_?[^\]]+)\]\s*$", text, re.M):
        name = m.group(1)
        seg = text[m.end():]
        fm = re.search(r"^\s*filename\s*=\s*(.+?)\s*$", seg, re.M)
        if fm:
            raw_path = fm.group(1).strip().strip('"')
            res[name] = os.path.normpath(os.path.join(folder, raw_path))
    return res


def _dds_info(path):
    """解析 DDS 头，返回 (宽, 高, 是否SRGB, 格式组)。
    格式组：'bc1'/'bc3'/'bc5'/'bc7'/'other'；解析失败返回 None"""
    try:
        with open(path, "rb") as f:
            head = f.read(140)
    except OSError:
        return None
    if len(head) < 128 or head[:4] != b"DDS ":
        return None
    w, h = struct.unpack("<II", head[12:20])
    fourcc = head[84:88]
    if fourcc == b"DX10":
        if len(head) < 132:
            return None
        fmt = struct.unpack("<I", head[128:132])[0]
        # DXGI_FORMAT: 71=BC1_UNORM 72=BC1_SRGB 77=BC3_UNORM 78=BC3_SRGB
        # 80=BC4 83=BC5 98=BC7_UNORM 99=BC7_SRGB 95=BC6H 28=R8G8B8A8
        srgb = fmt in (72, 78, 99)
        if fmt in (71, 72):
            group = "bc1"
        elif fmt in (77, 78):
            group = "bc3"
        elif fmt == 80:
            group = "bc4"
        elif fmt == 83:
            group = "bc5"
        elif fmt in (98, 99):
            group = "bc7"
        else:
            group = "other"
        return w, h, srgb, group
    code = fourcc.hex()
    if code == "44585431":  # DXT1
        return w, h, False, "bc1"
    if code == "44585433":  # DXT3
        return w, h, False, "other"
    if code == "44585435":  # DXT5
        return w, h, False, "bc3"
    if code == "31495441":  # ATI1
        return w, h, False, "bc4"
    if code == "32495441":  # ATI2
        return w, h, False, "bc5"
    return w, h, False, "other"


def _score(name):
    n = name.lower()
    s = 0
    if "main" in n:
        s += 100
    if "color" in n or "colour" in n:
        s += 50
    if "red" in n or "blue" in n:
        s += 20
    if "diffuse" in n:
        s += 60
    if "normal" in n or "nor" in n:
        s -= 300
    if "mask" in n:
        s -= 150
    if "shine" in n or "light" in n or "shadow" in n:
        s -= 120
    if "other" in n or "ao" in n:
        s -= 100
    if "rough" in n or "metal" in n:
        s -= 100
    return s


def pick_diffuse_normal(res, ini_name=""):
    """从资源表挑主贴图（漫反射）与法线贴图；ini_name 辅助红/蓝版选择"""
    dds = {}
    for k, v in res.items():
        if v.lower().endswith(".dds") and os.path.exists(v):
            dds[k] = v
    if not dds:
        for k, v in res.items():
            if os.path.exists(v):
                dds[k] = v
    ini_l = (ini_name or "").lower()

    def score(kv):
        k, v = kv
        s = _score(k)
        base = os.path.basename(v).lower()
        if "red" in base:
            s += 25
        if "blue" in base:
            s += 25
        if "blue" in ini_l and "blue" in base:
            s += 50
        if "red" in ini_l and "red" in base:
            s += 50
        if "2" in ini_l and "blue" in base:
            s += 60
        if "1" in ini_l and "red" in base:
            s += 60
        if ini_l.endswith("_2") or ini_l.endswith("2.ini"):
            pass
        return s

    ranked = sorted(dds.items(),
                    key=lambda kv: (-score(kv), -os.path.getsize(kv[1]) if os.path.exists(kv[1]) else 0))
    diffuse = ranked[0][0] if ranked else None
    normal = None
    for k in dds:
        if "normal" in k.lower() or k.lower().endswith("_n") or "nor" in k.lower():
            normal = k
            break
    return diffuse, normal


_MATERIAL_KEYS = ("gloss", "rough", "metal", "ao", "spec", "rma", "material", "light", "shadow")


def pick_textures(res, ini_name=""):
    """三槽位识别：返回 (漫反射, 法线, 材质图)。
    法线启发式：normal 关键词 > 非SRGB的BC5/BC7中等尺寸图（排除主贴图）。
    材质图启发式：gloss/rough/metal/ao/spec/rma/material/light/shadow 关键词（BC1/BC4单通道优先）。"""
    dds = {}
    for k, v in res.items():
        if v.lower().endswith(".dds") and os.path.exists(v):
            dds[k] = v
    if not dds:
        for k, v in res.items():
            if os.path.exists(v):
                dds[k] = v

    diffuse, _ = pick_diffuse_normal(dds, ini_name)

    normal = None
    for k in dds:
        if k != diffuse and ("normal" in k.lower() or k.lower().endswith("_n") or "nor" in k.lower()):
            normal = k
            break
    if normal is None:
        cands = []
        for k, v in dds.items():
            if k == diffuse:
                continue
            info = _dds_info(v)
            if info and not info[2] and info[3] in ("bc5", "bc7") and 256 <= info[0] <= 4096:
                cands.append((k, info[0] * info[1]))
        if cands:
            normal = max(cands, key=lambda x: x[1])[0]

    material = None
    for k, v in dds.items():
        if k in (diffuse, normal):
            continue
        n = k.lower()
        if not any(mk in n for mk in _MATERIAL_KEYS):
            continue
        info = _dds_info(v)
        if material is None:
            material = k
        else:
            gi = info[3] if info else "other"
            g_cur = None
            if material in dds:
                mi = _dds_info(dds[material])
                g_cur = mi[3] if mi else "other"
            if gi in ("bc1", "bc4") and g_cur not in ("bc1", "bc4"):
                material = k
    return diffuse, normal, material


def find_run_lines(text, cmd):
    """返回所有 run = cmd 的行号（0-based）与缩进"""
    out = []
    for i, line in enumerate(text.splitlines()):
        m = re.match(r"^(\s*)run\s*=\s*" + re.escape(cmd) + r"\s*$", line)
        if m:
            out.append((i, m.group(1)))
    return out


def _ensure_t2_save_restore(text):
    """SetTexture 段若没保存 t2、RestoreTexture 段若没恢复 t2，则补齐（写入 t2 必须配套）"""
    lines = text.splitlines()
    new_lines = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        new_lines.append(line)
        if re.match(r"^\[CommandListSetTexture\]\s*$", line.strip()):
            # 收集段内行，检查是否有 ResourceTempT2
            j = i + 1
            seg = []
            while j < n and not re.match(r"^\[", lines[j].strip()):
                seg.append(lines[j])
                j += 1
            has_t2 = any(re.match(r"^\s*ResourceTempT2\s*=\s*ref\s+ps-t2\s*$", s) for s in seg)
            if not has_t2:
                # 在段内第一个 ResourceTemp 行前插入 T2 保存
                for k, s in enumerate(seg):
                    if re.match(r"^\s*ResourceTempT\d+\s*=", s):
                        indent = re.match(r"^(\s*)", s).group(1)
                        seg.insert(k, indent + "ResourceTempT2 = ref ps-t2")
                        break
                else:
                    indent = "    "
                    seg.insert(0, indent + "ResourceTempT2 = ref ps-t2")
                new_lines.extend(seg)
                i = j
                continue
            new_lines.extend(seg)
            i = j
            continue
        if re.match(r"^\[CommandListRestoreTexture\]\s*$", line.strip()):
            j = i + 1
            seg = []
            while j < n and not re.match(r"^\[", lines[j].strip()):
                seg.append(lines[j])
                j += 1
            has_t2 = any(re.match(r"^\s*ps-t2\s*=\s*ref\s+ResourceTempT2\s*$", s) for s in seg)
            if not has_t2:
                # 在段首插 T2 恢复
                for k, s in enumerate(seg):
                    if re.match(r"^\s*if\s+ResourceTempT\d+", s):
                        indent = re.match(r"^(\s*)", s).group(1)
                        seg.insert(k, indent + "if ResourceTempT2 !== null")
                        seg.insert(k + 1, indent + "    ps-t2 = ref ResourceTempT2")
                        seg.insert(k + 2, indent + "    ResourceTempT2 = null")
                        seg.insert(k + 3, indent + "endif")
                        break
                else:
                    indent = "    "
                    seg.insert(0, indent + "if ResourceTempT2 !== null")
                    seg.insert(1, indent + "    ps-t2 = ref ResourceTempT2")
                    seg.insert(2, indent + "    ResourceTempT2 = null")
                    seg.insert(3, indent + "endif")
                new_lines.extend(seg)
                i = j
                continue
            new_lines.extend(seg)
            i = j
            continue
        i += 1
    return "\n".join(new_lines)


def _split_vs_branches(body):
    """把 SetTexture 段按 vs 条件行切成 (条件行原文, 缩进, 该块行列表)"""
    branches = []
    cur = None
    for ln in body:
        m = re.match(r"^(\s*)(?:else\s+)?if\s*(?:\(\s*)?vs\s*==\s*[\d.]+", ln)
        if m:
            if cur is not None:
                branches.append(cur)
            cur = [ln, m.group(1), []]
        elif cur is not None:
            cur[2].append(ln)
    if cur is not None:
        branches.append(cur)
    return branches


def _branch_main_slots(body):
    """每个分支绑定 Resource_Texture_main 的槽位列表"""
    out = []
    for cond, indent, block in _split_vs_branches(body):
        slots = []
        for ln in block:
            m = re.match(r"^\s*ps-t(\d+)\s*=\s*ref\s+Resource_Texture_main\b", ln)
            if m:
                slots.append(m.group(1))
        out.append((cond, indent, slots))
    return out


def _apply_method_b_dual(path, has_bom, text):
    """双形态分支修复（作者修复版通法）：各分支用不同槽位打标区分"""
    body = _get_section(text, "CommandListSetTexture")
    info = _branch_main_slots(body)
    if len(info) < 2:
        return {"ok": False, "reason": "未识别到多个 vs 分支"}
    slot_map = {}
    for cond, indent, slots in info:
        if not slots:
            return {"ok": False, "reason": "分支缺少 Resource_Texture_main 绑定，无法推断区分槽位"}
        # 取该分支 main 绑定槽（常见 t3/t2）；取第一个（作者惯例）
        slot_map[cond] = slots[0]
    slots = list(slot_map.values())
    if len(set(slots)) < 2:
        return {"ok": False, "reason": "各分支 main 绑定同一槽位，格式打标无法区分形态；需AI转储直改哈希"}

    # 逐行替换 vs 条件行
    lines = text.splitlines()
    new_lines = []
    replaced = 0
    in_set = False
    for ln in lines:
        if ln.strip().startswith("[CommandListSetTexture]"):
            in_set = True
        elif ln.strip().startswith("[") and in_set:
            in_set = False
        if in_set:
            m = re.match(r"^(\s*)(?:else\s+)?if\s*(?:\(\s*)?vs\s*==\s*([\d.]+)", ln)
            if m:
                cond = ln  # 原文做 key（trim）
                key = None
                for c in slot_map:
                    if c.strip() == ln.strip():
                        key = c
                        break
                if key is None:
                    return {"ok": False, "reason": "条件行匹配失败"}
                t = slot_map[key]
                new_lines.append(m.group(1) + "if (ps-t0 == 1718.3 && ps-t%d == 1718.3) || (ps-t0 == 1718.6 && ps-t%d == 1718.6)" % (int(t), int(t)))
                replaced += 1
                continue
        new_lines.append(ln)
    text = "\n".join(new_lines)
    if replaced != len(info):
        return {"ok": False, "reason": "条件行替换数量不符"}

    # 打标器（方法 B 同款）
    if "[TextureOverrideMainColorFeature]" not in text:
        block = FEATURE_SECTION.strip("\n")
        if "\n\n[CommandListSetTexture]" in text:
            text = text.replace("\n\n[CommandListSetTexture]", "\n\n" + block + "\n\n[CommandListSetTexture]", 1)
        else:
            text = block + "\n" + text

    # 写回
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path + ".bak_" + ts
    with open(path, "w", encoding="utf-8-sig" if has_bom else "utf-8", newline="\n") as f:
        f.write(text)
    return {"ok": True, "method": "B2(双分支)", "diffuse": "沿用原贴图资源", "backup": bak}



def _find_var_setters(text):
    """方法 G：找 TextureOverride 段内设置 $var = 1 的 (变量名, 段名, hash) 列表。
    这类段是"形态标记"——某个形态的专属网格出现时把变量置 1，供窗口分支判断。
    排除 [TextureOverrideComponentN] 组件网格打标段（设 $object_detected 等通用出现标记，非形态）。"""
    out = []
    for m in re.finditer(r'(?m)^\[TextureOverride([^\]]+)\]\s*$', text):
        name = m.group(1)
        if re.match(r'Component\d+$', name):
            continue  # 组件打标段：通用出现标记，非形态变量
        rest = text[m.end():]
        nxt = re.search(r'^\[', rest, re.M)
        body = rest[:nxt.start()] if nxt else rest
        hp = re.search(r'^\s*hash\s*=\s*([0-9a-fA-F]{8})', body, re.M)
        vm = re.search(r'^\s*\$(\w+)\s*=\s*([01])', body, re.M)
        if vm and vm.group(2) == '1' and hp:
            out.append((vm.group(1), name, hp.group(1).lower()))
    return out


def _detect_method_g(text, folder=None):
    """方法 G 适用：窗口命令体内 >=2 个 vs 分支（多形态）+ 存在形态变量标记段。
    folder 给定时跨文件查找标记（main.ini 控制层放标记、mod_x.ini 放窗口的多文件 mod）。"""
    sec = _get_section(text, "CommandListSetTexture")
    if not sec:
        return False
    n = sum(1 for ln in sec if re.match(r'\s*(else\s+)?if\s+vs\s*==', ln.strip()))
    if n < 2:
        return False
    if _find_var_setters(text):
        return True
    # 跨文件：同目录其他 ini（main.ini 控制层常放形态标记）
    if folder:
        try:
            others = [os.path.join(folder, o) for o in os.listdir(folder)
                      if o.lower().endswith('.ini') and o != os.path.basename(folder)]
        except OSError:
            others = []
        for op in others:
            try:
                _, otext = read_text(op)
            except OSError:
                continue
            if _find_var_setters(otext):
                return True
    return False


def _pick_branch_main(body_lines):
    """分支内选主贴图(Diffuse)与法线(Normal)资源：优先含 Main/Normal 关键词，退 t3/t0 槽"""
    main, normal = None, None
    for ln in body_lines:
        m = re.search(r'ps-t(\d)\s*=\s*ref\s+(\S+)', ln)
        if not m:
            continue
        slot, res = m.group(1), m.group(2)
        if res.lower() == 'null':
            continue
        if 'main' in res.lower():
            if main is None:
                main = res
        elif 'normal' in res.lower():
            if normal is None:
                normal = res
    if not main:
        for ln in body_lines:
            m = re.search(r'ps-t(\d)\s*=\s*ref\s+(\S+)', ln)
            if m and m.group(2).lower() != 'null' and m.group(1) in ('3', '0'):
                main = m.group(2)
                break
    return main, normal


def _apply_method_g(path, has_bom, text, wuwa_path=None, override_path=None):
    """方法 G（绯雪/Hiyuki 案例通法）：多形态窗口的 vs 分支 -> 形态变量分支
    1) 找形态变量标记段（TextureOverride 设 $var=1）与其 hash——跨文件：优先当前文件，
       同目录其他 ini 也可（如 main.ini 控制层放标记、mod_x.ini 放窗口的多文件 mod）
    2) 该 hash 从社区配置映射（replace[0]->key）更新为新值 -> 形态标记恢复（写回所在文件）
    3) 窗口内 vs 条件整行改写为 $var == 0 / $var == 1 ...（分支按序编号）
    4) 各分支内注入 RabbitFX（Diffuse=该分支主贴图 + Normalmap + SetTextures）
    5) Restore 前插 ClearTSR
    适用：SetTexture 窗口多 vs 分支（红/蓝等形态）依赖失效打标器；mod 自带形态变量可替代"""
    setters = _find_var_setters(text)
    setter_src = path
    if not setters:
        folder = os.path.dirname(path)
        base = os.path.basename(path)
        try:
            others = [os.path.join(folder, o) for o in os.listdir(folder)
                      if o.lower().endswith('.ini') and o != base]
        except OSError:
            others = []
        for op in others:
            try:
                _, otext = read_text(op)
            except OSError:
                continue
            s = _find_var_setters(otext)
            if s:
                setters = s
                setter_src = op
                break
    if not setters:
        return {"ok": False, "reason": "未找到形态变量标记段（当前与同目录 ini 均无 $var=1 的 TextureOverride）"}

    # ---- 1) 形态变量选择 + 标记 hash 更新（社区配置映射 旧->新）----
    # 优先选"哈希在社区配置有旧->新映射"的 setter：那是失效的形态标记网格；
    # 排除 object_detected 等通用标记变量（无映射，非形态）
    config = _load_community_config(wuwa_path, override_path)

    def _lookup_new(h):
        for _n, _c in config.items():
            for _o, _new in (_c.get("hash_replace") or {}).items():
                if _o.lower() == h:
                    return _new
            for _mh in (_c.get("match") or []):
                if _mh.lower() == h and _c.get("main_new"):
                    return _c["main_new"]
        return None

    # 形态变量评分：① 哈希在社区配置有映射(100) ② 段名/变量名含形态语义(10)
    # ③ 设置次数越少越像形态标记（工具/UI 开关变量常出现在多个段，形态变量只出现在 1 个段）
    from collections import Counter
    _cnt = Counter(_s[0] for _s in setters)
    _FORM_WORDS = ('blue', 'red', 'form', 'mode', 'variant', 'swap', 'morph', 'phase', 'color')

    def _form_score(_s):
        _n, _name, _h = _s
        _sc = 0
        if _lookup_new(_h):
            _sc += 100
        _low = (_name + ' ' + _n).lower()
        if any(_w in _low for _w in _FORM_WORDS):
            _sc += 10
        _sc += max(0, 5 - _cnt[_n])   # 出现 1 次 +4，5 次 0，更多为负
        return _sc

    var, setter_name, old_hash = max(setters, key=_form_score)
    new_hash = _lookup_new(old_hash)

    # ---- 2) 窗口 vs 分支 -> 变量分支 + 各分支注入 ----
    sec = _get_section(text, "CommandListSetTexture")
    if not sec:
        return {"ok": False, "reason": "无 CommandListSetTexture 窗口"}
    lines = list(sec)
    heads = []
    for idx, ln in enumerate(lines):
        if re.match(r'\s*(else\s+)?if\s+vs\s*==', ln.strip()):
            heads.append(idx)
    if not heads:
        return {"ok": False, "reason": "窗口内无 vs 分支"}
    blocks = []
    for hi, h in enumerate(heads):
        end = len(lines)
        for k in range(h + 1, len(lines)):
            st = lines[k].strip()
            if st.startswith('else if ') and 'vs' in st:
                end = k
                break
            if st == 'endif':
                end = k
                break
        blocks.append((h, end))
    insertions = []
    injected = 0
    for h, end in blocks:
        hdr = lines[h]
        indent = hdr[:len(hdr) - len(hdr.lstrip())]
        body = lines[h + 1:end]
        main, normal = _pick_branch_main(body)
        if not main:
            continue
        last = None
        for k in range(end - 1, h, -1):
            if lines[k].strip():
                last = k
                break
        if last is None:
            continue
        ins = [indent + MARK_DIFFUSE + main]
        if normal:
            ins.append(indent + MARK_NORMAL + normal)
        ins.append(indent + RABBIT_SET)
        insertions.append((last + 1, ins))
        injected += 1
    new_lines = list(lines)
    for pos, ins in sorted(insertions, key=lambda x: -x[0]):
        for j, iln in enumerate(ins):
            new_lines.insert(pos + j, iln)
    final = []
    branch_no = -1
    for ln in new_lines:
        m = re.match(r'^(\s*)(?:else\s+)?if\s+vs\s*==\s*([\d.]+)', ln)
        if m:
            branch_no += 1
            pref = m.group(1)
            if branch_no == 0:
                final.append(pref + "if $%s == 0" % var)
            else:
                final.append(pref + "else if $%s == %d" % (var, branch_no))
            continue
        final.append(ln)
    new_sec = "\n".join(final)
    if injected == 0:
        return {"ok": False, "reason": "分支内未识别到主贴图资源"}

    # ---- 3) 写回窗口段 ----
    m = re.search(r'(?m)^\[CommandListSetTexture\]\s*$', text)
    if not m:
        return {"ok": False, "reason": "窗口段定位失败"}
    rest = text[m.end():]
    nxt = re.search(r'^\[', rest, re.M)
    end = m.end() + (nxt.start() if nxt else len(rest))
    text = text[:m.start()] + "[CommandListSetTexture]\n" + new_sec + "\n\n" + text[end:]

    # ---- 4) 形态标记 hash 更新（写回标记所在文件：本文件或同目录 ini）----
    if new_hash and setter_src != path:
        # 标记在别的文件：先备份该文件，再独立更新 setter hash（只改该段 hash 行）
        s_has_bom, s_text = read_text(setter_src)
        if is_repaired(s_text) and re.search(r'\b' + re.escape(new_hash) + r'\b', s_text):
            pass  # 已是新版，无需重复更新
        else:
            pat_s = re.compile(r'(?m)^(\[TextureOverride' + re.escape(setter_name) + r'\]\s*\n(?:.*\n)*?)\s*hash\s*=\s*' + re.escape(old_hash) + r'\s*$')
            mh_s = pat_s.search(s_text)
            if mh_s:
                s_text2 = s_text[:mh_s.start(1)] + mh_s.group(1) + "hash = " + new_hash + s_text[mh_s.end():]
                s_bak = setter_src + ".bak_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                shutil.copy2(setter_src, s_bak)
                write_text(setter_src, s_has_bom, s_text2)
    elif new_hash:
        pat = re.compile(r'(?m)^(\[TextureOverride' + re.escape(setter_name) + r'\]\s*\n(?:.*\n)*?)\s*hash\s*=\s*' + re.escape(old_hash) + r'\s*$')
        mh = pat.search(text)
        if mh:
            text = text[:mh.start(1)] + mh.group(1) + "hash = " + new_hash + text[mh.end():]
        else:
            text2 = re.sub(r'(?m)^(\s*hash\s*=\s*)' + re.escape(old_hash) + r'(\s*)$', lambda mm: mm.group(1) + new_hash + mm.group(2), text, count=1)
            if text2 != text:
                text = text2

    # ---- 5) Restore 前插 ClearTSR ----
    lines = text.splitlines()
    outl = []
    for ln in lines:
        m2 = re.match(r'^(\s*)run\s*=\s*CommandListRestoreTexture\s*$', ln)
        if m2:
            outl.append(m2.group(1) + RABBIT_CLEAR)
        outl.append(ln)
    text = "\n".join(outl)

    if F_MARK not in text:
        text = "; " + F_MARK + "\n" + text
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path + ".bak_" + ts
    shutil.copy2(path, bak)
    write_text(path, has_bom, text)
    return {"ok": True, "method": "G(变量分支)", "var": var,
            "hash_updated": (old_hash, new_hash) if new_hash else None,
            "branches": injected, "backup": bak}


def _apply_method_b(path, has_bom, text):
    """方法 B（作者官方修法）：
    1) SetTexture 段内 `if vs == X` 条件整行 → 1718.3/1718.6 格式打标条件
    2) 若无 [TextureOverrideMainColorFeature] 则插入（BC7_TYPELESS 方形 → 1718.3）
    不改贴图资源（沿用 mod 自己的 ps-t0/t2/t3/t8 替换）"""
    lines = text.splitlines()
    new_lines = []
    cond_replaced = False
    for ln in lines:
        m = re.match(r"^(\s*)(?:else\s+)?if\s*(?:\(\s*)?vs\s*==\s*[\d.]+", ln)
        if m and ("vs ==" in ln):
            new_lines.append(m.group(1) + METHOD_B_COND)
            cond_replaced = True
        else:
            new_lines.append(ln)
    text = "\n".join(new_lines)

    if not cond_replaced:
        return {"ok": False, "reason": "SetTexture 段未发现 vs 打标条件"}

    if not re.search(r"^\[TextureOverrideMainColorFeature\]\s*$", text, re.M):
        anchor = re.search(r"^\[CommandListSetTexture\]\s*$", text, re.M)
        if anchor:
            text = text[:anchor.start()] + FEATURE_SECTION + "\n" + text[anchor.start():]
        else:
            return {"ok": False, "reason": "未找到 SetTexture 段锚点"}

    # ---- t5 槽兜底清理（作者洛瑟拉修复版 v1.0.1 手法）：防残留槽污染 ----
    if "ResourceTempT5" not in text:
        text = _add_t5_cleanup(text)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path + ".bak_" + ts
    shutil.copy2(path, bak)
    write_text(path, has_bom, text)
    return {"ok": True, "method": "B", "diffuse": "沿用原贴图资源", "backup": bak}


def _add_t5_cleanup(text):
    """给 SetTexture/Restore 段补 t5 备份→清空→恢复"""
    lines = text.splitlines()
    set_start = rst_start = None
    for i, ln in enumerate(lines):
        if ln.strip() == "[CommandListSetTexture]":
            set_start = i
        elif ln.strip() == "[CommandListRestoreTexture]":
            rst_start = i
            break
    if set_start is None:
        return text

    # ① 备份行：最后一个 ResourceTempT\d+ = ref ps-t\d+ 后插入
    last_bak = None
    for i in range(set_start + 1, len(lines)):
        ln = lines[i]
        if re.match(r"^ResourceTempT\d+\s*=\s*ref\s+ps-t\d+", ln):
            last_bak = i
        elif ln.strip().startswith("[") or ln.strip().startswith("if "):
            break
    if last_bak is not None:
        indent = lines[last_bak][:len(lines[last_bak]) - len(lines[last_bak].lstrip())]
        lines.insert(last_bak + 1, indent + "ResourceTempT5 = ref ps-t5")

    # ② 条件块内：ps-t3 = ref 主贴图替换行后插入 ps-t5 = null
    for i in range(set_start + 1, len(lines)):
        if lines[i].strip().startswith("[") or (rst_start is not None and i >= rst_start):
            break
        if re.match(r"^\s*ps-t3\s*=\s*ref\s+Resource_Texture_main", lines[i]):
            ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
            if not any("ps-t5 = null" in x for x in lines[set_start:rst_start or len(lines)]):
                lines.insert(i + 1, ind + "ps-t5 = null")
            break

    # ③ Restore 段末尾补 t5 恢复
    if rst_start is not None:
        end = rst_start + 1
        while end < len(lines) and lines[end].strip():
            end += 1
        tail = [
            "if ResourceTempT5 !== null",
            "    ps-t5 = ref ResourceTempT5",
            "    ResourceTempT5 = null",
            "endif",
            "",
        ]
        lines[end:end] = tail

    # ④ [ResourceTempT5] 声明段（若存在 [ResourceTempT0] 等声明）
    has_decl = any(re.match(r"^\[ResourceTempT\d+\]\s*$", ln) for ln in lines)
    if has_decl and not any(ln.strip() == "[ResourceTempT5]" for ln in lines):
        for i, ln in enumerate(lines):
            if re.match(r"^\[ResourceTempT\d+\]\s*$", ln):
                # 插到最后一个 ResourceTemp 声明后
                j = i
                while j + 1 < len(lines) and re.match(r"^\[ResourceTempT\d+\]\s*$", lines[j + 1]):
                    j += 1
                lines.insert(j + 1, "[ResourceTempT5]")
                break

    return "\n".join(lines)


def repair_ini(path, diffuse_res=None, normal_res=None, material_res=None, wuwa_path=None, override_path=None, dedup_folder=None):
    """修复入口：方法 B（作者式 ps-t 替换+格式打标）优先，方法 A（RabbitFX 窗口）后备，
    RFX 补全（漏注组件）单独处理"""
    has_bom, text = read_text(path)
    if is_repaired(text):
        # 误判防护：作者原生内置 RabbitFX 的 mod（如 Nait3D-Hiyuki）会被判"已修复"，
        # 但仍可能缺 toggle 默认态兜底（方法 H）→ 优先二次检测
        h_var = _detect_method_h(text)
        if h_var:
            return _apply_method_h(path, has_bom, text, h_var)
        # RFX 补全只适用于「无 SetTexture 窗口的组件挂钩型」已修复 mod（尤诺女仆场景）：
        # 窗口型已修复（绯雪/莫宁等：窗口内统一注入，组件段本就不需要注入）绝不补全，
        # 否则会把窗口贴图重复灌到每个组件段，导致纹理错乱
        if RABBIT_SET in text and not _window_present(text, "CommandListSetTexture"):
            missing = _find_components_without_rfx(text)
            if missing:
                triplet = _find_rfx_triplet(text)
                return _apply_rfx_backfill(path, has_bom, text, missing, triplet)
        return {"ok": False, "reason": "已是修复版"}

    set_lines = find_run_lines(text, "CommandListSetTexture")
    rst_lines = find_run_lines(text, "CommandListRestoreTexture")

    if not (_window_present(text, "CommandListSetTexture") and _window_present(text, "CommandListRestoreTexture")):
        h_var = _detect_method_h(text)
        if h_var:
            return _apply_method_h(path, has_bom, text, h_var)
        if _find_texture_overrides(text):
            # 贴图挂钩型：方法 F（社区配置，人眼标注准确）优先，方法 E（自动匹配）兜底
            r = _apply_method_f(path, has_bom, text, os.path.dirname(path), wuwa_path, override_path)
            if r["ok"]:
                # 方法 D2：方法 F 注入后仍有组件漏注（社区语义未覆盖但贴图文件名
                # Components-N-M 标签显示与已注入组件共享贴图，如 iuno_maid_mk3 的 C7 鞋子
                # 与 C4 共用 Components-4-7）→ 复用共享组件三件套补注
                _, t2 = read_text(path)
                missing2 = _find_components_without_rfx(t2)
                if missing2:
                    back = _apply_rfx_backfill(path, has_bom, t2, missing2, None)
                    if back.get("ok"):
                        r["backfill"] = back
                return r
            return _apply_method_e(path, has_bom, text, os.path.dirname(path), dedup_folder)
        return {"ok": False, "reason": "无标准 SetTexture 窗口，本工具暂不支持此类 mod"}

    # ---- 多 vs 条件行：先试方法 G（形态变量分支），再试双分支格式打标（作者修复版通法）----
    if set_lines or _get_section(text, "CommandListSetTexture"):
        n_cond, _, _ = _vs_cond_count(text)
        if n_cond > 1:
            if _detect_method_g(text, os.path.dirname(path)):
                r = _apply_method_g(path, has_bom, text, wuwa_path, override_path)
                if r["ok"]:
                    return r
            r = _apply_method_b_dual(path, has_bom, text)
            if r["ok"] or "无法区分" in r.get("reason", ""):
                return r
            return {"ok": False,
                    "reason": "双形态/多分支 vs 条件，一键修复会破坏形态切换；需按 AI 提示词从转储更新打标器哈希"}

    # ---- 方法 B：SetTexture 段内有 vs 打标条件（依赖失效打标器）----
    if _window_present(text, "CommandListSetTexture") and has_vs_mark_condition(text):
        return _apply_method_b(path, has_bom, text)

    # ---- 方法 A：RabbitFX 精确窗口 ----
    if not set_lines:
        return {"ok": False, "reason": "无标准 SetTexture 窗口，本工具暂不支持此类 mod"}
    if not rst_lines:
        return {"ok": False, "reason": "有 SetTexture 但无 RestoreTexture，结构异常"}

    folder = os.path.dirname(path)
    res = find_textures(text, folder)
    ini_name = os.path.basename(path)
    if diffuse_res is None or normal_res is None or material_res is None:
        auto_d, auto_n, auto_m = pick_textures(res, ini_name)
        if diffuse_res is None:
            diffuse_res = auto_d
        if normal_res is None:
            normal_res = auto_n
        if material_res is None:
            material_res = auto_m
    if not diffuse_res:
        return {"ok": False, "reason": "未识别到主贴图资源"}
    if diffuse_res not in res:
        return {"ok": False, "reason": "主贴图资源 %s 不存在" % diffuse_res}
    if normal_res is not None and normal_res not in res:
        normal_res = None
    if material_res is not None and material_res not in res:
        material_res = None

    lines = text.splitlines()
    out = []
    i = 0
    n = len(lines)
    set_line_nums = [ln for ln, _ in set_lines]
    rst_line_nums = [ln for ln, _ in rst_lines]
    while i < n:
        if i in set_line_nums:
            indent = [ind for (ln, ind) in set_lines if ln == i][0]
            out.append(lines[i])
            out.append(indent + MARK_DIFFUSE + diffuse_res)
            if normal_res:
                out.append(indent + MARK_NORMAL + normal_res)
            if material_res:
                out.append(indent + MARK_MATERIAL + material_res)
            out.append(indent + RABBIT_SET)
            i += 1
            continue
        if i in rst_line_nums:
            indent = [ind for (ln, ind) in rst_lines if ln == i][0]
            out.append(indent + RABBIT_CLEAR)
            out.append(lines[i])
            i += 1
            continue
        out.append(lines[i])
        i += 1

    text = "\n".join(out)
    text = _ensure_t2_save_restore(text)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path + ".bak_" + ts
    shutil.copy2(path, bak)
    write_text(path, has_bom, text)
    return {"ok": True, "method": "A", "diffuse": diffuse_res,
            "normal": normal_res, "material": material_res, "backup": bak}



def _shared_texture_components(text):
    """从 Resource filename 提取 Components-N-M 标签，按"共享贴图分组"返回：
    {组件: [该组件所属的共享贴图组件集合列表]}。
    例：Components-4-7 t=eb65da67.dds → {4:[{4,7}], 7:[{4,7}]}；
    Components-0-1-2-3-4-5-7（身体大贴图）→ 各组件都有 {0..7} 组。
    补注时选【最小】共享组（如 C7 的 {4,7} 而非 {0..7}）→ 才是鞋子专属贴图参考。"""
    groups = {}
    for m in re.finditer(r"\[ResourceTexture\d+\](.*?)(?=\n\[)", text, re.S):
        body = m.group(1)
        fm = re.search(r"filename\s*=\s*[^\n]*?Components-([\d\-]+)", body, re.I)
        if fm:
            g = frozenset(int(x) for x in fm.group(1).split('-'))
            groups[g] = g
    comp_sets = {}
    for g in groups:
        for c in g:
            comp_sets.setdefault(c, []).append(g)
    return comp_sets


def _injected_component_triplets(text):
    """返回 {组件编号: {Diffuse:.., Normalmap:.., Lightmap:..}} —— 已注入 RabbitFX 的组件"""
    out = {}
    for m in re.finditer(r"\[(TextureOverrideComponent(\d+))\](.*?)(?=\n\[)", text, re.S):
        num = int(m.group(2))
        body = m.group(3)
        if 'RabbitFX' not in body:
            continue
        trip = {}
        for km in re.finditer(r"Resource\\RabbitFX\\(Diffuse|Normalmap|Lightmap)\s*=\s*ref\s+(\S+)", body):
            trip[km.group(1)] = km.group(2)
        if trip:
            out[num] = trip
    return out


def _has_shared_injected(text, comp_name):
    """组件 comp_name 是否与某已注入组件共享贴图（精确匹配）：
    已注入组件实际注入的贴图资源，其 filename 的 Components-N-M 标签包含 comp_name。
    例：C4 注入 Diffuse=ResourceTexture8，filename=Components-4-7 t=eb65da67.dds
    → 7 ∈ {4,7} → C7 算漏注可补；C6 虽与 C0 共享 d2b23835，但 C0 实际注入的不是它
    → 不算漏注（尊重官方 skip_components）"""
    num = int(re.search(r'\d+', comp_name).group())
    injected = _injected_component_triplets(text)
    if not injected:
        return False
    # 资源名 → filename 里的组件标签集（ResourceTexture8 → {4,7}）
    res_comps = {}
    for m in re.finditer(r"\[(ResourceTexture\d+)\](.*?)(?=\n\[)", text, re.S):
        rid = m.group(1)
        body = m.group(2)
        fm = re.search(r"filename\s*=\s*[^\n]*?Components-([\d\-]+)", body, re.I)
        if fm:
            res_comps[rid] = {int(x) for x in fm.group(1).split('-')}
    for _p, trip in injected.items():
        for res in trip.values():
            comps = res_comps.get(res, set())
            if num in comps:
                return True
    return False


def _find_components_without_rfx(text):
    """找【有绘制动作但无 RabbitFX 注入】的 [TextureOverrideComponentN] 段。
    场景：mod 已被稳定纹理工具（RabbitFX）修过，大部分组件注入了 SetTextures，
    但个别组件（如鞋子 Component7）漏注 → 该部件纹理仍错。返回段名列表。
    排除：组件段内已有 RabbitFX、或走换贴图窗口（含 CommandListSetTexture/
    RestoreTexture 引用，如方法 A 修过的 mod）——这些不算漏注。"""
    # 单窗口注入（方法 A 修复版，如绯雪/莫宁：只挂身体 SetTexture 窗口）→ 其他组件
    # 本就无需注入，不判漏注；仅当 SetTextures 引用 >=2（稳定纹理工具逐组件注入）
    # 才存在"个别组件漏注"的可能（尤诺 case）。
    n_set = len(re.findall(r"run\s*=\s*Commandl(?:ist|ist)\\RabbitFX\\SetTextures", text, re.I))
    if n_set < 2:
        return []
    missing = []
    for m in re.finditer(r"^\[(TextureOverrideComponent\d+)\]\s*$", text, re.M):
        comp = m.group(1)
        rest = text[m.end():]
        nxt = re.search(r"^\[", rest, re.M)
        body = rest[:nxt.start()] if nxt else rest
        has_draw = ("drawindexed" in body or "handling = skip" in body
                    or "CheckTextureOverride" in body)
        if not has_draw:
            continue
        if "RabbitFX" in body:
            continue
        # 组件段走换贴图窗口（SetTexture/Restore 由 CommandList 管）→ 不算漏注
        if "CommandListSetTexture" in body or "CommandListRestoreTexture" in body:
            continue
        # 组件段含窗口结构（if $mod_enabled / if $object_detected）→ 作者原生窗口型
        # mod（如 Nait3D 的 Hiyuki：作者只给部分组件配 RabbitFX，未配是设计如此，
        # 不是漏注），默认排除——补全会把错误贴图灌进组件导致纹理混乱。
        # 例外（方法 D2）：贴图文件名标签 Components-N-M 显示该组件与已注入组件
        # 共享贴图（如 iuno_maid_mk3 的 C7 与 C4 共用 Components-4-7）→ 是注入遗漏，
        # 纳入补注，复用共享组件的三件套
        if re.search(r"^\s*if\s+\$mod_enabled\b", body, re.M) or \
           re.search(r"^\s*if\s+\$object_detected\b", body, re.M):
            if not _has_shared_injected(text, comp):
                continue
        missing.append(comp)
    return missing


def _find_rfx_triplet(text):
    """从已注入 RabbitFX 的段提取贴图三件套（Diffuse/Normalmap/Lightmap）。
    优先返回三件套齐全的一组（如 Component4 的 8/21/22），否则返回任一组。"""
    combos = []
    cur = {}
    for m in re.finditer(
            r"Resource\\RabbitFX\\(Diffuse|Normalmap|Lightmap)\s*=\s*ref\s+(\S+)", text):
        cur[m.group(1)] = m.group(2)
        if len(cur) >= 3:
            combos.append(dict(cur))
    if combos:
        return combos[-1]
    return {}


def _inject_rfx_to_component(text, comp_name, triplet):
    """在组件段内 drawindexed 行前注入 RabbitFX 三件套 + SetTextures（漏注补全）"""
    lines = text.splitlines()
    out = []
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        if ln.strip() == "[" + comp_name + "]":
            out.append(ln)
            i += 1
            seg = []
            while i < n and not re.match(r"^\[", lines[i].strip()):
                seg.append(lines[i])
                i += 1
            di = None
            for k, sln in enumerate(seg):
                if re.search(r"drawindexed\s*=", sln):
                    di = k
                    break
            has_rfx = any("RabbitFX" in sln for sln in seg)
            if di is None or has_rfx:
                out.extend(seg)
                continue
            indent = "    "
            for sln in seg:
                if sln.strip():
                    indent = sln[:len(sln) - len(sln.lstrip())]
                    break
            ins = []
            if "Diffuse" in triplet:
                ins.append(indent + "if $object_detected")
                ins.append(indent + "    Resource\\RabbitFX\\Diffuse = ref " + triplet["Diffuse"])
                for key in ("Normalmap", "Lightmap"):
                    if key in triplet:
                        ins.append(indent + "    Resource\\RabbitFX\\" + key + " = ref " + triplet[key])
                ins.append(indent + "endif")
                ins.append(indent + "run = Commandlist\\RabbitFX\\SetTextures")
            elif triplet:
                first = next(iter(triplet.values()))
                ins.append(indent + "Resource\\RabbitFX\\Diffuse = ref " + first)
                ins.append(indent + "run = Commandlist\\RabbitFX\\SetTextures")
            out.extend(seg[:di])
            out.extend(ins)
            out.extend(seg[di:])
            continue
        out.append(ln)
        i += 1
    return "\n".join(out)


def _apply_rfx_backfill(path, has_bom, text, missing, triplet=None):
    """方法 RFX 补全（含方法 D2 共享补注）：给漏注组件补 RabbitFX 三件套。
    三件套来源优先级：① 共享贴图组件（Components-N-M 标签，方法 D2 通法）
    → ② 传入的 triplet（调用方指定）→ ③ 任意已注入组件的三件套"""
    injected = _injected_component_triplets(text)
    share = _shared_texture_components(text)
    last = {}
    for comp in missing:
        tt = triplet
        if not tt:
            num = int(re.search(r'\d+', comp).group())
            # 最小共享组优先（鞋子专属贴图 Components-4-7 比身体大贴图 Components-0..7 更准）
            for g in sorted(share.get(num, []), key=len):
                for p in sorted(g, reverse=True):
                    if p != num and p in injected and len(injected[p]) >= 2:
                        tt = injected[p]
                        break
                if tt:
                    break
        if not tt:
            tt = _find_rfx_triplet(text)
        if not tt:
            return {"ok": False, "reason": "无已注入组件的贴图可参考"}
        text = _inject_rfx_to_component(text, comp, tt)
        last = tt
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path + ".bak_" + ts
    shutil.copy2(path, bak)
    write_text(path, has_bom, text)
    return {"ok": True, "method": "RFX补全", "diffuse": last.get("Diffuse", ""),
            "normal": last.get("Normalmap", ""), "material": last.get("Lightmap", ""),
            "backup": bak, "components": missing}




# ================= 方法 E：贴图挂钩型 mod（[TextureOverrideTextureN] hash+this）=================
# 游戏更新后游戏贴图哈希变了 → 挂钩失效 → mod 贴图永不替换 → 纹理乱。
# 修复：读最新转储 deduped\ 里游戏当前贴图，与 mod 自带贴图（旧游戏快照）做内容相似匹配，
# 自动把 hash 更新为内容最相似的新贴图哈希。
E_MARK = "; [E-repaired by ModRepairTool]"

# ================= 方法 F：社区配置修复（Moonholder/Wuwa_Mod_Fixer 数据源）=================
# 背景：方法 E 的自动内容匹配（32x32 亮度相似度）对漫反射可靠，但法线/材质/大尺寸图相似度天然低，
# 且曾出现匹配错（b399ecff 错配 a60c5c6e，社区人眼标注应为 5315f443）→ 纹理仍乱。
# 决定性的修复来自 Moonholder 的 Wuwa_Mod_Fixer 社区维护 config.json：
#   社区按角色人眼标注「旧哈希→新哈希」映射（游戏更新后的准确值）+ 每组件贴图语义（D/N/L）。
# 本工具内置已验证角色（Iuno 尤诺），并支持外部 community_config.json 扩展（工具目录/工作目录）。
# 修复：hash_replace（社区映射旧→新）→ 稳定纹理注入（handling=skip 后 + 语义三件套 + SetTextures）。
F_MARK = "; [F-repaired by ModRepairTool]"

# ===== 数据源设计（版权合规）=====
# 本工具【不内置】任何来自 Wuwa_Mod_Fixer 的 config.json 数据（该项目为 GPL-3.0）。
# 方法 F 的数据完全来自【用户自行选择/下载的官方 config.json】，工具运行时解析其结构
# （characters.<角色>.main_hashes / textures.<旧hash>.{meta{id,type}, replace[]}）。
# 工具目录 community_config.json 只是【用户自己的实战修正层】：
#   - semantic_swaps：组件语义 N/L 对调（本工具实战发现，如 Iuno C3 与社区标注相反）
#   - hash_extra：用户自己确认的额外哈希修正
# 修正层为纯逻辑/自研发现，不包含他人版权内容。

_type_key = {"D": "Diffuse", "N": "Normalmap", "L": "Lightmap", "M": "Materialmap", "C": "Cutoutmap", "S": "Specialmap"}


def _parse_wuwa_config(data):
    """解析 Wuwa_Mod_Fixer 官方 config.json → 内部格式 {角色: {match, hash_replace, semantics}}
    官方结构：characters.<角色> = {main_hashes:[{old:[...], new}],
              textures:{<新hash>: {meta:{id, type}, replace:[旧hash,...]}}}
    注意方向（实测）：textures 的 **key = 游戏当前新 hash**，replace[0] = mod 里挂钩的旧 hash，
    所以 hash_replace = replace[0](旧) → key(新)；semantics 也以 replace[0](旧) 为值（供反查挂钩段 this）。
    skip_components：官方标注的免注入组件（如 Iuno=[6]），解析后并入 cfg["skip_components"]。
    """
    out = {}
    chars = data.get("characters") if isinstance(data, dict) else None
    if not isinstance(chars, dict):
        chars = data if isinstance(data, dict) else {}
    for name, cc in chars.items():
        if not isinstance(cc, dict):
            continue
        match = []
        for rep in cc.get("main_hashes") or []:
            if isinstance(rep, dict):
                for old in rep.get("old") or []:
                    match.append(str(old).lower())
        hash_replace = {}
        semantics = {}
        for new_h, tn in (cc.get("textures") or {}).items():
            if not isinstance(tn, dict):
                continue
            new_h = str(new_h).lower()
            reps = tn.get("replace") or []
            if reps:
                hash_replace[str(reps[0]).lower()] = new_h  # 旧→新
            meta = tn.get("meta")
            if isinstance(meta, dict):
                ids = meta.get("id")
                ids = ids if isinstance(ids, list) else ([ids] if ids is not None else [])
                typ = str(meta.get("type", "")).upper()
                old_h = str(reps[0]).lower() if reps else new_h
                for cid in ids:
                    semantics.setdefault(str(cid), {})[typ] = old_h
        skip = [str(x) for x in (cc.get("skip_components") or [])]
        if match or hash_replace or semantics or skip:
            out[name] = {"match": match, "hash_replace": hash_replace,
                         "semantics": semantics, "skip_components": skip}
    return out


def _apply_overrides(cfg, overrides):
    """应用用户修正层（纯逻辑/自研，不包含他人数据）：
    semantic_swaps: {角色: {组件: {A: B}}} → 组件内类型 A/B 互换（如 Iuno C3 的 N/L 与社区标注相反）
    hash_extra: {角色: {旧hash: 新hash}} → 追加哈希映射
    """
    if not isinstance(overrides, dict):
        return cfg
    for name, swaps in (overrides.get("semantic_swaps") or {}).items():
        if name not in cfg or not isinstance(swaps, dict):
            continue
        sem = cfg[name].get("semantics", {})
        for comp, typ_map in swaps.items():
            if comp not in sem:
                continue
            if isinstance(typ_map, list) and len(typ_map) >= 2:
                a, b = typ_map[0], typ_map[1]
                va, vb = sem[comp].get(a), sem[comp].get(b)
                if va and vb:
                    sem[comp][a], sem[comp][b] = vb, va
            elif isinstance(typ_map, dict) and typ_map:
                a, b = next(iter(typ_map.items()))
                va, vb = sem[comp].get(a), sem[comp].get(b)
                if va and vb:
                    sem[comp][a], sem[comp][b] = vb, va
                elif va:
                    sem[comp][b] = va
                    sem[comp].pop(a, None)
    for name, reps in (overrides.get("hash_extra") or {}).items():
        if name not in cfg or not isinstance(reps, dict):
            continue
        for old, new in reps.items():
            cfg[name]["hash_replace"][str(old).lower()] = str(new).lower()
    for name, skip in (overrides.get("skip_components") or {}).items():
        if name not in cfg or not isinstance(skip, list):
            continue
        cur = cfg[name].setdefault("skip_components", [])
        for c in skip:
            s = str(c)
            if s not in cur:
                cur.append(s)
    return cfg


def _load_overrides(override_path=None):
    """读用户通过 UI 选择的 community_config.json（实战修正层，不内置任何数据）。
    版权合规：工具不内嵌任何社区/修正数据；用户自行选择配置文件，未选择则返回空。"""
    import json
    if override_path and os.path.isfile(override_path):
        try:
            with open(override_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _load_community_config(wuwa_path=None, override_path=None):
    """加载方法 F 数据（版权合规：不内置任何他人数据）：
    - 官方数据：用户通过 UI 选择的 Wuwa_Mod_Fixer config.json（wuwa_path）
    - 修正层：用户通过 UI 选择的 community_config.json（override_path，不内置）
    返回内部格式 {角色: {...}}；无官方数据返回空 dict（方法 F 不可用，退方法 E）。"""
    import json
    cfg = {}
    if wuwa_path and os.path.isfile(wuwa_path):
        try:
            with open(wuwa_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = _parse_wuwa_config(data)
        except Exception:
            cfg = {}
    overrides = _load_overrides(override_path)
    return _apply_overrides(cfg, overrides)


def _hashes_all_current(text, cfg):
    """社区 hash_replace 的旧值是否一个都不在文本中（全部已是最新哈希）。"""
    repl = cfg.get("hash_replace") or {}
    tl = text.lower()
    for old in repl:
        if old.lower() in tl:
            return False
    return True


def _match_character(text, config):
    """按组件网格 hash 匹配社区配置角色，返回 (角色名, 配置) 或 None"""
    mesh_hashes = set()
    for m in re.finditer(r"^\[TextureOverrideComponent\d+\]\s*$", text, re.M):
        rest = text[m.end():]
        nxt = re.search(r"^\[", rest, re.M)
        body = rest[:nxt.start()] if nxt else rest
        hm = re.search(r"^\s*hash\s*=\s*([0-9a-fA-F]{8})", body, re.M)
        if hm:
            mesh_hashes.add(hm.group(1).lower())
    for name, cfg in config.items():
        for h in cfg.get("match", []):
            if h.lower() in mesh_hashes:
                return name, cfg
    return None


def _hash_to_this(text):
    """挂钩段 hash→this 映射（TextureOverrideTextureN）"""
    out = {}
    for m in re.finditer(r"^\[TextureOverrideTexture\d+\]\s*$", text, re.M):
        rest = text[m.end():]
        nxt = re.search(r"^\[", rest, re.M)
        body = rest[:nxt.start()] if nxt else rest
        hm = re.search(r"^\s*hash\s*=\s*([0-9a-fA-F]{8})", body, re.M)
        tm = re.search(r"^\s*this\s*=\s*(Resource\S+)", body, re.M)
        if hm and tm:
            out[hm.group(1).lower()] = tm.group(1)
    return out


def _apply_method_f(path, has_bom, text, folder, wuwa_path=None, override_path=None):
    """方法 F：社区配置 hash_replace + 稳定纹理注入。
    1) 按组件网格 hash 匹配角色（社区配置）
    2) hash_replace：所有 `hash = xxx` 行按社区映射旧→新
    3) 稳定纹理注入：按社区语义（组件→类型→旧hash→this 资源）→ handling=skip 后三件套 + SetTextures
    4) 备份 + 写回（F_MARK 幂等标记）"""
    config = _load_community_config(wuwa_path, override_path)
    matched = _match_character(text, config)
    if not matched:
        return {"ok": False, "reason": "未匹配到社区配置角色：请在界面选择 Wuwa_Mod_Fixer 的 config.json，或向 community_config.json 修正层补充"}
    name, cfg = matched
    if not cfg.get("hash_replace") and not cfg.get("semantics"):
        return {"ok": False, "reason": "社区配置无可用修复数据"}
    # 哈希全部已是最新（作者原生完整 mod，如 Nait3D 的 Hiyuki）→ 无需修复，
    # 绝不重复注入（会把错误贴图灌进组件导致纹理混乱）
    if _hashes_all_current(text, cfg):
        return {"ok": False, "reason": "哈希已是最新，本 mod 无需修复"}

    lines = text.splitlines()

    # ---- ① hash_replace（社区映射旧→新）----
    # 注意：先在替换前构建 hash→this（原 hash），供语义注入反查 this 资源
    hash2this = _hash_to_this(text)
    repl = cfg.get("hash_replace", {})
    repl_lower = {k.lower(): v for k, v in repl.items()}
    n_rep = 0
    for i, ln in enumerate(lines):
        m = re.match(r"^(\s*)hash\s*=\s*([0-9a-fA-F]{8})\s*$", ln)
        if m and m.group(2).lower() in repl_lower:
            lines[i] = m.group(1) + "hash = " + repl_lower[m.group(2).lower()]
            n_rep += 1

    # ---- ② 稳定纹理注入 ----
    text2 = "\n".join(lines)
    # 语义用配置的旧 hash（映射表）在替换前构建的 hash2this 中查 this 资源
    skip_comps = set(cfg.get("skip_components") or [])
    comp_res = {}
    for comp, typ_map in cfg.get("semantics", {}).items():
        if comp in skip_comps:
            continue  # 官方/用户标注的免注入组件
        for typ, old_hash in typ_map.items():
            res = hash2this.get(old_hash.lower())
            if res:
                comp_res.setdefault(comp, {})[_type_key.get(typ, typ)] = res
    if not comp_res:
        return {"ok": False, "reason": "社区语义无法定位贴图资源（挂钩段结构不符）", "hash_replaced": n_rep}

    modified = False
    out_lines = []
    i = 0
    n = len(lines)
    while i < n:
        m = re.match(r"^\[(TextureOverrideComponent\d+)\]\s*$", lines[i].strip())
        if m:
            comp = m.group(1).replace("TextureOverrideComponent", "")
            out_lines.append(lines[i])
            i += 1
            seg = []
            while i < n and not re.match(r"^\[", lines[i].strip()):
                seg.append(lines[i])
                i += 1
            if comp in comp_res:
                dm = None
                for k, sln in enumerate(seg):
                    if re.search(r"handling\s*=\s*skip", sln):
                        dm = k
                        break
                if dm is not None:
                    indent = "    "
                    for sln in seg:
                        if sln.strip():
                            indent = sln[:len(sln) - len(sln.lstrip())]
                            break
                    triple = comp_res[comp]
                    block = ["", indent + "if $object_detected"]
                    for typ in ("Diffuse", "Normalmap", "Lightmap", "Materialmap"):
                        if typ in triple:
                            block.append(indent + "    Resource\\RabbitFX\\%s = ref %s" % (typ, triple[typ]))
                    block.append(indent + "endif")
                    block.append(indent + "run = Commandlist\\RabbitFX\\SetTextures")
                    seg[dm:dm + 1] = [seg[dm]] + block
                    modified = True
            out_lines.extend(seg)
            continue
        out_lines.append(lines[i])
        i += 1

    text = "\n".join(out_lines)
    if F_MARK not in text:
        text = F_MARK + "\n" + text

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path + ".bak_" + ts
    shutil.copy2(path, bak)
    write_text(path, has_bom, text)
    return {"ok": True, "method": "F(社区配置)", "character": name,
            "hash_replaced": n_rep, "components": list(comp_res.keys()), "backup": bak}



def _detect_method_h(text):
    """方法 H 适用（Nait3D-Hiyuki/PathOfTheShura 案例通法）：
    组件窗口（[TextureOverrideComponentN]）内贴图绑定分支只写 $var == -1 / == 1，
    但 [Constants] 里 global persist $var = 0（三态 toggle 默认态 0）-> switch=0 时
    所有绑定分支都不执行 -> 组件用原版贴图配 mod 网格 -> 纹理乱。
    返回需兜底的变量名；无则 None。"""
    comp_bodies = {}
    for m in re.finditer(r"^\[(TextureOverrideComponent\d+)\]\s*$", text, re.M):
        comp = m.group(1)
        rest = text[m.end():]
        nxt = re.search(r"^\[", rest, re.M)
        body = rest[:nxt.start()] if nxt else rest
        if "ps-t" in body:
            comp_bodies[comp] = body
    if not comp_bodies:
        return None
    vars_needing = {}
    for _c, body in comp_bodies.items():
        for mm in re.finditer(r"(?:if|elif)\b[^\n]*?\$(\w+)\s*==\s*-1", body):
            v = mm.group(1)
            vars_needing[v] = vars_needing.get(v, 0) + 1
    if not vars_needing:
        return None
    constants = "\n".join(_get_section(text, "Constants") or [])
    default_zero = set()
    for mm in re.finditer(r"global\s+persist\s+\$(\w+)\s*=\s*0\b", constants):
        default_zero.add(mm.group(1))
    if not default_zero:
        return None
    all_body = "\n".join(comp_bodies.values())
    for v, _cnt in sorted(vars_needing.items(), key=lambda x: -x[1]):
        if v not in default_zero:
            continue
        # 组件段内已有 0 态兜底（== 0 / <= 0 / >= 0 / != 1）→ 默认态有绑定，无需修复
        if re.search(r"\$" + v + r"\s*(?:==|<=|>=)\s*0\b", all_body):
            continue
        if re.search(r"\$" + v + r"\s*!=\s*1\b", all_body):
            continue
        return v
    return None


def _apply_method_h(path, has_bom, text, var):
    """方法 H：组件窗口内 $var == -1 -> $var <= 0（补默认态兜底，与作者 LOD 段写法一致），
    加 F_MARK。只改 [TextureOverrideComponentN] 段；贴图挂钩段/LOD 段保持作者原样。"""
    lines = text.splitlines()
    pat = re.compile(r"\$" + var + r"\s*==\s*-1")
    in_comp = False
    out = []
    n = 0
    for ln in lines:
        s = ln.strip()
        if re.match(r"^\[TextureOverrideComponent\d+\]\s*$", s):
            in_comp = True
        elif s.startswith("["):
            in_comp = False
        if in_comp and pat.search(ln):
            out.append(pat.sub("$" + var + " <= 0", ln))
            n += 1
        else:
            out.append(ln)
    if not n:
        return {"ok": False, "reason": "未找到需兜底的条件分支"}
    nl = "\r\n" if "\r\n" in text else "\n"
    text2 = nl.join(out)
    mark = F_MARK + " switch 默认态兜底\n"
    if mark not in text2:
        text2 = mark + text2
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path + ".bak_" + ts
    shutil.copy2(path, bak)
    write_text(path, has_bom, text2)
    return {"ok": True, "method": "H", "var": var, "changed": n, "backup": bak}


def _find_texture_overrides(text):
    """找 [TextureOverrideTextureN] 及 [TextureOverrideTextureNLODx] 段：hash + this 引用，
    返回 [(段名, hash行号, hash值, this资源)]。LOD 段与主挂钩一起参与匹配更新。"""
    out = []
    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        m = re.match(r"^\[(TextureOverrideTexture\d+(?:LOD\d+)?)\]\s*$", lines[i].strip())
        if m:
            seg_name = m.group(1)
            seg = []
            j = i + 1
            while j < n and not re.match(r"^\[", lines[j].strip()):
                seg.append((j, lines[j]))
                j += 1
            h = None
            this = None
            for (ln_no, ln) in seg:
                mm = re.match(r"^\s*hash\s*=\s*([0-9a-fA-F]{8})\s*$", ln)
                if mm:
                    h = (ln_no, mm.group(1))
                mm2 = re.match(r"^\s*this\s*=\s*(Resource\S+)", ln)
                if mm2 and this is None:
                    this = mm2.group(1)
            if h and this:
                out.append((seg_name, h[0], h[1], this))
            i = j
        else:
            i += 1
    return out


def _find_dedup_folder(folder):
    """从任意深度向上找最近的含 FrameAnalysis-*deduped 的目录（支持多层嵌套 mod 结构）"""
    parent = os.path.dirname(folder)
    while True:
        best = None
        if os.path.isdir(parent):
            try:
                entries = os.listdir(parent)
            except OSError:
                entries = []
            for d in entries:
                if d.startswith("FrameAnalysis-"):
                    dd = os.path.join(parent, d, "deduped")
                    if os.path.isdir(dd):
                        if best is None or d > best[0]:
                            best = (d, dd)
            if best:
                return best[1]
        up = os.path.dirname(parent)
        if up == parent:
            return None
        parent = up


def _find_all_dedup_folders(folder, extra=None):
    """从任意深度向上找所有含 FrameAnalysis-*deduped 的目录（多形态/多转储交叉验证用）
    extra：用户显式指定的 FrameAnalysis 文件夹（含 deduped 子目录），优先并入。"""
    parents = []
    parent = os.path.dirname(folder)
    while True:
        if os.path.isdir(parent):
            try:
                entries = os.listdir(parent)
            except OSError:
                entries = []
            for d in entries:
                if d.startswith("FrameAnalysis-"):
                    dd = os.path.join(parent, d, "deduped")
                    if os.path.isdir(dd):
                        parents.append(dd)
        up = os.path.dirname(parent)
        if up == parent:
            break
        parent = up
    if extra:
        # 兼容用户选 FrameAnalysis 文件夹或直接选 deduped 子目录
        cand = extra.rstrip("\\/")
        if os.path.basename(cand) == "deduped":
            if os.path.isdir(cand):
                parents.insert(0, cand)
        else:
            dd = os.path.join(cand, "deduped")
            if os.path.isdir(dd):
                parents.insert(0, dd)
    seen = set()
    uniq = []
    for dd in parents:
        if dd not in seen:
            seen.add(dd)
            uniq.append(dd)
    return uniq



_DDS_CACHE = {}


def _thumb_dds(path, size=32):
    """读取贴图 → 32x32 亮度缩略（缓存）"""
    if path in _DDS_CACHE:
        return _DDS_CACHE[path]
    try:
        import imageio.v3 as iio
        a = np.asarray(iio.imread(path))
    except Exception:
        _DDS_CACHE[path] = None
        return None
    if a.ndim == 3:
        a = a[..., :3]
    h, w = a.shape[:2]
    ys = np.linspace(0, h - 1, size, dtype=int)
    xs = np.linspace(0, w - 1, size, dtype=int)
    t = a[np.ix_(ys, xs)].astype(np.float32)
    _DDS_CACHE[path] = t
    return t


def _dds_size(path):
    try:
        with open(path, "rb") as f:
            head = f.read(20)
        if head[:4] != b"DDS ":
            return None
        return struct.unpack("<II", head[12:20])
    except Exception:
        return None


def _sim(t1, t2):
    if t1 is None or t2 is None or t1.shape != t2.shape:
        return -1.0
    m1, m2 = t1.mean(), t2.mean()
    return 1.0 - np.abs((t1 - m1) - (t2 - m2)).mean() / 255.0


def _collect_dedup_textures(dedup):
    """deduped 里所有贴图（按哈希-格式 文件名），缓存缩略图"""
    c = []
    if not dedup or not os.path.isdir(dedup):
        return c
    for f in os.listdir(dedup):
        if f.lower().endswith((".dds", ".jpg", ".png")):
            h8 = f[:8]
            if len(h8) == 8 and all(ch in "0123456789abcdef" for ch in h8):
                fp = os.path.join(dedup, f)
                t = _thumb_dds(fp)
                if t is not None:
                    c.append((h8, fp, t, _dds_size(fp)))
    return c


def _match_new_hash(tex_path, dedup_textures, thr=0.86):
    """内容相似匹配：返回 (新哈希, 相似度, 匹配文件) 或 None。
    不做尺寸过滤——游戏更新可能改贴图尺寸（高清化），内容仍是同一张贴图。"""
    t1 = _thumb_dds(tex_path)
    if t1 is None:
        return None
    best = None
    for h8, fp, t2, sz in dedup_textures:
        sc = _sim(t1, t2)
        if sc >= thr and (best is None or sc > best[1]):
            best = (h8, sc, fp)
    return best


def _apply_method_e(path, has_bom, text, folder, dedup_folder=None):
    """方法 E（贴图挂钩型通法，Radiant Hiyuki/shiroho 案例升级）：
    更新所有失效贴图挂钩的 hash（内容相似匹配）。
    - 匹配池 = 【全部可用转储】的并集（多形态/多转储交叉验证），取相似度最高匹配
      → 避免单一转储把内容相似的不同形态贴图误匹配到同一哈希（Texture6 曾被误改成 Ice 形态哈希）
    - 挂钩段含 LOD 段（TextureOverrideTextureNLODx）：LOD 段与主挂钩一起参与匹配更新
      → 游戏近景走 LOD0 挂钩，LOD 哈希失效会导致切换功能不生效（恶魔脸案例）"""
    oves = _find_texture_overrides(text)
    if not oves:
        return {"ok": False, "reason": "未找到贴图挂钩段"}
    dedups = _find_all_dedup_folders(folder, dedup_folder)
    if not dedups:
        return {"ok": False, "reason": "未找到转储 deduped 目录（需 F8 转储）"}
    res = find_textures(text, folder)
    # 全部转储并集匹配池（同一哈希在不同转储重复 → 去重保留一个）
    pool = []
    seen_h = set()
    for dd in dedups:
        for h8, fp, t, sz in _collect_dedup_textures(dd):
            if h8 not in seen_h:
                seen_h.add(h8)
                pool.append((h8, fp, t, sz))
    if not pool:
        return {"ok": False, "reason": "deduped 目录无贴图可对比"}

    updated = []
    lines = text.splitlines()
    valid_hashes = set(h8 for h8, _fp, _t, _sz in pool)
    for seg_name, ln_no, old_hash, this in oves:
        if old_hash.lower() in valid_hashes:
            continue  # 旧哈希仍在转储（游戏当前在用）→ 有效，跳过，防止误改
        tex_path = res.get(this)
        if not tex_path or not os.path.exists(tex_path):
            continue
        mt = _match_new_hash(tex_path, pool, thr=0.90)
        if mt:
            new_hash, sc, mf = mt
            if new_hash.lower() != old_hash.lower():
                lines[ln_no] = re.sub(r"hash\s*=\s*[0-9a-fA-F]{8}",
                                      "hash = " + new_hash, lines[ln_no])
                updated.append((seg_name, old_hash, new_hash, sc))
    if not updated:
        return {"ok": False, "reason": "所有挂钩已匹配/无失效（或相似度不足，需AI）"}

    text = "\n".join(lines)
    if E_MARK not in text:
        text = E_MARK + "\n" + text

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path + ".bak_" + ts
    shutil.copy2(path, bak)
    write_text(path, has_bom, text)
    return {"ok": True, "method": "E(贴图哈希更新)", "diffuse": "",
            "backup": bak,
            "updated": ["%s: %s->%s (%.2f)" % (a, b, c, d) for a, b, c, d in updated]}


def _scan_inis(root):
    """递归收集 mod 目录下所有 .ini（含子文件夹；排除 .bak 备份），返回 [(显示路径, 绝对路径)]"""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for f in sorted(filenames):
            if f.lower().endswith(".ini") and ".bak_" not in f.lower():
                abs_p = os.path.join(dirpath, f)
                rel = os.path.relpath(abs_p, root)
                out.append((rel, abs_p))
    return sorted(out, key=lambda x: x[0].lower())


def _window_present(text, name):
    """判定贴图窗口是否存在：TextureOverride 里有 run = CommandListSetTexture 引用，
    或文件直接定义了 [CommandListSetTexture] 段（如洛瑟拉把贴图逻辑集中定义在 ui.ini）。"""
    if find_run_lines(text, name):
        return True
    return _get_section(text, name) is not None


def analyze_folder(folder, wuwa_path=None, override_path=None):
    """分析一个 mod 文件夹（递归子目录，支持多形态 mod），返回 ini 状态列表"""
    if not os.path.isdir(folder):
        return {"error": "文件夹不存在"}
    inis = _scan_inis(folder)
    items = []
    for rel, p in inis:
        has_bom, text = read_text(p)
        if is_repaired(text):
            # 误判防护：原版内置 RabbitFX 仍可能缺 toggle 默认态兜底 → 可修复(H)
            h_var = _detect_method_h(text)
            if h_var:
                state = "可修复(H)"
                diffuse_hint = ""
            elif RABBIT_SET in text and not _window_present(text, "CommandListSetTexture"):
                # RabbitFX 管道修过（无窗口组件挂钩型）：若存在漏注组件 → 可补全（尤诺女仆案例手法）
                missing = _find_components_without_rfx(text)
                if missing:
                    triplet = _find_rfx_triplet(text)
                    state = "可修复(RFX)"
                    diffuse_hint = triplet.get("Diffuse", "")
                else:
                    state = "已修复"
                    diffuse_hint = ""
            else:
                # 窗口型修复（方法 A/G 等，窗口内统一注入）或方法 B 修复版 → 已修复
                state = "已修复"
                diffuse_hint = ""
        else:
            set_lines = find_run_lines(text, "CommandListSetTexture")
            rst_lines = find_run_lines(text, "CommandListRestoreTexture")
            if not (_window_present(text, "CommandListSetTexture") and _window_present(text, "CommandListRestoreTexture")):
                h_var = _detect_method_h(text)
                if h_var:
                    state = "可修复(H)"  # 三态 toggle 默认态兜底（Nait3D-Hiyuki 通法）
                    diffuse_hint = ""
                elif _find_texture_overrides(text):
                    # 贴图挂钩型：TextureOverrideTextureN（hash+this）→ 方法 F（社区配置）优先 / E（自动匹配）兜底
                    config = _load_community_config(wuwa_path, override_path)
                    matched = _match_character(text, config)
                    if matched:
                        # 哈希全部已是最新 → 无需修复（避免对作者原生完整 mod 误判/重复注入）
                        if _hashes_all_current(text, matched[1]):
                            state = "无需修复"
                        else:
                            state = "可修复(F)"
                    else:
                        state = "可修复(E)"
                    diffuse_hint = ""
                else:
                    state = "不支持"
                    diffuse_hint = ""
            else:
                n_cond, _, _ = _vs_cond_count(text)
                if n_cond > 1:
                    if _detect_method_g(text, folder):
                        state = "可修复(G)"  # 形态变量分支（绯雪/Hiyuki 通法）
                        diffuse_hint = ""
                    else:
                        body = _get_section(text, "CommandListSetTexture")
                        info = _branch_main_slots(body)
                        slots = [x[2] for x in info if x[2]]
                        if len(info) >= 2 and all(x[2] for x in info) and len(set(x[2][0] for x in info)) >= 2:
                            state = "可修复(B2)"  # 双分支：各分支不同槽位打标，作者通法
                            diffuse_hint = ""
                        else:
                            state = "双形态(需AI)"  # 多分支无法区分：需转储直改哈希
                            diffuse_hint = ""
                elif has_vs_mark_condition(text):
                    state = "可修复(B)"  # 方法 B：单 vs 条件 → 作者式修复
                    diffuse_hint = ""
                else:
                    res = find_textures(text, os.path.dirname(p))
                    diffuse, _ = pick_diffuse_normal(res, rel)
                    state = "可修复(A)" if diffuse else "缺主贴图"
                    diffuse_hint = diffuse or ""
        items.append({"file": rel, "path": p, "state": state, "diffuse": diffuse_hint})
    return {"inis": items}
