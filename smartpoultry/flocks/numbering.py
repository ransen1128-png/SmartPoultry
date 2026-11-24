"""Server-side Flock ID numbering: one sequence per branch (01, 02, ... 99, 100, ...).

Displayed Flock IDs are unique only within a branch; the primary key identifies a flock everywhere else.
"""
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Flock, FlockIdSequence, numeric_flock_id


def format_flock_id(number):
    return f'{number:02d}'


def next_flock_id(user_id, branch_id):
    """Return the next unused Flock ID for this account's branch (None = main branch).

    Must run inside the transaction that saves the flock. The account row lock serializes
    concurrent creates and branch moves for one account; Flock.save then records the number.
    """
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError('next_flock_id must be called inside transaction.atomic().')
    lock_account_numbering(user_id)
    sequence = FlockIdSequence.objects.select_for_update().filter(user_id=user_id, branch_id=branch_id).first()
    used = Flock.objects.filter(user_id=user_id, branch_id=branch_id).values_list('flock_id', flat=True)
    # Existing numeric IDs cover rows saved without the counter (older data or bulk inserts).
    highest = max((numeric_flock_id(value) or 0 for value in used), default=0)
    return format_flock_id(max(sequence.last_number if sequence else 0, highest) + 1)


def lock_account_numbering(user_id):
    """Take the same lock as next_flock_id so moves between branches cannot race a create."""
    list(get_user_model().objects.select_for_update().filter(pk=user_id).values_list('pk', flat=True))
