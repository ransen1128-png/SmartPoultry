"""Shared browser fixtures for production record cases."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.utils import timezone

try:
    from tools.automation_browser import expect, expect_field_error, launch_browser
except ModuleNotFoundError:
    from automation_browser import expect, expect_field_error, launch_browser

from core.models import Branch, Farm
from flocks.models import Flock
from production.models import ProductionRecord


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ProductionRecordsBrowserCase(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.browser = launch_browser()
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        self.today = timezone.localdate()
        user = get_user_model().objects.create_user('production-qa', 'production-qa@example.invalid', 'Fixture!123')
        farm = Farm.objects.create(owner=user, name='QA Farm', established_date=self.today)
        self.branch = Branch.objects.create(farm=farm, name='Sample Branch')
        other_branch = Branch.objects.create(farm=farm, name='Other Branch')
        self.layers = Flock.objects.create(user=user, branch=self.branch, flock_id='01', breed='layers', quantity=25)
        self.broilers = Flock.objects.create(
            user=user, branch=self.branch, flock_id='02', breed='broilers', quantity=25,
            placement_date=self.today - timedelta(days=30),
        )
        Flock.objects.create(user=user, branch=other_branch, flock_id='03', breed='layers', quantity=25)

        self.page = self.browser.new_page(locale='en-US')
        self.addCleanup(self.page.close)
        self.records_url = f'{self.live_server_url}/production-records/'
        self.page.goto(f'{self.live_server_url}/login/')
        self.page.get_by_label('Email', exact=True).fill(user.email)
        self.page.get_by_label('Password', exact=True).fill('Fixture!123')
        self.page.get_by_role('button', name='Login', exact=True).click()
        expect(self.page).to_have_url(f'{self.live_server_url}/dashboard/')

    def open_add_form(self):
        self.page.goto(self.records_url)
        self.page.locator('.page-heading').get_by_role('link', name='Add Record', exact=True).click()
        expect(self.page).to_have_url(f'{self.records_url}add/')

    def fill_record(self, flock, quantity='12', record_date=None, egg_size='medium'):
        self.open_add_form()
        self.page.locator('#id_branch').select_option(str(self.branch.pk))
        self.page.locator('#id_flock').select_option(str(flock.pk))
        if flock.breed == 'layers':
            self.page.locator('#id_egg_size').select_option(egg_size)
        self.page.locator('#id_quantity').fill(quantity)
        self.page.locator('#id_date').fill(self.today.isoformat() if record_date is None else record_date)

    def submit(self):
        self.page.locator('main form button[type="submit"]').click()

    def assert_required(self, field):
        self.assertTrue(self.page.locator(field).evaluate('input => input.validity.valueMissing'))
        expect_field_error(self.page.locator(field))

    def egg_fixture(self):
        return ProductionRecord.objects.create(
            user=self.layers.user, branch=self.branch, flock=self.layers,
            product_type='eggs', egg_size='medium', quantity=12, date=self.today,
        )

    def open_egg_edit(self, record):
        self.page.goto(self.records_url)
        self.record_row(record).get_by_role('link', name='Edit').click()
        expect(self.page).to_have_url(f'{self.records_url}{record.pk}/edit/')

    def record_row(self, record):
        return self.page.locator(f'#availableProductionTable tr[data-production-id="{record.pk}"]')
