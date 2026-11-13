"""Read-only diagnosis; never creates accounts, resets passwords or logs hashes."""
import hashlib
import json
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models import Q


class Command(BaseCommand):
    help='Read-only account/database check for diagnosing rejected logins after deployment.'

    def add_arguments(self,parser):
        parser.add_argument('--email',required=True)

    def handle(self,*args,**options):
        identifier=options['email'].strip()
        user_model=get_user_model()
        matches=user_model.objects.filter(Q(email__iexact=identifier)|Q(username__iexact=identifier))
        database=connection.settings_dict
        identity='|'.join(str(database.get(key,'')) for key in ('ENGINE','HOST','PORT','NAME'))
        report={'backend':connection.vendor,'database_name':str(database['NAME']),
                'connection_identity':hashlib.sha256(identity.encode()).hexdigest()[:20],
                'total_accounts':user_model.objects.count(),'matching_accounts':[
                    {'id':user.pk,'username':user.username,'email':user.email,'is_active':user.is_active,
                     'is_active_user':user.is_active_user,'usable_password':user.has_usable_password(),
                     'date_joined':user.date_joined,'last_login':user.last_login} for user in matches],
                'read_only':True,'note':'A configuration fingerprint is not proof that a database was never reset. Compare account records and deployment history.'}
        self.stdout.write(json.dumps(report,indent=2,default=str))
