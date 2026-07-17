#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, html, json, os, threading, time, zipfile
from datetime import datetime
from pathlib import Path
import requests

CONFIG_FILE = Path('/etc/ggbackup/config.json')
TMP_DIR = Path('/tmp/ggbackup')
BRAND = 'ggcoder_ir@'
MAX_UPLOAD = 49 * 1024 * 1024
SKIP_DIRS = {'/proc','/sys','/dev','/run','/tmp','/var/cache','/var/lib/docker/overlay2'}
STOP = threading.Event()
BACKUP_LOCK = threading.Lock()
LAST_STATUS = 'آماده'
LAST_PROGRESS = 0


def now(): return datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')

def load_config():
    with CONFIG_FILE.open(encoding='utf-8') as f: return json.load(f)

def save_config(cfg):
    tmp = CONFIG_FILE.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as f: json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.chmod(tmp, 0o600); tmp.replace(CONFIG_FILE)

def api(cfg, method, data=None, files=None, timeout=60):
    r = requests.post(f"https://api.telegram.org/bot{cfg['token']}/{method}", data=data, files=files, timeout=timeout)
    return r.json()

def send(cfg, chat, text, keyboard=None):
    data={'chat_id':chat,'text':text,'parse_mode':'HTML'}
    if keyboard: data['reply_markup']=json.dumps(keyboard, ensure_ascii=False)
    return api(cfg,'sendMessage',data)

def edit(cfg, chat, mid, text, keyboard=None):
    data={'chat_id':chat,'message_id':mid,'text':text,'parse_mode':'HTML'}
    if keyboard: data['reply_markup']=json.dumps(keyboard, ensure_ascii=False)
    return api(cfg,'editMessageText',data)

def answer(cfg, cid, text=''): return api(cfg,'answerCallbackQuery',{'callback_query_id':cid,'text':text})

def kb():
    return {'inline_keyboard':[
        [{'text':'⚡ ارسال فوری','callback_data':'backup'},{'text':'📊 وضعیت','callback_data':'status'}],
        [{'text':'⏰ زمان‌بندی','callback_data':'schedule'},{'text':'📁 مسیرها','callback_data':'paths'}],
        [{'text':'🔑 تغییر توکن','callback_data':'token'},{'text':'⛔ لغو بکاپ','callback_data':'cancel'}],
        [{'text':'🔄 بروزرسانی پنل','callback_data':'home'}]
    ]}

def human(n):
    n=float(n or 0)
    for u in ('B','KB','MB','GB','TB'):
        if n<1024: return f'{n:.1f} {u}'
        n/=1024
    return f'{n:.1f} PB'

def panel(cfg):
    paths='\n'.join('• '+html.escape(str(x)) for x in cfg.get('paths',[]))
    return ("╭━━━━━━━━━━━━━━━━━━━━╮\n      🛡️ <b>GGCODER BACKUP</b>\n╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
            "🟢 <b>سیستم فعال است</b>\n\n"
            f"📦 آخرین بکاپ: <code>{html.escape(str(cfg.get('last_backup') or 'هنوز انجام نشده'))}</code>\n"
            f"💾 حجم آخرین بکاپ: <b>{human(cfg.get('last_size',0))}</b>\n"
            f"⏰ فاصله ارسال: <b>{cfg.get('interval_hours',6)} ساعت</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n📁 <b>مسیرهای فعال:</b>\n"+paths+f"\n\n━━━━━━━━━━━━━━━━━━━━\n💠 <b>{BRAND}</b>")

def skipped(p):
    s=str(p); return any(s==x or s.startswith(x+'/') for x in SKIP_DIRS)

def files(paths):
    for root in paths:
        p=Path(root)
        if not p.exists(): continue
        if p.is_file(): yield p; continue
        for base, dirs, names in os.walk(p, topdown=True, followlinks=False):
            if skipped(base): dirs[:]=[]; continue
            dirs[:]=[d for d in dirs if not skipped(os.path.join(base,d))]
            for name in names:
                f=Path(base)/name
                try:
                    if f.is_file() and not f.is_symlink(): yield f
                except OSError: pass

def make_backup(cfg):
    global LAST_STATUS, LAST_PROGRESS
    if not BACKUP_LOCK.acquire(False): return None
    try:
        STOP.clear(); LAST_STATUS='در حال اسکن فایل‌ها...'; LAST_PROGRESS=0
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        archive=TMP_DIR/f"ggbackup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        fs=[]
        for f in files(cfg.get('paths',[])):
            if STOP.is_set(): LAST_STATUS='بکاپ لغو شد'; return None
            fs.append(f)
        if not fs: LAST_STATUS='فایلی برای بکاپ پیدا نشد'; return None
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for i,f in enumerate(fs,1):
                if STOP.is_set():
                    LAST_STATUS='بکاپ لغو شد'
                    try: archive.unlink()
                    except FileNotFoundError: pass
                    return None
                try: z.write(f, f.as_posix().lstrip('/'))
                except (OSError,PermissionError): continue
                LAST_PROGRESS=int(i*100/len(fs)); LAST_STATUS=f'فشرده‌سازی: {LAST_PROGRESS}%'
        LAST_STATUS='بکاپ آماده ارسال'; return archive
    finally: BACKUP_LOCK.release()

def upload(cfg, chat, archive):
    size=archive.stat().st_size
    if size<=MAX_UPLOAD:
        with archive.open('rb') as f: api(cfg,'sendDocument',{'chat_id':chat,'caption':BRAND},{'document':(archive.name,f,'application/zip')},300)
        return
    part_size=45*1024*1024; total=(size+part_size-1)//part_size
    with archive.open('rb') as src:
        for i in range(1,total+1):
            part=TMP_DIR/f'{archive.name}.part{i}'
            with part.open('wb') as dst:
                left=part_size
                while left:
                    chunk=src.read(min(1024*1024,left))
                    if not chunk: break
                    dst.write(chunk); left-=len(chunk)
            with part.open('rb') as f: api(cfg,'sendDocument',{'chat_id':chat,'caption':f'{BRAND}\n📦 بخش {i}/{total}'},{'document':(part.name,f,'application/octet-stream')},300)
            try: part.unlink()
            except FileNotFoundError: pass

def worker(cfg, chat):
    global LAST_STATUS
    archive=None
    try:
        archive=make_backup(cfg)
        if not archive: return
        LAST_STATUS='در حال ارسال به تلگرام...'; upload(cfg,chat,archive)
        size=archive.stat().st_size; cfg['last_backup']=now(); cfg['last_size']=size; save_config(cfg); LAST_STATUS='بکاپ با موفقیت ارسال شد'
        send(cfg,chat,f"╭━━━━━━━━━━━━━━━━━━━━╮\n      ✅ <b>BACKUP SENT</b>\n╰━━━━━━━━━━━━━━━━━━━━╯\n\n📦 حجم: <b>{human(size)}</b>\n🕒 زمان: <code>{now()}</code>\n\n💠 <b>{BRAND}</b>",kb())
    except Exception as e:
        LAST_STATUS=f'خطا: {e}'; send(cfg,chat,'❌ <b>ارسال بکاپ ناموفق بود</b>\n\n<code>'+html.escape(str(e))[:1000]+'</code>',kb())
    finally:
        if archive:
            try: archive.unlink()
            except FileNotFoundError: pass

def start(cfg, chat):
    if BACKUP_LOCK.locked(): send(cfg,chat,'⏳ یک بکاپ در حال اجراست.',kb()); return
    threading.Thread(target=worker,args=(cfg,chat),daemon=True).start()
    send(cfg,chat,'⚡ <b>BACKUP STARTED</b>\n\n📦 بکاپ در پس‌زمینه شروع شد.',kb())

def scheduler():
    while True:
        try:
            cfg=load_config(); time.sleep(max(float(cfg.get('interval_hours',6)),0.1)*3600); start(load_config(),load_config()['admin_id'])
        except Exception: time.sleep(60)

def cli():
    cfg=load_config()
    while True:
        print('\n🛡️ GGCODER BACKUP\n1) تغییر توکن\n2) تغییر زمان\n3) ارسال فوری\n4) لغو\n5) وضعیت\n6) خروج')
        c=input('انتخاب: ').strip()
        if c=='1':
            v=input('توکن جدید: ').strip()
            if v: cfg['token']=v; save_config(cfg); print('✅ تغییر کرد')
        elif c=='2':
            try: cfg['interval_hours']=float(input('فاصله به ساعت: ')); save_config(cfg); print('✅ تغییر کرد')
            except ValueError: print('❌ نامعتبر')
        elif c=='3': start(cfg,cfg['admin_id'])
        elif c=='4': STOP.set(); print('⛔ درخواست لغو ارسال شد')
        elif c=='5': print(f'📊 {LAST_STATUS}\n📈 {LAST_PROGRESS}%')
        elif c=='6': break

def main():
    p=argparse.ArgumentParser(); p.add_argument('--menu',action='store_true'); a=p.parse_args()
    if a.menu: cli(); return
    cfg=load_config(); admin=int(cfg['admin_id']); threading.Thread(target=scheduler,daemon=True).start(); offset=None
    while True:
        try:
            cfg=load_config(); res=api(cfg,'getUpdates',{'timeout':30,'offset':offset},timeout=40)
            for u in res.get('result',[]):
                offset=u['update_id']+1; msg=u.get('message'); cb=u.get('callback_query')
                if cb:
                    chat=cb['message']['chat']['id']
                    if chat!=admin: answer(cfg,cb['id'],'⛔ دسترسی ندارید'); continue
                    d=cb.get('data'); answer(cfg,cb['id'])
                    if d=='home': edit(cfg,chat,cb['message']['message_id'],panel(cfg),kb())
                    elif d=='backup': start(cfg,chat)
                    elif d=='status': edit(cfg,chat,cb['message']['message_id'],f'📊 <b>{html.escape(LAST_STATUS)}</b>\n📈 پیشرفت: <b>{LAST_PROGRESS}%</b>\n🔒 بکاپ: <b>{"در حال اجرا" if BACKUP_LOCK.locked() else "آزاد"}</b>',kb())
                    elif d=='schedule': send(cfg,chat,f'⏰ فاصله فعلی: <b>{cfg.get("interval_hours",6)} ساعت</b>\n\nبرای تغییر: <code>ggbackup</code>',kb())
                    elif d=='paths': send(cfg,chat,'📁 <b>مسیرهای بکاپ</b>\n\n'+'\n'.join('• <code>'+html.escape(str(x))+'</code>' for x in cfg.get('paths',[])),kb())
                    elif d=='token': send(cfg,chat,'🔑 تغییر توکن از سرور:\n\n<code>ggbackup</code>',kb())
                    elif d=='cancel': STOP.set(); send(cfg,chat,'⛔ درخواست لغو بکاپ ارسال شد.',kb())
                    continue
                if not msg or msg['chat']['id']!=admin: continue
                text=msg.get('text','').strip()
                if text in ('/start','/panel','/menu'): send(cfg,admin,panel(cfg),kb())
                elif text=='/backup': start(cfg,admin)
                elif text=='/cancel': STOP.set(); send(cfg,admin,'⛔ درخواست لغو ارسال شد.',kb())
        except Exception: time.sleep(5)

if __name__=='__main__': main()
