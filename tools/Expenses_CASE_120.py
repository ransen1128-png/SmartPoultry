"""Expenses browser test CASE-120."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["120", *sys.argv[1:]]))

from tools.expenses_browser import ExpensesBrowserCase


class ExpensesCase120(ExpensesBrowserCase):
    def test_case_120_negative_return_amount_is_rejected(self):
        self.open_expenses()
        self.fill_egg_return(amount='-1')
        self.page.get_by_role('button', name='Save Return', exact=True).click()
        self.assert_native_error(
            '#returnAmount', 'rangeUnderflow',
        )
        self.assert_no_expenses()
