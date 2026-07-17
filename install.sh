#!/usr/bin/env bash
set -e

GREEN='\033[0;92m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${GREEN}${BOLD}"
cat << "EOF"
 ██████╗  ██████╗  ██████╗ ██████╗ ███████╗██████╗
██╔════╝ ██╔════╝ ██╔════╝██╔═══██╗██╔════╝██╔══██╗
██║  ███╗██║  ███╗██║     ██║   ██║█████╗  ██████╔╝
██║   ██║██║   ██║██║     ██║   ██║██╔══╝  ██╔══██╗
╚██████╔╝╚██████╔╝╚██████╗╚██████╔╝███████╗██║  ██║
 ╚═════╝  ╚═════╝  ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝

                 @GGCODER_IR
                  بکاپر ربکا
EOF
echo -e "${NC}"

if [ "$EUID" -ne 0 ]; then
  echo "❌ لطفاً با root اجرا کنید."
  exit 1
fi

apt-get update -y
apt-get install -y python3 python3-pip curl zip unzip cron
systemctl enable cron >/dev/null 2>&1 || true
systemctl start cron >/dev/null 2>&1 || true

mkdir -p /opt/rebeca-backup
cd /opt/rebeca-backup

if [ ! -f /opt/rebeca-backup/rebeca_backup.py ]; then
  echo "❌ فایل rebeca_backup.py در ریپو نیست."
  exit 1
fi

chmod +x /opt/rebeca-backup/rebeca_backup.py
python3 /opt/rebeca-backup/rebeca_backup.py --install

cat > /etc/systemd/system/rebeca-panel.service << 'EOF'
[Unit]
Description=Rebeca Backup Telegram Panel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/rebeca-backup/rebeca_backup.py --panel
Restart=always
RestartSec=3
User=root
WorkingDirectory=/opt/rebeca-backup

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable rebeca-panel.service
systemctl restart rebeca-panel.service

echo "✅ نصب کامل شد."
echo "منوی سرور: ggbackup"
echo "وضعیت سرویس پنل: systemctl status rebeca-panel --no-pager"
