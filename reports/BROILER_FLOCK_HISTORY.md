# Broiler production, sales and Flock History

Implemented locally on 2026-11-14. Not pushed or deployed to Render.

## Behavior

- New **Meat Ready** production recorded as a whole number of broiler birds removes that quantity from the live flock exactly once. Supported individual-bird units include the form's default `units`, birds, head, pieces and pcs.
- Selling the production reduces its available stock, without removing the live birds a second time. Partial production leaves the remaining live birds in the current flock list.
- A flock with zero live birds or a Sold status moves out of **Current Flocks** into **Flocks → History**. Deceased and retired flocks also appear there. The underlying flock, production and sales records are retained.
- Zero-quantity broiler flocks can still have unsold production available in Revenue. When no live birds remain and all their recorded meat stock has been sold, automatically tracked flocks are marked Sold.
- Correcting/deleting a sale restores production availability, not live birds. Correcting/deleting unsold production restores its applied live-bird movement. The automatic Sold marker is reversed when appropriate; manually closed/inactive flocks are not automatically reopened.
- Current dashboard flock counts exclude zero-quantity flocks. New production/mortality selectors exclude empty flocks; inventory cannot be assigned to a flock with no live birds. History remains available only to the owning account.

## Existing production records

Older production records lack reliable evidence that their bird count has already been removed manually from the live quantity. Their stock counts were therefore not silently rewritten. The new **Apply bird count to flock** link in Production Records opens a review page for compatible entries. The owner confirms that those recorded birds are still included in the live flock count before applying the movement. The action is transactional and repeat-safe, and records the confirmation in the production notes.

Entries whose recorded bird count exceeds the current live flock quantity need review rather than an invented adjustment. Kilograms and other weight measurements are not converted into bird counts. Existing production/sales values are preserved.

## Validation

A complete PostgreSQL backup was restored and checked before the two schema migrations. New fields default to zero/false; no historical bird quantities were automatically changed by migration. Stock changes lock production and flock rows, reject fractional/excess individual-bird quantities, and preserve the source movement applied by each production record. Recorded sales cannot be moved to a different production batch through editing.

The production/revenue/form/dashboard/inventory regression suite passed. Real PostgreSQL API checks verified production, full and partial sales, corrections, unsold-production deletion and repeat-safe legacy confirmation; all temporary records were rolled back. Chrome at desktop and mobile widths verified current/history separation, the History toggle and the legacy confirmation page, with no JavaScript exceptions or page overflow. No real flock was changed during browser checks.

Relevant migration files: `flocks/0007_flock_auto_sold` and `production/0006_productionrecord_birds_removed`. The local migrations are applied and the local server has been restarted.
