"""User-session fallback when Windows denies Task Scheduler registration.
Runs quietly after login. Daily target is 02:00 local time; missed runs catch up.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime,timezone
from pathlib import Path
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env',override=False)
OUT=ROOT/'.database-backups/scheduled';OUT.mkdir(parents=True,exist_ok=True)
lock=(OUT/'scheduler.lock').open('a+b');lock.write(b'0');lock.flush();lock.seek(0)
try:
    if os.name=='nt':
        import msvcrt
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    else:
        import fcntl
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
except OSError:sys.exit(0)
retry_after=0
remote_retry_after=0
while True:
    now=datetime.now().astimezone()
    last_date=None
    try:
        last=json.loads((OUT/'last_run.json').read_text())
        if last.get('status')=='completed' and last.get('restore_verified'):
            last_date=datetime.strptime(last['started_utc'].split('-')[0],'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).astimezone().date()
    except (OSError,ValueError,KeyError):pass
    (OUT/'scheduler_status.json').write_text(json.dumps({'pid':os.getpid(),'heartbeat':now.isoformat(),'target_local_time':'02:00',
        'mode':'current-user Startup; logged-in desktop session','last_verified_backup_date':str(last_date) if last_date else None},indent=2))
    if now.hour>=2 and last_date!=now.date() and time.time()>=retry_after:
        try:
            subprocess.run([sys.executable,str(ROOT/'tools/backup_database.py'),'--verify-restore'],cwd=ROOT,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1800,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        except (OSError,subprocess.TimeoutExpired):pass
        retry_after=time.time()+3600
    # Optional hosted backup uses the external URL stored privately on this desktop.
    # Keep its verification and retention separate from the desktop database.
    if os.environ.get('RENDER_BACKUP_DATABASE_URL') and now.hour>=2 and time.time()>=remote_retry_after:
        remote=ROOT/'.database-backups/render'
        remote_date=None
        try:
            last=json.loads((remote/'last_run.json').read_text())
            if last.get('status')=='completed' and last.get('restore_verified'):
                remote_date=datetime.strptime(last['started_utc'].split('-')[0],'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).astimezone().date()
        except (OSError,ValueError,KeyError):pass
        if remote_date!=now.date():
            try:
                subprocess.run([sys.executable,str(ROOT/'tools/backup_database.py'),'--verify-restore',
                    '--database-url-env','RENDER_BACKUP_DATABASE_URL','--destination',str(remote)],cwd=ROOT,
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1800,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            except (OSError,subprocess.TimeoutExpired):pass
        remote_retry_after=time.time()+3600
    time.sleep(60)
