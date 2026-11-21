"""November 2026 fixtures for the ML Predictions browser cases."""

from datetime import date
from unittest.mock import patch

from playwright.sync_api import expect

from expenses.models import Expense
from production.models import ProductionRecord
from revenue.models import Revenue
from tools.feed_inventory_browser import FeedInventoryBrowserCase


class NovemberFinancialBrowserCase(FeedInventoryBrowserCase):
    def setUp(self):
        super().setUp()
        recorded_on = date(2026, 11, 21)
        self.enterContext(patch('core.views.timezone.localdate', return_value=recorded_on))
        eggs = ProductionRecord.objects.create(
            user=self.user, branch=self.branch, flock=self.flock, product_type='eggs',
            egg_size='medium', quantity=14, unit='eggs', date=recorded_on,
        )
        Revenue.objects.create(
            user=self.user, production=eggs, quantity=4, price_per_unit=8, date=recorded_on,
        )
        Revenue.objects.create(
            user=self.user, branch=self.branch, revenue_type='meat', quantity=2,
            price_per_unit=150, date=recorded_on,
        )
        for expense_type, description, amount in (
            ('feed', 'Feed purchase', 5000), ('utilities', 'Utilities', 350), ('return_eggs', 'Egg return', 8),
        ):
            details = {'return_quantity': 1, 'return_unit': 'pcs'} if expense_type == 'return_eggs' else {}
            Expense.objects.create(
                user=self.user, branch=self.branch, expense_type=expense_type,
                description=description, amount=amount, date=recorded_on, **details,
            )


class MLPredictionsBrowserCase(NovemberFinancialBrowserCase):
    forecast_months = ['Dec 2026', 'Jan 2027', 'Feb 2027', 'Mar 2027', 'Apr 2027', 'May 2027']

    def setUp(self):
        super().setUp()
        self.page.get_by_role('link', name='ML Predictions').click()
        expect(self.page).to_have_url(f'{self.live_server_url}/analytics/')
        expect(self.page.get_by_role('heading', name='Analytics & Predictions')).to_be_visible()

    def plotted_data(self, chart_id):
        expect(self.page.locator(f'canvas#{chart_id}')).to_be_visible()
        self.page.wait_for_function('id => Boolean(window.Chart?.getChart(id))', arg=chart_id)
        return self.page.evaluate('''id => {
            const {labels, datasets} = window.Chart.getChart(id).data;
            return {labels, series: Object.fromEntries(datasets.map(series => [series.label, series.data]))};
        }''', chart_id)

    def november_actual_row(self, record_type):
        expect(self.page.get_by_role('heading', name='Actual Recorded Values')).to_be_visible()
        return self.page.get_by_role('row').filter(
            has=self.page.get_by_role('cell', name=record_type, exact=True),
        ).filter(has=self.page.get_by_role('cell', name='Nov 2026', exact=True))
