"""Read-only Selenium checks on Render for a dedicated farm account."""

import unittest

from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value


class RenderFarmReadOnlyCase(unittest.TestCase):
    def setUp(self):
        email = read_test_value('SMARTPOULTRY_TEST_EMAIL', 'Render farm-user email: ')
        password = read_test_value('SMARTPOULTRY_TEST_PASSWORD', 'Render farm-user password: ', secret=True)
        self.base = live_base_url()
        browser = launch_browser()
        self.addCleanup(browser.close)
        self.page = browser.new_page()
        self.page.goto(f'{self.base}/login/')
        self.page.get_by_label('Email', exact=True).fill(email)
        self.page.get_by_label('Password', exact=True).fill(password)
        self.page.get_by_role('button', name='Login', exact=True).click()
        expect(self.page).to_have_url(f'{self.base}/dashboard/', timeout=30000)

    def test_case_166(self):
        self.page.goto(f'{self.base}/profile/')
        expect(self.page.get_by_role('heading', name='Manage Profile', exact=True)).to_be_visible()
        for field in ('First Name', 'Last Name', 'Username', 'Email', 'Phone'):
            expect(self.page.get_by_label(field, exact=True)).to_be_visible()

    def open_feedback(self):
        self.page.goto(f'{self.base}/feedback/')
        return self.page.locator('main form').filter(
            has=self.page.get_by_role('button', name='Submit Feedback', exact=True),
        )

    def test_case_170(self):
        form = self.open_feedback()
        for label in ('Subject', 'Rating', 'Message'):
            expect(form.get_by_label(label, exact=True)).to_be_visible()
        rating = form.get_by_label('Rating', exact=True)
        expect(rating).to_have_value('5')
        expect(rating.locator('option:checked')).to_have_text('5 - Excellent')

    def test_case_171(self):
        rating = self.open_feedback().get_by_label('Rating', exact=True)
        rating.select_option(label='4 - Good')
        expect(rating).to_have_value('4')
        expect(rating.locator('option:checked')).to_have_text('4 - Good')

    def test_case_174(self):
        self.page.goto(f'{self.base}/settings/')
        self.page.get_by_role('tab', name='Account Security', exact=True).click()
        panel = self.page.locator('#security-panel')
        current = panel.get_by_label('Current Password', exact=True)
        current.fill('SyntheticToggleFixture!723')
        expect(current).to_have_attribute('type', 'password')
        panel.get_by_role('button', name='Show current password', exact=True).click()
        expect(current).to_have_attribute('type', 'text')
        expect(current).to_have_value('SyntheticToggleFixture!723')
        panel.get_by_role('button', name='Hide current password', exact=True).click()
        expect(current).to_have_attribute('type', 'password')
        expect(current).to_have_value('SyntheticToggleFixture!723')

    def test_case_175(self):
        self.page.goto(f'{self.base}/settings/')
        self.page.get_by_role('tab', name='Notification Preferences', exact=True).click()
        panel = self.page.locator('#notifications-panel')
        for name in ('Email alerts', 'Email notifications', 'In-app notifications', 'Push notifications'):
            expect(panel.get_by_role('switch', name=name)).to_be_visible()

    def test_case_213(self):
        branch = read_test_value('SMARTPOULTRY_TEST_BRANCH_NAME', 'Existing Render farm branch: ')
        expect(self.page.get_by_role('heading', name='Dashboard', exact=True)).to_be_visible()
        options = self.page.get_by_label('Farm branch', exact=True).locator('option')
        expect(options.filter(has_text=branch)).to_have_count(1)
