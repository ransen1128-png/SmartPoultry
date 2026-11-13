"""Record/compare account identity across a real deploy using read-only SQL.
Password comes from PGPASSWORD, never arguments or output. No accounts are made.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime,timezone
import psycopg2


def snapshot(connection,email):
    with connection.cursor() as cursor:
        cursor.execute('SHOW transaction_read_only')
        if cursor.fetchone()[0]!='on':raise RuntimeError('Read-only connection required')
        cursor.execute('SELECT current_database()');database=cursor.fetchone()[0]
        cursor.execute('SELECT id,username,email,date_joined,password,is_active FROM accounts_userprofile WHERE lower(email)=lower(%s)',(email,))
        rows=cursor.fetchall()
        if len(rows)!=1:raise RuntimeError(f'Expected exactly one matching account; found {len(rows)}')
        pk,username,address,joined,password,active=rows[0]
        cursor.execute('SELECT count(*) FROM accounts_userprofile');count=cursor.fetchone()[0]
    return {'database':database,'account_id':pk,'username':username,'email':address,'date_joined':joined.astimezone(timezone.utc).isoformat(),
        'credential_fingerprint':hashlib.sha256(password.encode()).hexdigest(),'active':active,'total_accounts':count}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True)
    parser.add_argument('--database',required=True)
    parser.add_argument('--user',required=True)
    parser.add_argument('--email',required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--record',action='store_true',help='Record initial baseline; refuses overwriting it.')
    args=parser.parse_args()
    with psycopg2.connect(host=args.host,dbname=args.database,user=args.user,password=os.environ.get('PGPASSWORD'),
            sslmode='require',connect_timeout=10,options='-c default_transaction_read_only=on') as connection:
        current=snapshot(connection,args.email)
    if args.record:
        args.baseline.parent.mkdir(parents=True,exist_ok=True)
        with args.baseline.open('x',encoding='utf-8') as target:
            json.dump({'recorded_utc':datetime.now(timezone.utc).isoformat(),'host':args.host,'snapshot':current},target,indent=2)
        print('Live account baseline recorded. A real redeploy must happen before comparing persistence.')
        return 0
    previous=json.loads(args.baseline.read_text())
    if previous['host']!=args.host:raise RuntimeError('Different database host; refusing an invalid comparison')
    original=previous['snapshot']
    identity_fields=('database','account_id','date_joined')
    retained=all(original[key]==current[key] for key in identity_fields)
    result={'same_account_retained':retained,'same_password_hash':original['credential_fingerprint']==current['credential_fingerprint'],
        'login_identifiers_unchanged':all(original[key]==current[key] for key in ('username','email')),
        'active':current['active'],'read_only':True,'note':'This is a redeploy-persistence test only if a real deployment occurred between recording and comparison. Legitimate password changes and hasher upgrades also change the credential fingerprint.'}
    print(json.dumps(result,indent=2))
    return 0 if retained else 2


if __name__=='__main__':raise SystemExit(main())
