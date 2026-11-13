"""Allocate paid purchase cost to branches without charging the purchase twice.

Caller holds the inventory row lock inside a transaction. Purchase dates remain
the financial dates; distribution dates and prices are retained in the audit.
"""
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.db.models import Sum
from expenses.models import Expense


def allocate_distribution(distribution, inventory):
    existing=Expense.objects.filter(inventory_distribution=distribution).first()
    if existing:
        return existing
    purchase=Expense.objects.select_for_update(of=('self',)).filter(inventory_purchase=inventory).order_by('pk').first()
    if purchase is None or inventory.purchase_cost_per_unit is None or inventory.purchase_cost_per_unit < 0:
        raise ValidationError({'inventory':'The original purchase expense/cost needs reconciliation before distributing this item.'})
    allocated=Expense.objects.filter(inventory_distribution__inventory=inventory,inventory_distribution__reversed_at__isnull=True)
    previous_quantity=allocated.aggregate(total=Sum('inventory_distribution__quantity'))['total'] or Decimal('0')
    previous_amount=allocated.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    amount=max(Decimal('0'),((previous_quantity+distribution.quantity)*inventory.purchase_cost_per_unit).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)-previous_amount)
    if amount>purchase.amount:
        raise ValidationError({'quantity':'Distribution cost exceeds the remaining purchase expense. Review the original purchase.'})
    purchase.amount-=amount
    purchase.save(update_fields=['amount','updated_at'])
    expense=Expense.objects.create(user=distribution.user,branch=distribution.branch,
        inventory_distribution=distribution,expense_type=purchase.expense_type,
        description=f'Distributed {inventory.name} to {distribution.branch.name}'[:255],
        amount=amount,date=purchase.date,category='inventory_distribution',
        notes=f'Distribution #{distribution.pk}; inventory #{inventory.pk}; '
              f'{distribution.quantity} {inventory.unit} at {inventory.purchase_cost_per_unit} each; '
              f'distributed {distribution.date}. Allocated from purchase expense #{purchase.pk}; not an additional payment.')
    type(distribution).objects.filter(pk=distribution.pk).update(cost_snapshot=amount)
    distribution.cost_snapshot=amount
    return expense


def reverse_allocation(distribution, inventory, preserve=False):
    expense=Expense.objects.select_for_update(of=('self',)).filter(inventory_distribution=distribution).order_by('pk').first()
    if expense:
        purchase=Expense.objects.select_for_update(of=('self',)).filter(inventory_purchase=inventory).order_by('pk').first()
        if purchase is None:
            raise ValidationError({'inventory':'Restore/reconcile the purchase expense before reversing this distribution.'})
        purchase.amount+=expense.amount
        purchase.save(update_fields=['amount','updated_at'])
        if preserve:
            expense.amount=Decimal('0')
            expense.notes+=f' Reversed distribution #{distribution.pk} by account #{distribution.reversed_by_id}: {distribution.reversal_reason}; assigned cost restored to purchase balance.'
            expense.save(update_fields=['amount','notes','updated_at'])
        else:
            expense.delete()
