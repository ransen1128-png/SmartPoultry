"""Shared browser fixtures for mortality record cases."""

import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.utils import timezone
from playwright.sync_api import expect, sync_playwright

from core.models import Branch, Farm
from flocks.models import Flock
from production.models import MortalityRecord


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class MortalityRecordsBrowserCase(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The sync Playwright driver keeps an event loop on the test thread.
        cls.enterClassContext(patch.dict(os.environ, DJANGO_ALLOW_ASYNC_UNSAFE='true'))
        playwright = sync_playwright().start()
        cls.addClassCleanup(playwright.stop)
        cls.browser = playwright.chromium.launch(channel='msedge', headless=True)
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        self.today = timezone.localdate()
        email = 'mortality-qa@example.invalid'
        password = 'Fixture!123'
        self.user = get_user_model().objects.create_user('mortality-qa', email, password)
        farm = Farm.objects.create(owner=self.user, name='QA Farm', established_date=self.today)
        self.branch = Branch.objects.create(farm=farm, name='Sample Branch')
        self.flock = Flock.objects.create(
            user=self.user, branch=self.branch, flock_id='01', breed='layers', quantity=30,
        )
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.records_url = f'{self.live_server_url}/mortality-records/'
        self.page.goto(f'{self.live_server_url}/login/')
        self.page.get_by_label('Email', exact=True).fill(email)
        self.page.get_by_label('Password', exact=True).fill(password)
        self.page.get_by_role('button', name='Login', exact=True).click()
        expect(self.page).to_have_url(f'{self.live_server_url}/dashboard/')

    def open_add_form(self):
        self.page.goto(self.records_url)
        self.page.get_by_role('link', name='Add Record').click()
        expect(self.page).to_have_url(f'{self.records_url}add/')

    def fill_add_form(self, *, branch=True, flock=True, quantity='2', date=None):
        self.open_add_form()
        if branch:
            self.page.locator('#id_branch').select_option(str(self.branch.pk))
        if flock:
            self.page.locator('#id_flock').select_option(str(self.flock.pk))
        self.page.locator('#id_quantity').fill(quantity)
        self.page.locator('#id_date').fill(self.today.isoformat() if date is None else date)

    def submit(self):
        self.page.locator('main form button[type="submit"]').click()

    def assert_required(self, selector, message):
        field = self.page.locator(selector)
        self.assertTrue(field.evaluate('input => input.validity.valueMissing'))
        dialog = self.page.locator('#appDialog[open]')
        expect(dialog.get_by_role('heading', name='Please Complete All Required Fields!')).to_be_visible()
        expect(dialog.locator('#appDialogText')).to_have_text(message)

    def assert_no_record_saved(self):
        expect(self.page).to_have_url(f'{self.records_url}add/')
        self.assertFalse(MortalityRecord.objects.filter(user=self.user).exists())
        self.flock.refresh_from_db()
        self.assertEqual(self.flock.quantity, 30)

    def accident_fixture(self):
        record = MortalityRecord.objects.create(
            user=self.user, branch=self.branch, flock=self.flock,
            quantity=2, reason='accident', date=self.today,
        )
        self.flock.refresh_from_db()
        self.assertEqual(self.flock.quantity, 28)
        return record

    def record_row(self, record):
        edit = self.page.locator(f'a[href="/mortality-records/{record.pk}/edit/"]')
        return self.page.get_by_role('row').filter(has=edit)
