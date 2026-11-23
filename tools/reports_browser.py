"""Shared November 2026 fixtures for the Reports browser cases."""

from datetime import date, datetime, timezone
from unittest.mock import patch

from playwright.sync_api import expect

from expenses.models import Expense
from reports.models import Report
from tools.feed_inventory_browser import FeedInventoryBrowserCase


class NovemberExpenseBrowserCase(FeedInventoryBrowserCase):
    branch_name = 'QA Sample Branch'

    def setUp(self):
        super().setUp()
        self.today = date(2026, 11, 21)
        self.enterContext(patch('django.utils.timezone.localdate', return_value=self.today))
        self.page.clock.set_fixed_time(datetime(2026, 11, 21, 12, tzinfo=timezone.utc))
        self.distribution = self.distribution_fixture()
        for expense_type, description, amount in (
            ('utilities', 'QA utilities', 350), ('return_eggs', 'QA returned egg', 8),
        ):
            details = {'return_quantity': 1, 'return_unit': 'pcs'} if expense_type == 'return_eggs' else {}
            Expense.objects.create(
                user=self.user, branch=self.branch, expense_type=expense_type,
                description=description, amount=amount, date=self.today, **details,
            )


class ReportsBrowserCase(NovemberExpenseBrowserCase):
    def setUp(self):
        super().setUp()
        self.page.get_by_role('link', name='Reports').click()
        expect(self.page).to_have_url(f'{self.live_server_url}/reports/')
        expect(self.page.locator('#branchExpenseTotal')).to_have_text('\u20b15358.00')

    def fill_expense_filter(self, branch, *, start='2026-11-01', end='2026-11-21'):
        self.page.get_by_label('Branch', exact=True).select_option(label=branch)
        self.page.get_by_label('From', exact=True).fill(start)
        self.page.get_by_label('To', exact=True).fill(end)
    def apply_expense_filter(self, branch):
        self.fill_expense_filter(branch)
        with self.page.expect_response(lambda response: '/api/reports/branch-expenses/?' in response.url) as result:
            self.page.get_by_role('button', name='Apply Filter', exact=True).click()
        return result.value

    def assert_expense_total(self, amount):
        expect(self.page.locator('#branchExpenseTotal')).to_have_text(f'\u20b1{amount}.00')

    def generate_monthly_report(self):
        with self.page.expect_response(
            lambda response: response.url.endswith('/api/reports/') and response.request.method == 'POST',
        ) as saved:
            self.page.get_by_role('button', name='Monthly', exact=True).click()
        self.assertEqual(saved.value.status, 201, saved.value.text())
        return Report.objects.get(pk=saved.value.json()['id'], user=self.user)

    def generated_report_row(self, report):
        return self.page.locator('#reportsBody tr').filter(
            has=self.page.get_by_role('cell', name=report.title, exact=True),
        )
