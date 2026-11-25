"""Shared fixtures for the Forecasting browser cases."""

from tools.automation_browser import expect


from expenses.models import Expense
from production.models import ProductionRecord
from revenue.models import Revenue
from tools.feed_inventory_browser import FeedInventoryBrowserCase


class ForecastingBrowserCase(FeedInventoryBrowserCase):
    branch_name = 'QA Sample Branch'

    def record_month(self, recorded_on):
        Revenue.objects.create(
            user=self.user, branch=self.branch, revenue_type='eggs', quantity=4,
            price_per_unit=8, date=recorded_on,
        )
        Expense.objects.create(
            user=self.user, branch=self.branch, expense_type='feed',
            description='QA feed expense', amount=20, date=recorded_on,
        )
        ProductionRecord.objects.create(
            user=self.user, branch=self.branch, flock=self.flock, product_type='eggs',
            egg_size='medium', quantity=14, date=recorded_on,
        )

    def open_forecasting(self):
        self.page.get_by_role('link', name='Forecasting').click()
        expect(self.page).to_have_url(f'{self.live_server_url}/forecasting/')
        expect(self.page.get_by_role('heading', name='Forecasting', exact=True)).to_be_visible()

    def apply_branch(self, branch):
        selection = self.page.get_by_label('Branch', exact=True)
        branch_id = str(branch.pk) if branch else ''
        url = f'{self.live_server_url}/forecasting/?branch={branch_id}'
        selection.select_option(branch_id)
        expect(self.page).to_have_url(url)
        with self.page.expect_navigation(wait_until='domcontentloaded'):
            self.page.get_by_role('button', name='Apply', exact=True).click()
        expect(self.page).to_have_url(url)
        expect(selection).to_have_value(branch_id)

    def metric(self, label):
        return self.page.locator('.metric-card').filter(has=self.page.get_by_text(label, exact=True))

    def assert_readiness(self, completed_months):
        readiness = self.page.locator('.model-readiness')
        expect(readiness.get_by_role('heading', name='Model Readiness', exact=True)).to_be_visible()
        for name in ('revenue', 'expenses', 'production'):
            card = readiness.locator(f'[data-model="{name}"]')
            expect(card.locator('.readiness-status')).to_have_text('Not Ready')
            expect(card).to_contain_text(f'Insufficient Data ({completed_months}/4 months)')
