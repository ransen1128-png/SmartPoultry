"""Back up configured PostgreSQL and optionally prove restoration in a private
temporary PostgreSQL cluster. Never restores over the application's database.
"""
import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime,timezone,timedelta
from pathlib import Path
import psycopg2
from psycopg2 import sql

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'smartpoultry'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings')
from django.conf import settings


def run(arguments,env=None,timeout=180):
    result=subprocess.run([str(arg) for arg in arguments],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if result.returncode: raise RuntimeError(f'{Path(arguments[0]).name} failed (exit {result.returncode}).')
    return result


def table_fingerprints(connection):
    result={}
    with connection.cursor() as cursor:
        cursor.execute("SET TIME ZONE 'UTC'")
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
        tables=[row[0] for row in cursor.fetchall()]
        for table in tables:
            cursor.execute(sql.SQL('SELECT row_to_json(t)::text FROM {} t ORDER BY row_to_json(t)::text COLLATE "C"').format(sql.Identifier('public',table)))
            digest=hashlib.sha256();count=0
            while True:
                batch=cursor.fetchmany(1000)
                if not batch: break
                for (row,) in batch:digest.update(row.encode()+b'\n');count+=1
            result[table]={'rows':count,'sha256':digest.hexdigest()}
    return result


def postgres_bin():
    configured=os.environ.get('POSTGRES_BIN')
    if configured:return Path(configured)
    found=shutil.which('pg_dump')
    if found:return Path(found).parent
    versions=sorted(Path('C:/Program Files/PostgreSQL').glob('*/bin/pg_dump.exe'),key=lambda p:int(p.parents[1].name) if p.parents[1].name.isdigit() else 0,reverse=True)
    if versions:return versions[0].parent
    raise RuntimeError('PostgreSQL client tools not found. Set POSTGRES_BIN.')


def verify_restore(binary,dump,expected,destination):
    scratch=Path(tempfile.mkdtemp(prefix='restore-check-',dir=destination)).resolve()
    scratch.relative_to(destination.resolve())
    data=scratch/'data';started=False;stopped=False
    with socket.socket() as candidate:candidate.bind(('127.0.0.1',0));port=candidate.getsockname()[1]
    extension='.exe' if os.name=='nt' else ''
    pgctl=binary/('pg_ctl'+extension)
    try:
        run([binary/('initdb'+extension),'-D',data,'-U','restorecheck','-A','trust','--no-locale','--encoding=UTF8'])
        run([pgctl,'-D',data,'-l',scratch/'server.log','-o',f'-h 127.0.0.1 -p {port}','-w','-t','30','start'])
        started=True
        run([binary/('pg_restore'+extension),'--exit-on-error','--no-owner','--no-privileges','-h','127.0.0.1','-p',port,'-U','restorecheck','-d','postgres',dump])
        with psycopg2.connect(host='127.0.0.1',port=port,user='restorecheck',dbname='postgres') as restored:
            actual=table_fingerprints(restored)
        if expected!=actual:raise RuntimeError('Restored row counts/content checksums do not match the backup snapshot.')
        return {'restore_verified':True,'verified_tables':len(actual),'verified_rows':sum(table['rows'] for table in actual.values())}
    finally:
        if started or (data/'postmaster.pid').exists():
            run([pgctl,'-D',data,'-m','fast','-w','stop']);stopped=True
        if not started or stopped:
            scratch.relative_to(destination.resolve())
            shutil.rmtree(scratch)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-restore',action='store_true')
    args=parser.parse_args()
    destination=ROOT/'.database-backups/scheduled';destination.mkdir(parents=True,exist_ok=True)
    lockpath=destination/'backup.lock'
    lock=lockpath.open('a+b');lock.write(b'0');lock.flush();lock.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:raise RuntimeError('Another backup is running.')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
    report={'started_utc':stamp,'status':'failed','restore_verified':False}
    try:
        db=settings.DATABASES['default']
        if not db['ENGINE'].endswith('postgresql'):raise RuntimeError('Configured database must be PostgreSQL.')
        binary=postgres_bin();extension='.exe' if os.name=='nt' else ''
        env=os.environ.copy();env['PGPASSWORD']=db.get('PASSWORD','')
        if db.get('OPTIONS',{}).get('sslmode'):env['PGSSLMODE']=db['OPTIONS']['sslmode']
        connect=dict(host=db.get('HOST') or 'localhost',port=db.get('PORT') or 5432,user=db['USER'],password=db.get('PASSWORD',''),dbname=db['NAME'])
        if 'PGSSLMODE' in env:connect['sslmode']=env['PGSSLMODE']
        dump=destination/f'backup-{stamp}.dump'
        with psycopg2.connect(**connect) as source:
            source.set_session(isolation_level='REPEATABLE READ',readonly=True)
            with source.cursor() as cursor:cursor.execute('SELECT pg_export_snapshot()');snapshot=cursor.fetchone()[0]
            expected=table_fingerprints(source)
            run([binary/('pg_dump'+extension),'-h',connect['host'],'-p',connect['port'],'-U',connect['user'],'-d',connect['dbname'],'-Fc','--snapshot',snapshot,'-f',dump],env=env)
        run([binary/('pg_restore'+extension),'--list',dump])
        report.update(dump_file=dump.name,dump_sha256=hashlib.sha256(dump.read_bytes()).hexdigest(),bytes=dump.stat().st_size,tables=expected)
        if args.verify_restore:report.update(verify_restore(binary,dump,expected,destination))
        report['status']='completed'
        (destination/f'backup-{stamp}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        # Retain at least seven verified snapshots; prune only our older verified pairs.
        verified=[]
        for path in destination.glob('backup-*.json'):
            try:
                meta=json.loads(path.read_text())
                if meta.get('restore_verified'):verified.append(path)
            except (OSError,ValueError):pass
        for path in sorted(verified,reverse=True)[7:]:
            if datetime.fromtimestamp(path.stat().st_mtime,timezone.utc)<datetime.now(timezone.utc)-timedelta(days=30):
                dump_path=path.with_suffix('.dump');dump_path.resolve().relative_to(destination.resolve())
                dump_path.unlink(missing_ok=True);path.unlink()
        return 0
    except Exception as error:
        report['error']=str(error) if isinstance(error,RuntimeError) else type(error).__name__
        return 1
    finally:
        (destination/'last_run.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        if sys.stdout:print(json.dumps({key:value for key,value in report.items() if key!='tables'},indent=2))
        lock.close()


if __name__=='__main__':sys.exit(main())
