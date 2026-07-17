cat > /tmp/install_fixed.sh <<'INSTALL'
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/ggbackup"
CONFIG_DIR="/etc/ggbackup"
CONFIG_FILE="$CONFIG_DIR/config.json"
SERVICE_FILE="/etc/systemd/system/ggbackup.service"
BIN_FILE="/usr/local/bin/ggbackup"

REPO_RAW="https://raw.githubusercontent.com/ggcoder021/rebeca_backup/main"

if [ "$(id -u)" != "0" ]; then
    echo "❌ با root اجرا کن"
    exit 1
fi

mkdir -p "$APP_DIR" "$CONFIG_DIR"

curl -fsSL "$REPO_RAW/ggcoder_backup.py" \
    -o "$APP_DIR/ggcoder_backup.py"

chmod 700 "$APP_DIR/ggcoder_backup.py"

python3 -m pip install --quiet --disable-pip-version-check requests 2>/dev/null || true

if [ ! -f "$CONFIG_FILE" ]; then
    read -r -p "🤖 توکن ربات: " BOT_TOKEN
    read -r -p "👤 آیدی عددی ادمین: " ADMIN_ID
    read -r -p "📁 مسیرهای بکاپ [ /var/www /home ]: " BACKUP_PATHS
    BACKUP_PATHS="${BACKUP_PATHS:-/var/www /home}"
    read -r -p "⏰ فاصله بکاپ به ساعت [6]: " INTERVAL
    INTERVAL="${INTERVAL:-6}"

    python3 - "$CONFIG_FILE" "$BOT_TOKEN" "$ADMIN_ID" "$BACKUP_PATHS" "$INTERVAL" <<'PY'
import json
import shlex
import sys

out, token, admin, paths, interval = sys.argv[1:]

with open(out, "w", encoding="utf-8") as f:
    json.dump({
        "token": token.strip(),
        "admin_id": int(admin.strip()),
        "paths": shlex.split(paths),
        "interval_hours": float(interval),
        "last_backup": None,
        "last_size": 0
    }, f, ensure_ascii=False, indent=2)
PY

    chmod 600 "$CONFIG_FILE"
fi

cat > "$SERVICE_FILE" <<EOF
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
EOF

cat > "$BIN_FILE" <<'EOF'
#!/usr/bin/env bash
exec /usr/bin/python3 /opt/ggbackup/ggcoder_backup.py --menu
EOF

chmod 755 "$BIN_FILE"

systemctl daemon-reload
systemctl enable ggbackup.service >/dev/null
systemctl restart ggbackup.service

echo
echo "╭━━━━━━━━━━━━━━━━━━━━╮"
echo "      ✅ نصب کامل شد"
echo "╰━━━━━━━━━━━━━━━━━━━━╯"
echo
echo "🎛️ مدیریت: ggbackup"
echo "📡 وضعیت: systemctl status ggbackup"
echo "💠 ggcoder_ir@"
INSTALL

bash /tmp/install_fixed.sh
