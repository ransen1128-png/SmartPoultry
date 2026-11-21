"""Shared browser fixtures for the Revenue cases."""

from datetime import timedelta
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.utils import timezone
from playwright.sync_api import expect, sync_playwright

from core.models import Branch, Farm
from flocks.models import Flock
from production.models import ProductionRecord
from revenue.models import Revenue


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RevenueBrowserCase(StaticLiveServerTestCase):
    buyer = 'QA Revenue Buyer'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The sync Playwright driver owns an event loop while fixture operations run serially.
        cls.enterClassContext(patch.dict(os.environ, DJANGO_ALLOW_ASYNC_UNSAFE='true'))
        playwright = sync_playwright().start()
        cls.addClassCleanup(playwright.stop)
        cls.browser = playwright.chromium.launch(channel='msedge', headless=True)
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        self.today = timezone.localdate()
        email, password = 'revenue-qa@example.invalid', 'Fixture!123'
        self.user = get_user_model().objects.create_user('revenue-qa', email, password)
        farm = Farm.objects.create(owner=self.user, name='QA Farm', established_date=self.today)
        self.branch = Branch.objects.create(farm=farm, name='QA Sample Branch')
        layers = Flock.objects.create(user=self.user, branch=self.branch, flock_id='01', breed='layers', quantity=30)
        broilers = Flock.objects.create(
            user=self.user, branch=self.branch, flock_id='02', breed='broilers', quantity=25,
            placement_date=self.today - timedelta(days=30),
        )
        self.eggs = ProductionRecord.objects.create(
            user=self.user, branch=self.branch, flock=layers, product_type='eggs',
            egg_size='medium', quantity=14, date=self.today,
        )
        self.meat = ProductionRecord.objects.create(
            user=self.user, branch=self.branch, flock=broilers, product_type='meat_ready',
            quantity=5, date=self.today,
        )
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.page.goto(f'{self.live_server_url}/login/')
        self.page.get_by_label('Email', exact=True).fill(email)
        self.page.get_by_label('Password', exact=True).fill(password)
        self.page.get_by_role('button', name='Login', exact=True).click()
        expect(self.page).to_have_url(f'{self.live_server_url}/dashboard/')
        self.page.goto(f'{self.live_server_url}/revenue/')
        self.modal = self.page.locator('#addRevenueModal')
        self.lines = self.modal.locator('.revenue-order-item')

    def open_order(self):
        with self.page.expect_response(lambda response: response.url.endswith('/api/revenue/available-production/')) as stock:
            self.page.get_by_role('button', name='Add Revenue').click()
        self.assertTrue(stock.value.ok, 'Available production could not be loaded')
        expect(self.modal).to_be_visible()

    def select_branch(self):
        self.modal.locator('[name="branch"]').select_option(label=self.branch.name)

    def fill_order_header(self):
        self.select_branch()
        self.modal.get_by_label('Buyer Name', exact=True).fill(self.buyer)
        self.modal.locator('[name="date"]').fill(self.today.isoformat())

    def fill_line(self, index, production, quantity, price):
        line = self.lines.nth(index)
        line.locator('[name="production"]').select_option(str(production.pk))
        line.locator('[name="quantity"]').fill(quantity)
        line.locator('[name="price_per_unit"]').fill(price)
        return line

    def submit(self):
        self.modal.get_by_role('button', name='Save Revenue', exact=True).click()

    def assert_sale_blocked(self, field, flag, validation_message):
        self.assertTrue(field.evaluate('(field, flag) => field.validity[flag]', flag))
        expect(self.page.locator('#appDialog[open] #appDialogText')).to_have_text(validation_message)
        expect(self.modal).to_be_visible()
        self.assertFalse(Revenue.objects.filter(user=self.user).exists())
        self.assertEqual(self.eggs.available_quantity, 14)

    def save_two_item_order(self):
        self.open_order()
        self.fill_order_header()
        self.fill_line(0, self.eggs, '4', '8')
        self.modal.get_by_role('button', name='Add another item').click()
        self.fill_line(1, self.meat, '2', '150')
        expect(self.modal.get_by_label('Order Number', exact=True)).to_have_value('')
        with self.page.expect_response(
            lambda response: response.url.endswith('/api/revenue/order/') and response.request.method == 'POST',
        ) as sale:
            self.submit()
        self.assertEqual(sale.value.status, 201, sale.value.text())
        expect(self.modal).to_be_hidden()
        records = list(Revenue.objects.filter(user=self.user).order_by('pk'))
        self.assertEqual(len(records), 2)
        return records

    def revenue_row(self, record):
        receipt = self.page.locator(f'a[href="/revenue/{record.pk}/receipt/"]')
        return self.page.locator('#revenueBody tr').filter(has=receipt)
