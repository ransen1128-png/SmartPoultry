"""Expenses browser test CASE-118."""

import sys

if __name__ == "__main__":
    from run_automation import main

    raise SystemExit(main(["118", *sys.argv[1:]]))

from tools.expenses_browser import ExpensesBrowserCase


class ExpensesCase118(ExpensesBrowserCase):
    def test_case_118_return_requires_branch(self):
        self.open_expenses()
        self.fill_egg_return(branch=False)
        self.page.get_by_role('button', name='Save Return', exact=True).click()
        self.assert_native_error('#returnBranch', 'valueMissing')
        self.assert_no_expenses()
