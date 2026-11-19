from django.core.management.base import BaseCommand
from notifications.readiness import notify_ready_flocks


class Command(BaseCommand):
    help='Create one in-app readiness notification per broiler flock and placement date.'
    def handle(self,*args,**options):self.stdout.write(f'Created {notify_ready_flocks()} readiness notifications.')
