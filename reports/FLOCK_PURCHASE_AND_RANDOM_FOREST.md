# Flock purchase expenses and Random Forest forecasting

Implemented and verified locally on 2026-11-14. No GitHub push or Render deployment was performed.

## Flock purchase expenses

The Add/Edit Flock form now has a source selector:

- **Bought / delivered:** enter the total bird purchase cost, optional delivery fee, purchase date and optional supplier. One linked **Flock Purchase** expense is created for the flock's branch, equal to purchase cost plus delivery fee.
- **Raised on my farm:** no bird-purchase expense is created. Feed, medicine and other genuine operating costs remain recorded separately.
- Existing flocks retain **Not recorded** until their actual source is supplied; no historical purchases or source identities were invented.

The cost is fixed to the entered purchase amount, rather than multiplied by the flock's remaining live quantity. Mortality, production transfers and sales do not erase the original cost. Editing purchase details updates the same expense instead of adding duplicates. Correcting a flock to own-raised changes its linked purchase expense to zero while preserving the expense and transaction audit history. Linked purchase expenses cannot be edited/deleted independently, and purchased flocks retain their financial history.

The local migration was applied only after a PostgreSQL backup was restored successfully into an isolated cluster and all saved table contents matched. Migrations: `flocks/0008_flock_acquisition_source_flock_delivery_cost_and_more`, `expenses/0006_expense_flock_purchase_alter_expense_expense_type`.

## Random Forest

The branch forecasting service now uses scikit-learn's actual [RandomForestRegressor](https://scikit-learn.org/1.3/modules/generated/sklearn.ensemble.RandomForestRegressor.html) instead of the previous trend extrapolation. Models train separately for each account, branch and target (revenue, expenses and egg production). Expected profit is forecast revenue minus forecast expense. Feed demand remains the explicitly labeled live-bird consumption assumption; it is not presented as a trained forest output.

Training uses recorded completed months from the previous 24 calendar months. It does not turn unrecorded months into fabricated zero labels, and it excludes the current partial month. Features use previous recorded values, recent averages, calendar month and elapsed time. Seed 2026, 80 trees and depth 4 make repeated runs reproducible. Model outputs are cached only for the same scope and exact observations.

The application requires at least **four completed recorded months** per target so it can reserve the latest observed month for validation before refitting on all eligible observations. This is an application readiness rule, not a universal requirement of Random Forest. [Time-ordered evaluation](https://scikit-learn.org/1.3/modules/cross_validation.html#time-series-split) avoids training on future observations. The page reports held-out MAE and a previous-value baseline. One held-out month provides limited evidence, not an accuracy guarantee or a confidence percentage.

The actual desktop forecasting history was inspected: the current three branches have insufficient completed monthly target history. **Zero live branch models were reported trained.** Their unavailable forecasts show a dash and an explicit readiness message. No fake business records, random forecast numbers or silent trend fallbacks were introduced. Random Forest fitting/prediction itself was executed and validated in isolated tests using clearly separate test fixtures. Genuine earlier dated records, if available, can supply the missing history; historical months must not be fabricated.

## Executed verification

- 34 flock, inventory and revenue tests passed, including purchase/own sources, delivery cost, branch assignment, corrections, no duplicate charges and unchanged purchase cost after mortality/production.
- Eight Random Forest/branch forecasting tests passed, including actual model fitting, reproducibility, time-ordered validation, no current-month leakage, sparse-history blocking and branch/account isolation.
- Real PostgreSQL API checks verified purchased-versus-own expenses. Temporary verification records were rolled back.
- Real Chrome at desktop/mobile widths verified the purchase form's source/field toggles and Random Forest readiness display without submitting any real flock changes.
- Django checks and migration consistency checks passed; the local server was restarted with the new code.
