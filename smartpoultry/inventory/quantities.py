"""Sum explicit physical quantities by unit, never adding sacks to kilograms."""
from collections import defaultdict
from decimal import Decimal


def measurement_totals(items):
    totals=defaultdict(Decimal)
    for item in items:
        unit=item.measurement_unit.strip()
        totals[unit]+=Decimal(str(item.measurement_quantity))
    return [{'unit':unit,'quantity':quantity} for unit,quantity in sorted(totals.items())]
