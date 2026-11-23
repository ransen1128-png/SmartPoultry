"""SmartPoultry integration INT-007 (CASE-191)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['191', *sys.argv[1:]]))

from tools.expenses_browser import ExpensesBrowserCase
import Expenses_CASE_124 as workflow_1


class IntegrationCase191(ExpensesBrowserCase):
    def test_int_007(self):
        workflow_1.ExpensesCase124.test_case_124_egg_return_does_not_restore_production_stock(self)
        self.open_expenses()
        self.assert_total(8)
