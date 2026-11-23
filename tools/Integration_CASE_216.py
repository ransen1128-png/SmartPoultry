"""SmartPoultry integration INT-032 (CASE-216)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['216', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.integration_workflows_browser import AccountIntegrationBrowserCase


class IntegrationCase216(AccountIntegrationBrowserCase):
    def test_int_032(self):
        staff = self.staff_fixture()
        subject = 'Integration feedback from a farm user'
        self.page.goto(f'{self.live_server_url}/feedback/')
        self.page.get_by_label('Subject', exact=True).fill(subject)
        self.page.get_by_label('Rating', exact=True).select_option('4')
        self.page.get_by_label('Message', exact=True).fill('Check the staff feedback queue.')
        self.page.get_by_role('button', name='Submit Feedback', exact=True).click()
        expect(self.page.get_by_text(subject, exact=True)).to_be_visible()
        self.page.driver.delete_all_cookies()
        self.login(staff, self.original_password)
        expect(self.page).to_have_url(f'{self.live_server_url}/admin-dashboard/')
        self.page.get_by_role('link', name='View All Feedback', exact=True).click()
        self.page.locator('form[method="get"] select[name="status"]').select_option('new')
        self.page.get_by_role('button', name='Filter', exact=True).click()
        card = self.page.locator('.card-body .border').filter(has_text=subject)
        expect(card).to_be_visible()
        expect(card).to_contain_text('Rating 4/5')
