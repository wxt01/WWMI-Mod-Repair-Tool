# -*- coding: utf-8 -*-
"""备份记录管理：记录每次修复，支持单条回滚与一键回滚全部"""
import os
import json
import shutil
import datetime
import uuid

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ModRepairTool")
HISTORY_FILE = os.path.join(APP_DIR, "history.json")


def _ensure():
    os.makedirs(APP_DIR, exist_ok=True)


def load_history():
    _ensure()
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(records):
    _ensure()
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def add_record(folder, inis, diffuse):
    """inis: [{'path':..., 'backup':...}]"""
    rec = {
        "id": uuid.uuid4().hex[:12],
        "folder": folder,
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "diffuse": diffuse,
        "inis": inis,
        "rolled_back": False,
    }
    records = load_history()
    records.insert(0, rec)
    save_history(records)
    return rec


def rollback_record(rec_id):
    records = load_history()
    for rec in records:
        if rec["id"] == rec_id:
            errors = []
            for item in rec.get("inis", []):
                bak = item.get("backup")
                dst = item.get("path")
                if bak and os.path.exists(bak):
                    try:
                        shutil.copy2(bak, dst)
                    except Exception as e:
                        errors.append(str(e))
                elif not bak:
                    errors.append("缺少备份路径")
            if not errors:
                rec["rolled_back"] = True
                save_history(records)
                return {"ok": True, "msg": "已回滚"}
            return {"ok": False, "msg": "部分失败: " + "; ".join(errors)}
    return {"ok": False, "msg": "记录不存在"}


def rollback_all():
    records = load_history()
    total, failed = 0, 0
    for rec in records:
        if rec.get("rolled_back"):
            continue
        r = rollback_record(rec["id"])
        total += 1
        if not r["ok"]:
            failed += 1
    return {"ok": failed == 0, "total": total, "failed": failed}

def clear_all():
    """一键清除全部备份记录（不删除备份文件本体）"""
    _ensure()
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
    return {"ok": True, "msg": "已清除全部记录"}

