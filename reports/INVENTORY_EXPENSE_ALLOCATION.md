# Inventory distribution expense tracking

Implemented and verified locally on 2026-11-13. Not deployed to Render in this session.

## Result

Distributing feed, medicine, equipment or other inventory now assigns its recorded purchase cost to the receiving branch in Expenses. The same transaction reduces stock and allocates cost; a failure rolls back both. Distribution history shows the receiving branch, distribution date, quantity, original unit price and assigned cost. Expenses shows the branch, item description and distribution date.

An inventory purchase already creates an expense. To avoid charging it twice, each distribution transfers part of that existing expense to a branch expense. The balance stays unassigned until distributed. For example, a 100 kg purchase costing PHP 5,000 followed by a 20 kg distribution assigns PHP 1,000 to that branch and leaves PHP 4,000 unassigned. Total farm expense remains PHP 5,000.

Financial entries retain the original purchase date, preserving monthly expense/cash-flow totals. The separate **Date Distributed** field records when the branch received the items. Allocations use the frozen purchase price, so later inventory price changes do not rewrite historical cost. Cumulative penny rounding prevents several small distributions from creating extra cost.

Inventory-linked expenses cannot be edited or deleted independently through the expense API. Distribution records are immutable through the existing API. Server-side distribution reversal restores both stock and cost. Expense transaction audit metadata includes branch and distribution references, and notes retain quantity, price and source purchase details. All expense pages now load subsequent API pages so older distributions remain visible.

## Historical records

A schema/data migration links an older inventory item to its original expense only if exactly one matching system-generated purchase exists, belongs to the same owner, has no assigned branch, matches the item type and agrees with the complete recorded stock ledger at the recorded unit price. Ambiguous purchases remain unlinked; their cost is not invented.

On the desktop PostgreSQL database, **2 existing distributions** were verified and allocated to their recorded branches. No purchase cost, date, account or stock quantity was lost. A repeat backfill made no changes. A private PostgreSQL dump was saved before migration under `.database-backups/before-distribution-costs-20261113T184627.dump`.

For another deployment, apply migrations and review existing distributions:

```text
python manage.py migrate --noinput
python manage.py allocate_distribution_expenses
python manage.py allocate_distribution_expenses --apply
```

The command defaults to a dry run and reports inventories requiring purchase review. `--apply` processes verified distributions atomically per inventory and is safe to repeat. Newly created distributions allocate their expense immediately without this command.

## Verification

- 17 focused inventory, dashboard, expense-audit and distribution tests passed, followed by a passing rounding/reversal regression check.
- Actual PostgreSQL API requests verified purchase creation, branch assignment, exact cost, unchanged farm totals and independent-deletion protection. All temporary verification records were rolled back.
- Before/after comparisons of the desktop database confirmed unchanged account count, stock, distribution count and expense totals for each owner and purchase date.
- Real Chrome at desktop and mobile widths verified expense branch assignments, cost columns, protected rows, no horizontal page overflow and no JavaScript exceptions.
