"""Expenses browser test CASE-107."""

from tools.expenses_browser import ExpensesBrowserCase


class ExpensesCase107(ExpensesBrowserCase):
    def test_case_107_return_requires_branch(self):
        self.open_expenses()
        self.fill_egg_return(branch=False)
        self.page.get_by_role('button', name='Save Return', exact=True).click()
        self.assert_native_error('#returnBranch', 'valueMissing', 'Please select an item in the list.')
        self.assert_no_expenses()
