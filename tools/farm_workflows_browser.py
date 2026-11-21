"""Shared fixtures for Dashboard, Farms, and Flocks coverage cases."""

from datetime import date
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect

from core.models import Branch
from production.models import ProductionRecord
from revenue.models import Revenue
from tools.feed_inventory_browser import FeedInventoryBrowserCase
from tools.reports_browser import NovemberExpenseBrowserCase


class DashboardWorkflowCase(NovemberExpenseBrowserCase):
    def setUp(self):
        super().setUp()
        self.flock.quantity = 47
        self.flock.save(update_fields=['quantity'])
        ProductionRecord.objects.create(
            user=self.user, branch=self.branch, flock=self.flock, product_type='eggs',
            egg_size='medium', quantity=14, date=self.today,
        )
        for product, quantity, price in (('eggs', 4, 8), ('meat', 2, 150)):
            Revenue.objects.create(
                user=self.user, branch=self.branch, revenue_type=product, quantity=quantity,
                price_per_unit=price, date=self.today,
            )
        self.page.goto(f'{self.live_server_url}/dashboard/')

    def apply_dashboard(self, month, branch=None):
        filters = self.page.locator('.dashboard-filters')
        selection = filters.get_by_label('Farm branch', exact=True)
        branch_id = str(branch.pk) if branch else ''
        if selection.input_value() != branch_id:
            with self.page.expect_navigation(wait_until='domcontentloaded'):
                selection.select_option(branch_id)
        filters.get_by_label('Month', exact=True).select_option(str(month))
        filters.get_by_label('Year', exact=True).select_option('2026')
        with self.page.expect_navigation(wait_until='domcontentloaded'):
            filters.get_by_role('button', name='Apply', exact=True).click()
        self.assertEqual(parse_qs(urlsplit(self.page.url).query, keep_blank_values=True), {
            'branch': [branch_id], 'month': [str(month)], 'year': ['2026'],
        })

    def expect_metric(self, label, value):
        card = self.page.locator('.metric-card').filter(has=self.page.get_by_text(label, exact=True))
        expect(card).to_be_visible()
        expect(card.locator('strong')).to_have_text(value)


class FarmWorkflowCase(FeedInventoryBrowserCase):
    seed_branch = False
    branch_name = 'QA Sample Branch'
    branch_address = '125 QA Farm Road, Quezon City'

    def open_farms(self):
        self.page.goto(f'{self.live_server_url}/farm/branches/')
        expect(self.page.get_by_role('heading', name='Farm', exact=True)).to_be_visible()

    def sample_branch(self):
        return Branch.objects.create(farm=self.farm, name=self.branch_name, address=self.branch_address)

    def search_farms(self, query):
        self.page.get_by_role('searchbox', name='Search farm and branches').fill(query)
        self.page.get_by_role('button', name='Search', exact=True).click()


class FlockWorkflowCase(FeedInventoryBrowserCase):
    branch_name = 'QA Sample Branch'

    def setUp(self):
        super().setUp()
        self.enterContext(patch('django.utils.timezone.localdate', return_value=date(2026, 11, 21)))
        self.page.goto(f'{self.live_server_url}/flocks/')
        expect(self.page.get_by_role('heading', name='Current Flocks', exact=True)).to_be_visible()

    def fill_flock(self, breed, quantity='30'):
        self.page.get_by_role('button', name='Add New Flock').click()
        modal = self.page.locator('#addFlockModal')
        form = modal.locator('#addFlockForm')
        form.locator('[name="branch"]').select_option(label=self.branch.name)
        form.locator('[name="breed"]').select_option(breed)
        form.locator('[name="acquisition_source"]').select_option('own')
        form.locator('[name="quantity"]').fill(quantity)
        form.locator('[name="status"]').select_option('active')
        expect(form.get_by_label('Flock ID', exact=True)).to_have_value('')
        return modal

    def save_new_flock(self, modal):
        with self.page.expect_response(
            lambda response: response.url.endswith('/api/flocks/') and response.request.method == 'POST',
        ) as saved:
            modal.get_by_role('button', name='Save Flock', exact=True).click()
        self.assertEqual(saved.value.status, 201, saved.value.text())
        result = saved.value.json()
        self.assertEqual(result['flock_id'], '02')
        expect(modal).to_be_hidden()
        return result

    def flock_row(self, flock_id):
        return self.page.locator('#flocksBody tr').filter(
            has=self.page.get_by_role('cell', name=flock_id, exact=True),
        )
