# Rebeca Backup Bot

Telegram Server Backup Bot (Single-file Core)  
**Tag:** @GGCODER_IR  
**Caption Footer:** `ggcoder_ir@`

---

## Features

- Zip backup from selected server paths
- Send backup to Telegram
- Split large backups into multiple parts automatically
- Only one `Admin ID` is authorized
- Telegram panel with `/start`:
  - Quick backup
  - Change schedule
  - Change paths
  - Change part size
  - Change send mode
  - Enable/Disable scheduled backup
- Server-side menu command: `ggbackup`
- Cron-based scheduler + systemd service for Telegram panel
- Logging: `/var/log/rebeca_backup.log`

---

## Project Structure

- `rebeca_backup.py` → Main single-file bot/engine/panel
- `install.sh` → Auto installer
- `LICENSE`
- `README.md`

---

## Quick Install (from GitHub)
```bash
bash <(curl -Ls https://raw.githubusercontent.com/USERNAME/rebeca-backup/main/install.sh)

---

## Manual Install (local)

bash
chmod +x install.sh
sudo ./install.sh

---

## Usage

### Server menu
bash
ggbackup

### Commands
bash
python3 /opt/rebeca-backup/rebeca_backup.py --menu
python3 /opt/rebeca-backup/rebeca_backup.py --run-now
python3 /opt/rebeca-backup/rebeca_backup.py --panel

---

## Telegram Panel

1. Start your bot in Telegram with `/start`
2. Only configured `Admin ID` can control the bot
3. Use inline buttons to manage backup settings

---

## Logs

- Main log: `/var/log/rebeca_backup.log`
- Service status:
bash
systemctl status rebeca-panel --no-pager

---

## Security Notes

- Keep bot token private
- Use root only when necessary
- Restrict server access (SSH keys, firewall)

---

## License

MIT License (see `LICENSE`)


---

## 4) فایل `LICENSE` (MIT)

```text
MIT License

Copyright (c) 2026 GGCODER_IR

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
