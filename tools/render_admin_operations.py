"""Read-only Admin Operations workflows for the deployed Selenium suite."""

from urllib.parse import parse_qs, urlsplit
import unittest

from tools.automation_browser import expect, launch_browser, live_base_url, read_test_value


class RenderAdminOperationsCase(unittest.TestCase):
    def setUp(self):
        email = read_test_value('SMARTPOULTRY_TEST_ADMIN_EMAIL', 'Render staff email: ')
        password = read_test_value('SMARTPOULTRY_TEST_ADMIN_PASSWORD', 'Render staff password: ', secret=True)
        self.base = live_base_url()
        browser = launch_browser()
        self.addCleanup(browser.close)
        self.page = browser.new_page()
        self.page.goto(f'{self.base}/login/')
        self.page.get_by_label('Email', exact=True).fill(email)
        self.page.get_by_label('Password', exact=True).fill(password)
        self.page.get_by_role('button', name='Login', exact=True).click()
        expect(self.page).to_have_url(f'{self.base}/admin-dashboard/', timeout=30000)
        self.users = self.page.locator('#users')

    def search(self, username):
        self.users.get_by_role('searchbox').fill(username)
        self.users.get_by_role('button', name='Search', exact=True).click()
        self.page.wait(lambda: parse_qs(urlsplit(self.page.url).query).get('q') == [username])

    def sample_row(self):
        username = read_test_value('SMARTPOULTRY_TEST_SAMPLE_USERNAME', 'Existing Render sample username: ')
        self.search(username)
        row = self.users.locator('tbody tr').filter(has=self.page.get_by_text(username, exact=True))
        expect(row).to_have_count(1)
        return row

    def filter_feedback(self, status):
        self.page.get_by_role('link', name='View All Feedback', exact=True).click()
        filters = self.page.locator('form[method="get"]').filter(
            has=self.page.get_by_role('button', name='Filter', exact=True),
        )
        filters.locator('select[name="status"]').select_option(status)
        filters.get_by_role('button', name='Filter', exact=True).click()
        expect(self.page).to_have_url(f'{self.base}/admin-dashboard/feedback/?status={status}')

    def test_case_177(self):
        self.search('qa-se-no-matching-account-177')
        expect(self.users.locator('tbody')).to_contain_text('No users found.')

    def test_case_178(self):
        self.filter_feedback('resolved')
        if self.page.get_by_role('link', name='Read Comment', exact=True).is_visible():
            self.skipTest('The Render account has resolved feedback. The empty-state precondition is absent.')
        expect(self.page.get_by_text('No feedback found.', exact=True)).to_be_visible()

    def test_case_179(self):
        expect(self.users.get_by_role('heading', name='Users Management', exact=True)).to_be_visible()

    def test_case_180(self):
        expect(self.sample_row()).to_be_visible()

    def test_case_181(self):
        row = self.sample_row()
        expect(row.get_by_role('cell', name='Active', exact=True)).to_be_visible()
        status = self.users.get_by_label('Status filter', exact=True)
        status.select_option('inactive')
        self.page.wait(lambda: parse_qs(urlsplit(self.page.url).query).get('status') == ['inactive'])
        expect(row).to_have_count(0)
        status.select_option('active')
        self.page.wait(lambda: parse_qs(urlsplit(self.page.url).query).get('status') == ['active'])
        expect(row).to_be_visible()

    def test_case_182(self):
        self.filter_feedback('new')
        link = self.page.get_by_role('link', name='Read Comment', exact=True).first
        if not link.is_visible():
            self.skipTest('The Render queue has no New feedback to open.')
        card = self.page.locator('.card-body .border').filter(has=link).first
        subject = card.get_by_role('heading').first.inner_text()
        rating = card.locator('.text-muted').first.inner_text().split('Rating ', 1)[1]
        link.click()
        expect(self.page.get_by_role('heading', name=subject, exact=True)).to_be_visible()
        expect(self.page.get_by_text(f'Rating {rating}')).to_be_visible()

    def test_case_183(self):
        self.page.locator('nav a[href="/profile/"]').filter(has_text='Admin Profile').click()
        expect(self.page.get_by_role('heading', name='Manage Profile', exact=True)).to_be_visible()
        for label in ('First Name', 'Last Name', 'Username', 'Email', 'Phone'):
            with self.subTest(field=label):
                expect(self.page.get_by_label(label, exact=True)).to_be_visible()

    def test_case_184(self):
        # Staff without account permissions get no View link, and the account page refuses them.
        row = self.sample_row()
        expect(row.locator('a[title="View"]')).to_have_count(0)
        toggle = row.locator('form[action*="/toggle/"]').get_attribute('action')
        user_id = toggle.strip('/').split('/')[-2]
        target = f'{self.base}/admin/accounts/userprofile/{user_id}/change/'
        with self.page.expect_response(
            lambda response: response.url == target and response.request.method == 'GET',
        ) as response:
            self.page.goto(target)
        self.assertEqual(response.value.status, 403, 'Staff without account permissions must not open the account page.')
