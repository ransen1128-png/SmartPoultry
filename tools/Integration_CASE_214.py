"""SmartPoultry integration INT-030 (CASE-214)."""

import sys

if __name__ == '__main__':
    from run_automation import main

    raise SystemExit(main(['214', *sys.argv[1:]]))

from tools.automation_browser import expect
from tools.integration_workflows_browser import AccountIntegrationBrowserCase
from core.recovery_questions import RecoverySetupForm


class IntegrationCase214(AccountIntegrationBrowserCase):
    def test_int_030(self):
        answers = ('Integration field trip', 'Integration stuffed toy')
        setup = RecoverySetupForm({
            'question_one': 'school_trip', 'question_two': 'stuffed_toy',
            'answer_one': answers[0], 'answer_two': answers[1],
        })
        self.assertTrue(setup.is_valid(), setup.errors)
        setup.save(self.user)
        self.page.driver.delete_all_cookies()
        self.page.goto(f'{self.live_server_url}/forgot-password/')
        self.page.get_by_label('Email', exact=True).fill(self.user.email)
        self.page.get_by_label('Username', exact=True).fill(self.user.username)
        self.page.get_by_role('button', name='Continue', exact=True).click()
        expect(self.page).to_have_url(f'{self.live_server_url}/forgot-password/questions/')
        for index, answer in enumerate(answers, 1):
            self.page.locator(f'#answer_{index}').fill(answer)
        self.page.get_by_role('button', name='Verify Answers', exact=True).click()
        expect(self.page).to_have_url(f'{self.live_server_url}/forgot-password/new-password/')
        for label in ('New Password', 'Confirm Password'):
            self.page.get_by_label(label, exact=True).fill(self.new_password)
        self.page.get_by_role('button', name='Update Password', exact=True).click()
        expect(self.page).to_have_url(f'{self.live_server_url}/reset-password/complete/')
        self.assert_password_replaced()
