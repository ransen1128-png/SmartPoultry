"""Idempotent backfill for known branch distributions, never a second purchase."""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.core.exceptions import ValidationError
from inventory.models import Inventory
from inventory.expense_allocation import allocate_distribution


class Command(BaseCommand):
    help='Review historical inventory distributions; --apply allocates verified purchase cost to their recorded branches.'

    def add_arguments(self, parser):
        parser.add_argument('--apply',action='store_true')

    def handle(self,*args,**options):
        count=0
        pending=0
        ids=Inventory.objects.filter(distributions__isnull=False,distributions__expense__isnull=True).values_list('pk',flat=True).distinct()
        for pk in ids:
            try:
                with transaction.atomic():
                    inventory=Inventory.objects.select_for_update().get(pk=pk)
                    distributions=list(inventory.distributions.filter(expense__isnull=True,reversed_at__isnull=True).order_by('date','pk'))
                    for distribution in distributions:
                        allocate_distribution(distribution,inventory)
                    count+=len(distributions)
                    if not options['apply']: transaction.set_rollback(True)
            except ValidationError as error:
                pending+=1
                self.stdout.write(f'Inventory #{pk} needs purchase review: {error}')
        self.stdout.write(f'{"Applied" if options["apply"] else "Verified (dry run)"}: {count} distribution(s). Items needing review: {pending}.')
