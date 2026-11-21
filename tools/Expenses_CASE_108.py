"""Expenses browser test CASE-108."""

from playwright.sync_api import expect

from tools.expenses_browser import ExpensesBrowserCase


class ExpensesCase108(ExpensesBrowserCase):
    def test_case_108_zero_return_quantity_is_rejected(self):
        self.open_expenses()
        self.fill_egg_return(quantity='0')
        quantity = self.page.locator('#returnQuantity')
        expect(quantity).to_have_attribute('min', '0.01')
        self.page.get_by_role('button', name='Save Return', exact=True).click()
        self.assert_native_error(
            '#returnQuantity', 'rangeUnderflow', 'Value must be greater than or equal to 0.01.',
        )
        self.assert_no_expenses()
