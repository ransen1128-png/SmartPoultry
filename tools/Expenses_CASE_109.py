"""Expenses browser test CASE-109."""

from tools.expenses_browser import ExpensesBrowserCase


class ExpensesCase109(ExpensesBrowserCase):
    def test_case_109_negative_return_amount_is_rejected(self):
        self.open_expenses()
        self.fill_egg_return(amount='-1')
        self.page.get_by_role('button', name='Save Return', exact=True).click()
        self.assert_native_error(
            '#returnAmount', 'rangeUnderflow', 'Value must be greater than or equal to 0.',
        )
        self.assert_no_expenses()
