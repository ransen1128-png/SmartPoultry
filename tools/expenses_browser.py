"""Shared browser fixtures for the Expenses cases."""

from playwright.sync_api import expect

from expenses.models import Expense
from production.models import ProductionRecord
from revenue.models import Revenue
from tools.feed_inventory_browser import FeedInventoryBrowserCase


class ExpensesBrowserCase(FeedInventoryBrowserCase):
    branch_name = 'QA Sample Branch'
    utilities_description = 'QA Branch electricity bill'
    return_reason = 'QA returned egg'

    def open_expenses(self):
        self.page.goto(f'{self.live_server_url}/expenses/')
        expect(self.page.get_by_role('heading', name='Expenses Tracking')).to_be_visible()

    def fill_expense(self, *, blank=None):
        self.page.get_by_role('button', name='Add Expense').click()
        form = self.page.locator('#addExpenseForm')
        if blank != 'branch':
            form.locator('[name="branch"]').select_option(label=self.branch.name)
        form.locator('[name="expense_type"]').select_option('utilities')
        for name, value in (
            ('description', self.utilities_description), ('amount', '350'), ('date', self.today.isoformat()),
        ):
            form.locator(f'[name="{name}"]').fill('' if name == blank else value)

    def fill_egg_return(self, *, branch=True, quantity='1', amount='8'):
        self.page.get_by_role('button', name='Add Return', exact=True).click()
        if branch:
            self.page.locator('#returnBranch').select_option(label=self.branch.name)
        self.page.locator('#returnType').select_option('return_eggs')
        self.page.locator('#returnDate').fill(self.today.isoformat())
        self.page.locator('#returnReason').fill(self.return_reason)
        self.page.locator('#returnQuantity').fill(quantity)
        self.page.locator('#returnAmount').fill(amount)

    def save_expense(self, button):
        with self.page.expect_response(
            lambda response: response.url.endswith('/api/expenses/') and response.request.method == 'POST',
        ) as saved:
            self.page.get_by_role('button', name=button, exact=True).click()
        self.assertEqual(saved.value.status, 201, saved.value.text())
        return Expense.objects.get(pk=saved.value.json()['id'], user=self.user)

    def expense_row(self, description):
        return self.page.locator('#expensesBody tr').filter(
            has=self.page.get_by_role('cell', name=description, exact=True),
        )

    def assert_total(self, amount):
        expect(self.page.locator('#totalExpenses')).to_have_text(f'\u20b1{amount}.00')

    def assert_no_expenses(self):
        self.assertFalse(Expense.objects.filter(user=self.user).exists())
        self.assert_total(0)

    def sold_egg_fixture(self):
        record = ProductionRecord.objects.create(
            user=self.user, branch=self.branch, flock=self.flock,
            product_type='eggs', egg_size='medium', quantity=14, date=self.today,
        )
        Revenue.objects.create(
            user=self.user, production=record, quantity=4, price_per_unit=8,
            date=self.today, buyer_name='QA Egg Buyer',
        )
        self.assertEqual(record.available_quantity, 10)
        return record
