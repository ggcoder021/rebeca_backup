#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import io
import sys
import json
import time
import math
import fcntl
import sqlite3
import zipfile
import signal
import shutil
import hashlib
import logging
import tempfile
import threading
import subprocess
from datetime import datetime
from urllib import request, parse
from urllib.error import URLError, HTTPError

# =========================
# Rebeca Backup Bot
# @GGCODER_IR
# =========================

APP_NAME = "بکاپر ربکا"
APP_TAG = "@GGCODER_IR"
CAPTION_FOOTER = "ggcoder_ir@"

BASE_DIR = "/opt/rebeca-backup"
CONFIG_PATH = "/etc/rebeca_backup.json"
DB_PATH = "/var/lib/rebeca_backup.db"
WORK_DIR = "/var/lib/rebeca_backup"
TMP_DIR = os.path.join(WORK_DIR, "tmp")
LOG_FILE = "/var/log/rebeca_backup.log"
LOCK_FILE = "/var/lock/rebeca_backup.lock"

MENU_CMD_NAME = "ggbackup"

DEFAULT_CONFIG = {
    "bot_token": "",
    "admin_id": 0,                 # فقط این آیدی مجاز است
    "backup_paths": ["/etc", "/root"],
    "schedule": "03:30",           # HH:MM
    "enabled": True,
    "part_size_mb": 45,            # پارت‌بندی امن برای تلگرام
    "send_mode": "auto",           # auto | single | force_split
    "keep_local_days": 0,          # 0 یعنی حذف فوری موقت‌ها
    "panel_poll_interval": 2,
    "last_update_id": 0
}

# وضعیت مکالمه ادمین در تلگرام (برای دریافت ورودی مرحله‌ای)
STATE_IDLE = "idle"
STATE_SET_SCHEDULE = "set_schedule"
STATE_SET_PATHS = "set_paths"
STATE_SET_PART = "set_part"
STATE_SET_MODE = "set_mode"
STATE_SET_TOKEN = "set_token"

# رنگی
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# -------------------------
# Utils & Core
# -------------------------

def print_banner():
    banner = f"""
{GREEN}{BOLD}
 ██████╗ ███████╗██████╗ ███████╗ ██████╗ █████╗
 ██╔══██╗██╔════╝██╔══██╗██╔════╝██╔════╝██╔══██╗
 ██████╔╝█████╗  ██████╔╝█████╗  ██║     ███████║
 ██╔══██╗██╔══╝  ██╔══██╗██╔══╝  ██║     ██╔══██║
 ██║  ██║███████╗██████╔╝███████╗╚██████╗██║  ██║
 ╚═╝  ╚═╝╚══════╝╚═════╝ ╚══════╝ ╚═════╝╚═╝  ╚═╝

                {APP_NAME}
                {APP_TAG}
{RESET}
"""
    print(banner)

def ensure_dirs():
    os.makedirs(BASE_DIR, exist_ok=True)
    os.makedirs(WORK_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    os.makedirs("/var/lock", exist_ok=True)

def setup_logging():
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

def load_config():
    ensure_dirs()
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG.copy())
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = DEFAULT_CONFIG.copy()

    for k, v in DEFAULT_CONFIG.items():
        if k not in cfg:
            cfg[k] = v

    # sanitize
    cfg["admin_id"] = int(cfg.get("admin_id", 0) or 0)
    cfg["part_size_mb"] = int(cfg.get("part_size_mb", 45) or 45)
    cfg["enabled"] = bool(cfg.get("enabled", True))
    cfg["panel_poll_interval"] = int(cfg.get("panel_poll_interval", 2) or 2)
    cfg["last_update_id"] = int(cfg.get("last_update_id", 0) or 0)

    if cfg["send_mode"] not in ("auto", "single", "force_split"):
        cfg["send_mode"] = "auto"

    sch = str(cfg.get("schedule", "03:30"))
    if not is_valid_hhmm(sch):
        cfg["schedule"] = "03:30"

    if not isinstance(cfg.get("backup_paths", []), list):
        cfg["backup_paths"] = ["/etc", "/root"]

    return cfg

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            filename TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            parts INTEGER NOT NULL,
            status TEXT NOT NULL,
            note TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bot_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            state TEXT NOT NULL DEFAULT 'idle'
        )
    """)
    cur.execute("INSERT OR IGNORE INTO bot_state(id, state) VALUES(1, 'idle')")
    con.commit()
    con.close()

def set_bot_state(state):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("UPDATE bot_state SET state=? WHERE id=1", (state,))
    con.commit()
    con.close()

def get_bot_state():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT state FROM bot_state WHERE id=1")
    row = cur.fetchone()
    con.close()
    return row[0] if row else STATE_IDLE

def db_add_backup(filename, size_bytes, parts, status, note=""):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        INSERT INTO backups(created_at, filename, size_bytes, parts, status, note)
        VALUES(?,?,?,?,?,?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), filename, int(size_bytes), int(parts), status, note))
    con.commit()
    con.close()

def db_last_backups(limit=5):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT created_at, filename, size_bytes, parts, status FROM backups ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    con.close()
    return rows

def run_cmd(cmd):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True)

def is_valid_hhmm(s):
    return re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", s or "") is not None

def size_fmt(num):
    n = float(num)
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.2f} {u}"
        n /= 1024
    return f"{n:.2f} PB"

class FileLock:
    def __init__(self, path):
        self.path = path
        self.fd = None

    def acquire(self):
        self.fd = open(self.path, "w")
        fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.fd.write(str(os.getpid()))
        self.fd.flush()

    def release(self):
        try:
            if self.fd:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
                self.fd.close()
        except Exception:
            pass

# -------------------------
# Telegram API
# -------------------------

def tg_api_url(token, method):
    return f"https://api.telegram.org/bot{token}/{method}"

def tg_post_json(token, method, payload, timeout=60):
    data = parse.urlencode(payload).encode("utf-8")
    req = request.Request(tg_api_url(token, method), data=data, method="POST")
    with request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="ignore"))

def tg_send_message(token, chat_id, text, reply_markup=None):
    payload = {"chat_id": str(chat_id), "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    return tg_post_json(token, "sendMessage", payload, timeout=60)

def tg_send_document(token, chat_id, file_path, caption="", retries=4):
    boundary = "----RebecaBoundary" + hashlib.md5(str(time.time()).encode()).hexdigest()
    filename = os.path.basename(file_path)

    with open(file_path, "rb") as f:
        file_data = f.read()

    body = []
    def add_field(name, value):
        body.append(f"--{boundary}\r\n".encode())
        body.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.append(f"{value}\r\n".encode())

    add_field("chat_id", str(chat_id))
    add_field("caption", caption)

    body.append(f"--{boundary}\r\n".encode())
    body.append(f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'.encode())
    body.append(b"Content-Type: application/octet-stream\r\n\r\n")
    body.append(file_data)
    body.append(b"\r\n")
    body.append(f"--{boundary}--\r\n".encode())
    data = b"".join(body)

    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}

    last_err = None
    for i in range(retries):
        try:
            req = request.Request(tg_api_url(token, "sendDocument"), data=data, headers=headers, method="POST")
            with request.urlopen(req, timeout=600) as r:
                res = json.loads(r.read().decode("utf-8", errors="ignore"))
                if res.get("ok"):
                    return True, res
                last_err = str(res)
        except Exception as e:
            last_err = str(e)
            time.sleep(2 + i)
    return False, last_err

def tg_get_updates(token, offset=0, timeout=30):
    payload = {"offset": offset, "timeout": timeout}
    return tg_post_json(token, "getUpdates", payload, timeout=timeout+10)

# -------------------------
# Backup Engine
# -------------------------

def make_zip(paths):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(TMP_DIR, f"rebeca_backup_{ts}.zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in paths:
            p = p.strip()
            if not p:
                continue
            if not os.path.exists(p):
                logging.warning(f"path not found: {p}")
                continue

            if os.path.isfile(p):
                arcname = os.path.basename(p)
                try:
                    zf.write(p, arcname=arcname)
                except Exception as e:
                    logging.warning(f"zip file skip {p}: {e}")
            else:
                base = os.path.abspath(os.path.join(p, ".."))
                for root, dirs, files in os.walk(p):
                    for fn in files:
                        fp = os.path.join(root, fn)
                        try:
                            arcname = os.path.relpath(fp, base)
                            zf.write(fp, arcname=arcname)
                        except Exception as e:
                            logging.warning(f"zip walk skip {fp}: {e}")
    return zip_path

def split_file(file_path, part_size_mb):
    part_bytes = int(part_size_mb) * 1024 * 1024
    total = os.path.getsize(file_path)
    if total <= part_bytes:
        return [file_path]

    parts = []
    with open(file_path, "rb") as src:
        idx = 1
        while True:
            chunk = src.read(part_bytes)
            if not chunk:
                break
            part_path = f"{file_path}.part{idx:03d}"
            with open(part_path, "wb") as dst:
                dst.write(chunk)
            parts.append(part_path)
            idx += 1
    return parts

def cleanup_files(paths):
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

def cleanup_old(days):
    if int(days) <= 0:
        return
    now = time.time()
    ttl = int(days) * 86400
    for name in os.listdir(TMP_DIR):
        fp = os.path.join(TMP_DIR, name)
        try:
            if os.path.isfile(fp) and now - os.path.getmtime(fp) > ttl:
                os.remove(fp)
        except Exception:
            pass

def perform_backup(force=False):
    cfg = load_config()
    token = cfg["bot_token"].strip()
    admin_id = int(cfg["admin_id"])
    enabled = bool(cfg["enabled"])

    if not token or admin_id <= 0:
        return False, "توکن یا ادمین آیدی تنظیم نشده"

    if not enabled and not force:
        logging.info("backup skipped: disabled")
        return False, "غیرفعال است"

    lock = FileLock(LOCK_FILE)
    try:
        lock.acquire()
    except Exception:
        return False, "یک بکاپ دیگر در حال اجراست"

    zip_path = None
    part_paths = []
    try:
        paths = cfg.get("backup_paths", [])
        part_size_mb = int(cfg.get("part_size_mb", 45))
        send_mode = cfg.get("send_mode", "auto")

        logging.info("backup started")
        zip_path = make_zip(paths)
        total_size = os.path.getsize(zip_path)

        if send_mode == "single":
            part_paths = [zip_path]
        elif send_mode == "force_split":
            part_paths = split_file(zip_path, part_size_mb)
        else:
            # auto
            if total_size > part_size_mb * 1024 * 1024:
                part_paths = split_file(zip_path, part_size_mb)
            else:
                part_paths = [zip_path]

        try:
            tg_send_message(token, admin_id, f"✅ {APP_NAME}\nشروع ارسال بکاپ\nحجم: {size_fmt(total_size)}")
        except Exception:
            pass

        total_parts = len(part_paths)
        errors = []
        for i, p in enumerate(part_paths, start=1):
            cap = f"{CAPTION_FOOTER} | part {i}/{total_parts}"
            ok, res = tg_send_document(token, admin_id, p, caption=cap, retries=4)
            if not ok:
                errors.append(f"part {i}: {res}")
                logging.error(f"send part {i} failed: {res}")
            else:
                logging.info(f"sent part {i}/{total_parts}")

        if not errors:
            db_add_backup(os.path.basename(zip_path), total_size, total_parts, "SUCCESS", "")
            try:
                tg_send_message(token, admin_id, f"✅ بکاپ کامل ارسال شد\nفایل: {os.path.basename(zip_path)}\nپارت: {total_parts}")
            except Exception:
                pass
            status = (True, f"ارسال موفق ({total_parts} پارت)")
        else:
            note = " | ".join(errors)[:1500]
            db_add_backup(os.path.basename(zip_path), total_size, total_parts, "FAILED", note)
            try:
                tg_send_message(token, admin_id, "❌ ارسال بکاپ ناقص شد.\n" + "\n".join(errors[:5]))
            except Exception:
                pass
            status = (False, "ارسال ناقص/ناموفق")

        # پاکسازی
        to_del = []
        if zip_path:
            to_del.append(zip_path)
        for p in part_paths:
            if p != zip_path:
                to_del.append(p)
        cleanup_files(to_del)

        cleanup_old(cfg.get("keep_local_days", 0))
        return status

    except Exception as e:
        logging.exception(f"perform_backup error: {e}")
        return False, f"خطا: {e}"
    finally:
        lock.release()

# -------------------------
# Scheduler (cron)
# -------------------------

def write_cron(schedule_hhmm, script_path):
    hh, mm = schedule_hhmm.split(":")
    line = f'{int(mm)} {int(hh)} * * * /usr/bin/python3 {script_path} --run >> {LOG_FILE} 2>&1'
    res = run_cmd("crontab -l 2>/dev/null")
    current = res.stdout if res.returncode == 0 else ""
    lines = [x for x in current.splitlines() if "--run" not in x or "rebeca_backup.py" not in x]
    lines.append(line)
    temp = "/tmp/rebeca_cron.txt"
    with open(temp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    run_cmd(f"crontab {temp}")
    os.remove(temp)

def remove_cron():
    res = run_cmd("crontab -l 2>/dev/null")
    if res.returncode != 0:
        return
    lines = [x for x in res.stdout.splitlines() if "rebeca_backup.py --run" not in x]
    temp = "/tmp/rebeca_cron.txt"
    with open(temp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    run_cmd(f"crontab {temp}")
    os.remove(temp)

# -------------------------
# Telegram Panel
# -------------------------

def kb_main():
    return {
        "inline_keyboard": [
            [{"text": "⚡ بکاپ فوری", "callback_data": "do_backup_now"}],
            [{"text": "⏰ تغییر زمان‌بندی", "callback_data": "set_schedule"}],
            [{"text": "📁 تغییر مسیرها", "callback_data": "set_paths"}],
            [{"text": "📦 تغییر سایز پارت", "callback_data": "set_part"}],
            [{"text": "🧠 حالت ارسال", "callback_data": "set_mode"}],
            [{"text": "✅ فعال‌سازی", "callback_data": "enable_backup"},
             {"text": "⛔ غیرفعال‌سازی", "callback_data": "disable_backup"}],
            [{"text": "📊 وضعیت", "callback_data": "show_status"},
             {"text": "🕘 آخرین بکاپ‌ها", "callback_data": "show_last"}],
            [{"text": "🔁 بروزرسانی توکن", "callback_data": "set_token"}]
        ]
    }

def answer_callback(token, callback_id, text="انجام شد"):
    try:
        tg_post_json(token, "answerCallbackQuery", {"callback_query_id": callback_id, "text": text}, timeout=30)
    except Exception:
        pass

def is_admin_user(update, admin_id):
    try:
        if "message" in update:
            uid = int(update["message"]["from"]["id"])
            return uid == int(admin_id)
        if "callback_query" in update:
            uid = int(update["callback_query"]["from"]["id"])
            return uid == int(admin_id)
    except Exception:
        return False
    return False

def get_chat_id_from_update(update):
    if "message" in update:
        return update["message"]["chat"]["id"]
    if "callback_query" in update:
        return update["callback_query"]["message"]["chat"]["id"]
    return None

def render_status_text(cfg):
    return (
        f"📌 وضعیت {APP_NAME}\n"
        f"Admin ID: {cfg.get('admin_id')}\n"
        f"Enabled: {cfg.get('enabled')}\n"
        f"Schedule: {cfg.get('schedule')}\n"
        f"Paths: {', '.join(cfg.get('backup_paths', []))}\n"
        f"Part Size: {cfg.get('part_size_mb')} MB\n"
        f"Mode: {cfg.get('send_mode')}\n"
        f"{APP_TAG}"
    )

def handle_admin_text_message(token, cfg, msg):
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    state = get_bot_state()

    if text == "/start":
        set_bot_state(STATE_IDLE)
        tg_send_message(token, chat_id, f"سلام ادمین 👋\nبه {APP_NAME} خوش آمدی.", reply_markup=kb_main())
        return

    if text == "/menu":
        set_bot_state(STATE_IDLE)
        tg_send_message(token, chat_id, "منوی مدیریت:", reply_markup=kb_main())
        return

    if text == "/backup":
        ok, m = perform_backup(force=True)
        tg_send_message(token, chat_id, ("✅ " if ok else "❌ ") + m, reply_markup=kb_main())
        return

    # stateful input
    if state == STATE_SET_SCHEDULE:
        if not is_valid_hhmm(text):
            tg_send_message(token, chat_id, "❌ فرمت درست نیست. مثال: 03:30")
            return
        cfg["schedule"] = text
        cfg["enabled"] = True
        save_config(cfg)
        write_cron(text, os.path.abspath(__file__))
        set_bot_state(STATE_IDLE)
        tg_send_message(token, chat_id, f"✅ زمان‌بندی ذخیره شد: {text}", reply_markup=kb_main())
        return

    if state == STATE_SET_PATHS:
        items = [x.strip() for x in text.split(",") if x.strip()]
        if not items:
            tg_send_message(token, chat_id, "❌ حداقل یک مسیر لازم است.")
            return
        cfg["backup_paths"] = items
        save_config(cfg)
        set_bot_state(STATE_IDLE)
        tg_send_message(token, chat_id, "✅ مسیرها ذخیره شد.", reply_markup=kb_main())
        return

    if state == STATE_SET_PART:
        if not text.isdigit() or int(text) <= 0:
            tg_send_message(token, chat_id, "❌ عدد معتبر وارد کن. مثال: 45")
            return
        cfg["part_size_mb"] = int(text)
        save_config(cfg)
        set_bot_state(STATE_IDLE)
        tg_send_message(token, chat_id, f"✅ سایز پارت شد {text}MB", reply_markup=kb_main())
        return

    if state == STATE_SET_MODE:
        if text not in ("auto", "single", "force_split"):
            tg_send_message(token, chat_id, "❌ فقط: auto یا single یا force_split")
            return
        cfg["send_mode"] = text
        save_config(cfg)
        set_bot_state(STATE_IDLE)
        tg_send_message(token, chat_id, f"✅ حالت ارسال: {text}", reply_markup=kb_main())
        return

    if state == STATE_SET_TOKEN:
        if len(text) < 20 or ":" not in text:
            tg_send_message(token, chat_id, "❌ توکن معتبر نیست.")
            r