#!/usr/bin/env bash
set -euo pipefail
APP_DIR="/opt/ggbackup"
CONFIG_DIR="/etc/ggbackup"
CONFIG_FILE="$CONFIG_DIR/config.json"
SERVICE_FILE="/etc/systemd/system/ggbackup.service"
BIN_FILE="/usr/local/bin/ggbackup"

if [ "$(id -u)" != "0" ]; then echo "❌ با root اجرا کن"; exit 1; fi

if ! command -v python3 >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then apt-get update -y && apt-get install -y python3 python3-pip
  elif command -v dnf >/dev/null 2>&1; then dnf install -y python3 python3-pip
  elif command -v yum >/dev/null 2>&1; then yum install -y python3 python3-pip
  else echo "❌ مدیر بسته پشتیبانی نمی‌شود"; exit 1; fi
fi

mkdir -p "$APP_DIR" "$CONFIG_DIR"
cp "$(dirname "$0")/ggcoder_backup.py" "$APP_DIR/ggcoder_backup.py"
python3 -m pip install --quiet --disable-pip-version-check requests

if [ ! -f "$CONFIG_FILE" ]; then
  read -r -p "🤖 توکن ربات: " BOT_TOKEN
  read -r -p "👤 آیدی عددی ادمین: " ADMIN_ID
  read -r -p "📁 مسیرهای بکاپ [ /var/www /home ]: " BACKUP_PATHS
  BACKUP_PATHS="${BACKUP_PATHS:-/var/www /home}"
  read -r -p "⏰ فاصله بکاپ به ساعت [6]: " INTERVAL
  INTERVAL="${INTERVAL:-6}"
  python3 - "$CONFIG_FILE" "$BOT_TOKEN" "$ADMIN_ID" "$BACKUP_PATHS" "$INTERVAL" <<'PY'
import json, shlex, sys
out, token, admin, paths, interval = sys.argv[1:]
data = {"token": token.strip(), "admin_id": int(admin), "paths": shlex.split(paths), "interval_hours": float(interval), "last_backup": None, "last_size": 0}
with open(out, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
PY
  chmod 600 "$CONFIG_FILE"
fi

cat > "$SERVICE_FILE" <<EOF2
[Unit]
Description=GGCODER Server Backup Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $APP_DIR/ggcoder_backup.py
Restart=always
RestartSec=5
WorkingDirectory=$APP_DIR
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF2

cat > "$BIN_FILE" <<'EOF2'
#!/usr/bin/env bash
exec /usr/bin/python3 /opt/ggbackup/ggcoder_backup.py --menu
EOF2
chmod 755 "$BIN_FILE"
systemctl daemon-reload
systemctl enable ggbackup.service >/dev/null
systemctl restart ggbackup.service

echo
printf '╭━━━━━━━━━━━━━━━━━━━━╮\n'
printf '      🛡️ GGCODER BACKUP\n'
printf '╰━━━━━━━━━━━━━━━━━━━━╯\n'
echo "✅ نصب کامل شد"
echo "🎛️ مدیریت: ggbackup"
echo "📡 وضعیت: systemctl status ggbackup"
echo "💠 ggcoder_ir@"
