"""Isolated admin browser fixtures for staff without Django model permissions."""

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

from core.models import Feedback
from tools.automation_browser import expect, launch_browser


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AdminOperationsBrowserCase(StaticLiveServerTestCase):
    def setUp(self):
        users = get_user_model().objects
        password = 'StaffFixture!123'
        self.staff = users.create_user('qa-staff', 'qa-staff@example.invalid', password, is_staff=True)
        self.sample = users.create_user('qa-sample-user', 'qa-sample@example.invalid')
        self.feedback = Feedback.objects.create(
            user=self.sample, subject='QA sample feedback', message='Sample comment for the staff review.',
            rating=4, status='new',
        )
        self.reviewed_feedback = Feedback.objects.create(
            user=self.sample, subject='QA reviewed feedback', message='Previously reviewed comment.',
            rating=3, status='reviewed',
        )
        browser = launch_browser()
        self.addCleanup(browser.close)
        self.page = browser.new_page()
        self.page.goto(f'{self.live_server_url}/login/')
        self.page.get_by_label('Email', exact=True).fill(self.staff.email)
        self.page.get_by_label('Password', exact=True).fill(password)
        self.page.get_by_role('button', name='Login', exact=True).click()
        expect(self.page).to_have_url(f'{self.live_server_url}/admin-dashboard/')
        self.users = self.page.locator('#users')

    def search_users(self, query):
        self.users.get_by_role('searchbox').fill(query)
        self.users.get_by_role('button', name='Search', exact=True).click()
        expect(self.page).to_have_url(f'{self.live_server_url}/admin-dashboard/?status=&q={query}')

    def sample_row(self):
        return self.users.get_by_role('row').filter(
            has=self.page.get_by_role('cell', name=self.sample.email, exact=True),
        )

    def filter_feedback(self, status):
        self.page.get_by_role('link', name='View All Feedback', exact=True).click()
        filters = self.page.locator('form[method="get"]').filter(
            has=self.page.get_by_role('button', name='Filter', exact=True),
        )
        filters.locator('select[name="status"]').select_option(status)
        filters.get_by_role('button', name='Filter', exact=True).click()
        expect(self.page).to_have_url(f'{self.live_server_url}/admin-dashboard/feedback/?status={status}')
